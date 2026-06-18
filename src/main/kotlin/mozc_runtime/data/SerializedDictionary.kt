package mozc_runtime.data

import java.nio.ByteBuffer
import java.nio.ByteOrder

data class SerializedDictionaryToken(
    val key: String,
    val value: String,
    val description: String,
    val additionalDescription: String,
    val lid: Int,
    val rid: Int,
    val cost: Int,
)

class SerializedDictionary(
    tokenArray: ByteBuffer,
    stringArrayData: ByteBuffer,
) : Iterable<SerializedDictionaryToken> {
    private val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    private val strings = SerializedStringArray.from(stringArrayData)
    private val tokenCount: Int

    init {
        tokenCount = verifyData(tokens.asReadOnlyBuffer(), strings)
    }

    fun size(): Int = tokenCount

    fun equalRange(key: String): List<SerializedDictionaryToken> {
        val first = lowerBound(key)
        val result = ArrayList<SerializedDictionaryToken>()
        var index = first
        while (index < tokenCount) {
            val token = tokenAt(index)
            if (token.key != key) {
                break
            }
            result += token
            index += 1
        }
        return result
    }

    fun tokenAt(index: Int): SerializedDictionaryToken {
        require(index in 0 until tokenCount) { "SerializedDictionary token index out of range: index=$index size=$tokenCount" }
        val offset = index * TokenByteLength
        return SerializedDictionaryToken(
            key = strings[tokens.getInt(offset)],
            value = strings[tokens.getInt(offset + 4)],
            description = strings[tokens.getInt(offset + 8)],
            additionalDescription = strings[tokens.getInt(offset + 12)],
            lid = tokens.getShort(offset + 16).toInt() and 0xFFFF,
            rid = tokens.getShort(offset + 18).toInt() and 0xFFFF,
            cost = tokens.getShort(offset + 20).toInt(),
        )
    }

    override fun iterator(): Iterator<SerializedDictionaryToken> = object : Iterator<SerializedDictionaryToken> {
        private var index = 0

        override fun hasNext(): Boolean = index < tokenCount

        override fun next(): SerializedDictionaryToken = tokenAt(index++)
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
        const val TokenByteLength: Int = 24

        fun verifyData(tokenArray: ByteBuffer, strings: SerializedStringArray): Int {
            val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(tokens.remaining() % TokenByteLength == 0) {
                "SerializedDictionary token array size must be divisible by $TokenByteLength: actual=${tokens.remaining()}"
            }
            val count = tokens.remaining() / TokenByteLength
            repeat(count) { index ->
                val offset = index * TokenByteLength
                require(tokens.getShort(offset + 22).toInt() == 0) {
                    "SerializedDictionary token padding must be zero: index=$index"
                }
                repeat(4) { stringIndexField ->
                    val stringIndex = tokens.getInt(offset + stringIndexField * Int.SIZE_BYTES)
                    require(stringIndex in 0 until strings.size()) {
                        "SerializedDictionary string index out of range: token=$index field=$stringIndexField stringIndex=$stringIndex stringCount=${strings.size()}"
                    }
                }
            }
            return count
        }
    }
}
