package mozc_runtime.data

import java.nio.ByteBuffer
import java.nio.ByteOrder

enum class ZeroQueryType(val id: Int) {
    NONE(0),
    NUMBER_SUFFIX(1),
    EMOTICON(2),
    EMOJI(3),
    BIGRAM(4),
    SUFFIX(5),
    SUPPLEMENTAL_MODEL(6),
}

data class SerializedZeroQueryEntry(
    val key: String,
    val value: String,
    val type: ZeroQueryType,
)

class SerializedZeroQueryDictionary(
    tokenArray: ByteBuffer,
    stringArrayData: ByteBuffer,
) {
    private val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    private val strings = SerializedStringArray.from(stringArrayData)
    private val tokenCount: Int

    init {
        tokenCount = verifyData(tokens.asReadOnlyBuffer(), strings)
    }

    fun equalRange(key: String): List<SerializedZeroQueryEntry> {
        val first = lowerBound(key)
        val result = ArrayList<SerializedZeroQueryEntry>()
        var index = first
        while (index < tokenCount) {
            val entry = entryAt(index)
            if (entry.key != key) {
                break
            }
            result += entry
            index += 1
        }
        return result
    }

    fun entryAt(index: Int): SerializedZeroQueryEntry {
        require(index in 0 until tokenCount) {
            "SerializedZeroQueryDictionary token index out of range: index=$index size=$tokenCount"
        }
        val offset = index * TokenByteLength
        val typeId = tokens.getShort(offset + 8).toInt() and 0xffff
        return SerializedZeroQueryEntry(
            key = strings[tokens.getInt(offset)],
            value = strings[tokens.getInt(offset + 4)],
            type = ZeroQueryType.entries.firstOrNull { it.id == typeId }
                ?: error("Unknown zero query type: index=$index type=$typeId"),
        )
    }

    private fun lowerBound(key: String): Int {
        var low = 0
        var high = tokenCount
        while (low < high) {
            val mid = (low + high) ushr 1
            if (keyAt(mid) < key) {
                low = mid + 1
            } else {
                high = mid
            }
        }
        return low
    }

    private fun keyAt(index: Int): String = strings[tokens.getInt(index * TokenByteLength)]

    companion object {
        const val TokenByteLength: Int = 16

        fun verifyData(tokenArray: ByteBuffer, strings: SerializedStringArray): Int {
            val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(tokens.remaining() % TokenByteLength == 0) {
                "SerializedZeroQueryDictionary token array size must be divisible by $TokenByteLength: actual=${tokens.remaining()}"
            }
            val count = tokens.remaining() / TokenByteLength
            repeat(count) { index ->
                val offset = index * TokenByteLength
                val keyIndex = tokens.getInt(offset)
                val valueIndex = tokens.getInt(offset + 4)
                val typeId = tokens.getShort(offset + 8).toInt() and 0xffff
                require(keyIndex in 0 until strings.size()) {
                    "Zero query key string index out of range: token=$index stringIndex=$keyIndex stringCount=${strings.size()}"
                }
                require(valueIndex in 0 until strings.size()) {
                    "Zero query value string index out of range: token=$index stringIndex=$valueIndex stringCount=${strings.size()}"
                }
                require(ZeroQueryType.entries.any { it.id == typeId }) {
                    "Unknown zero query type: token=$index type=$typeId"
                }
                require(tokens.getShort(offset + 10).toInt() == 0) {
                    "Zero query token uint16 padding must be zero: token=$index"
                }
                require(tokens.getInt(offset + 12) == 0) {
                    "Zero query token uint32 padding must be zero: token=$index"
                }
            }
            return count
        }
    }
}
