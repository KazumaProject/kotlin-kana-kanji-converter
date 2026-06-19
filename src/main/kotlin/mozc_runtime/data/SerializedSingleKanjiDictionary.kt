package mozc_runtime.data

import java.nio.ByteBuffer
import java.nio.ByteOrder

class SerializedSingleKanjiDictionary(
    tokenArray: ByteBuffer,
    stringArrayData: ByteBuffer,
    variantTypeArrayData: ByteBuffer,
    variantTokenArrayData: ByteBuffer,
    variantStringArrayData: ByteBuffer,
    nounPrefixTokenArrayData: ByteBuffer,
    nounPrefixStringArrayData: ByteBuffer,
) {
    private val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    private val strings = SerializedStringArray.from(stringArrayData)
    private val variantTypes = SerializedStringArray.from(variantTypeArrayData)
    private val variantTokens = variantTokenArrayData.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    private val variantStrings = SerializedStringArray.from(variantStringArrayData)
    private val nounPrefixDictionary = SerializedDictionary(nounPrefixTokenArrayData, nounPrefixStringArrayData)
    private val tokenCount: Int
    private val variantTokenCount: Int

    init {
        tokenCount = verifyKanjiData(tokens.asReadOnlyBuffer(), strings)
        variantTokenCount = verifyVariantData(variantTokens.asReadOnlyBuffer(), variantTypes, variantStrings)
        require(nounPrefixDictionary.size() >= 0) {
            "Single kanji noun prefix dictionary is invalid"
        }
    }

    fun lookupKanjiEntries(key: String): List<String> {
        val first = lowerBound(key)
        if (first !in 0 until tokenCount || strings[tokens.getInt(first * KanjiTokenByteLength)] != key) {
            return listOf()
        }
        val values = strings[tokens.getInt(first * KanjiTokenByteLength + 4)]
        return splitUtf8Graphemes(values)
    }

    fun generateDescription(surface: String): String? {
        val first = variantLowerBound(surface)
        if (first !in 0 until variantTokenCount || variantStrings[variantTokens.getInt(first * VariantTokenByteLength)] != surface) {
            return null
        }
        val offset = first * VariantTokenByteLength
        val original = variantStrings[variantTokens.getInt(offset + 4)]
        val type = variantTypes[variantTokens.getInt(offset + 8)]
        return original + "の" + type
    }

    fun lookupNounPrefixEntries(key: String): List<SerializedDictionaryToken> =
        nounPrefixDictionary.equalRange(key)

    private fun lowerBound(key: String): Int {
        var low = 0
        var high = tokenCount
        while (low < high) {
            val mid = (low + high) ushr 1
            if (strings[tokens.getInt(mid * KanjiTokenByteLength)] < key) {
                low = mid + 1
            } else {
                high = mid
            }
        }
        return low
    }

    private fun variantLowerBound(surface: String): Int {
        var low = 0
        var high = variantTokenCount
        while (low < high) {
            val mid = (low + high) ushr 1
            if (variantStrings[variantTokens.getInt(mid * VariantTokenByteLength)] < surface) {
                low = mid + 1
            } else {
                high = mid
            }
        }
        return low
    }

    companion object {
        private const val KanjiTokenByteLength: Int = 8
        private const val VariantTokenByteLength: Int = 12

        private fun verifyKanjiData(tokenArray: ByteBuffer, strings: SerializedStringArray): Int {
            val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(tokens.remaining() % KanjiTokenByteLength == 0) {
                "Single kanji token array size must be divisible by $KanjiTokenByteLength: actual=${tokens.remaining()}"
            }
            val count = tokens.remaining() / KanjiTokenByteLength
            repeat(count) { index ->
                val offset = index * KanjiTokenByteLength
                val keyIndex = tokens.getInt(offset)
                val valueIndex = tokens.getInt(offset + 4)
                require(keyIndex in 0 until strings.size()) {
                    "Single kanji key string index out of range: token=$index stringIndex=$keyIndex stringCount=${strings.size()}"
                }
                require(valueIndex in 0 until strings.size()) {
                    "Single kanji value string index out of range: token=$index stringIndex=$valueIndex stringCount=${strings.size()}"
                }
            }
            return count
        }

        private fun verifyVariantData(
            tokenArray: ByteBuffer,
            variantTypes: SerializedStringArray,
            variantStrings: SerializedStringArray,
        ): Int {
            val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(tokens.remaining() % VariantTokenByteLength == 0) {
                "Single kanji variant token array size must be divisible by $VariantTokenByteLength: actual=${tokens.remaining()}"
            }
            val count = tokens.remaining() / VariantTokenByteLength
            repeat(count) { index ->
                val offset = index * VariantTokenByteLength
                val targetIndex = tokens.getInt(offset)
                val originalIndex = tokens.getInt(offset + 4)
                val typeIndex = tokens.getInt(offset + 8)
                require(targetIndex in 0 until variantStrings.size()) {
                    "Single kanji variant target index out of range: token=$index stringIndex=$targetIndex stringCount=${variantStrings.size()}"
                }
                require(originalIndex in 0 until variantStrings.size()) {
                    "Single kanji variant original index out of range: token=$index stringIndex=$originalIndex stringCount=${variantStrings.size()}"
                }
                require(typeIndex in 0 until variantTypes.size()) {
                    "Single kanji variant type index out of range: token=$index typeIndex=$typeIndex typeCount=${variantTypes.size()}"
                }
            }
            return count
        }

        private fun splitUtf8Graphemes(value: String): List<String> {
            val result = ArrayList<String>()
            var index = 0
            while (index < value.length) {
                val codePoint = value.codePointAt(index)
                val next = index + Character.charCount(codePoint)
                val text = String(Character.toChars(codePoint))
                if (next < value.length && isVariationSelector(value.codePointAt(next))) {
                    val selector = value.codePointAt(next)
                    result += text + String(Character.toChars(selector))
                    index = next + Character.charCount(selector)
                } else {
                    result += text
                    index = next
                }
            }
            return result
        }

        private fun isVariationSelector(codePoint: Int): Boolean =
            codePoint in 0xFE00..0xFE0F || codePoint in 0xE0100..0xE01EF
    }
}
