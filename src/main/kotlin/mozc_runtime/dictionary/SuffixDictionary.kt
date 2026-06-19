package mozc_runtime.dictionary

import mozc_data.MozcDataManager
import mozc_runtime.data.SerializedStringArray
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/dictionary/suffix_dictionary.*
class SuffixDictionary(
    entries: List<Token>,
) : DictionaryInterface {
    private val entries: List<Token> = entries.toList()

    override fun hasKey(key: String): Boolean = entries.any { it.key == key }

    override fun hasValue(value: String): Boolean = entries.any { it.value == value }

    override fun lookupPrefix(key: String, callback: (Token) -> Unit) {
        lookupPredictive(key, callback)
    }

    override fun lookupExact(key: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.key == key }
            .forEach(callback)
    }

    override fun lookupPredictive(key: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.key.startsWith(key) }
            .forEach(callback)
    }

    override fun lookupReverse(value: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.value == value }
            .forEach { token -> callback(token.copy(key = token.value, value = token.key)) }
    }

    override fun lookupComment(key: String, value: String): String? = null

    override fun populateReverseLookupCache() = Unit

    override fun clearReverseLookupCache() = Unit

    companion object {
        fun fromMozcDataManager(dataManager: MozcDataManager): SuffixDictionary {
            val keys = SerializedStringArray.from(dataManager.section("suffix_key"))
            val values = SerializedStringArray.from(dataManager.section("suffix_value"))
            val tokenBuffer = dataManager.section("suffix_token").asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(tokenBuffer.remaining() % TokenByteLength == 0) {
                "Suffix token data size must be divisible by $TokenByteLength: size=${tokenBuffer.remaining()}"
            }
            val tokenCount = tokenBuffer.remaining() / TokenByteLength
            require(keys.size() == tokenCount && values.size() == tokenCount) {
                "Suffix dictionary arrays have different sizes: keys=${keys.size()} values=${values.size()} tokens=$tokenCount"
            }
            val entries = ArrayList<Token>(tokenCount)
            repeat(tokenCount) { index ->
                val offset = index * TokenByteLength
                val key = keys[index]
                val rawValue = values[index]
                entries += Token(
                    key = key,
                    value = rawValue.ifEmpty { key },
                    lid = tokenBuffer.getUInt32AsInt(offset),
                    rid = tokenBuffer.getUInt32AsInt(offset + Int.SIZE_BYTES),
                    cost = tokenBuffer.getInt(offset + Int.SIZE_BYTES * 2),
                    attributes = Token.Attributes.SuffixDictionary,
                )
            }
            return SuffixDictionary(entries)
        }

        private const val TokenByteLength: Int = 12
    }
}

private fun ByteBuffer.getUInt32AsInt(offset: Int): Int {
    val value = getInt(offset).toLong() and 0xffffffffL
    require(value <= Int.MAX_VALUE) { "Suffix dictionary uint32 field exceeds Int range: $value" }
    return value.toInt()
}
