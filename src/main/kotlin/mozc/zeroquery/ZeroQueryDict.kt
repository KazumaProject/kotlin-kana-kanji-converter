package com.kazumaproject.mozc.zeroquery

data class ZeroQueryCandidate(
    val value: String,
    val type: ZeroQueryType,
)

private data class DecodedZeroQueryToken(
    val keyIndex: Int,
    val valueIndex: Int,
    val type: ZeroQueryType,
)

class ZeroQueryDict(
    tokenBytes: ByteArray,
    stringBytes: ByteArray,
) {
    private val strings: List<String> = SerializedStringArrayReader.read(stringBytes)
    private val tokens: List<DecodedZeroQueryToken> = decodeTokens(tokenBytes)

    val entryCount: Int get() = tokens.size
    val stringCount: Int get() = strings.size

    fun lookup(key: String): List<ZeroQueryCandidate> {
        val lower = lowerBound(key)
        val upper = upperBound(key)
        if (lower == upper) {
            return emptyList()
        }
        return tokens.subList(lower, upper).map { token ->
            ZeroQueryCandidate(
                value = strings[token.valueIndex],
                type = token.type,
            )
        }
    }

    private fun lowerBound(key: String): Int {
        var low = 0
        var high = tokens.size
        while (low < high) {
            val mid = (low + high) ushr 1
            if (UnicodeCodePointStringComparator.compare(keyAt(mid), key) < 0) {
                low = mid + 1
            } else {
                high = mid
            }
        }
        return low
    }

    private fun upperBound(key: String): Int {
        var low = 0
        var high = tokens.size
        while (low < high) {
            val mid = (low + high) ushr 1
            if (UnicodeCodePointStringComparator.compare(key, keyAt(mid)) < 0) {
                high = mid
            } else {
                low = mid + 1
            }
        }
        return low
    }

    private fun keyAt(tokenIndex: Int): String = strings[tokens[tokenIndex].keyIndex]

    private fun decodeTokens(tokenBytes: ByteArray): List<DecodedZeroQueryToken> {
        if (tokenBytes.size % ZeroQueryBinaryWriter.TokenEntrySize != 0) {
            error(
                "Invalid zero query token array: byte size=${tokenBytes.size}, " +
                        "reason=token file size is not a multiple of ${ZeroQueryBinaryWriter.TokenEntrySize}"
            )
        }

        val result = ArrayList<DecodedZeroQueryToken>(tokenBytes.size / ZeroQueryBinaryWriter.TokenEntrySize)
        var previousKey: String? = null
        for (offset in tokenBytes.indices step ZeroQueryBinaryWriter.TokenEntrySize) {
            val tokenIndex = offset / ZeroQueryBinaryWriter.TokenEntrySize
            val keyIndex = tokenBytes.readUInt32LE(offset).toIntInRange("key_index", tokenIndex)
            val valueIndex = tokenBytes.readUInt32LE(offset + 4).toIntInRange("value_index", tokenIndex)
            val typeCode = tokenBytes.readUInt16LE(offset + 8)
            val unused16 = tokenBytes.readUInt16LE(offset + 10)
            val unused32 = tokenBytes.readUInt32LE(offset + 12)

            if (keyIndex !in strings.indices) {
                failToken(tokenIndex, "key_index out of range: key_index=$keyIndex, string array size=${strings.size}")
            }
            if (valueIndex !in strings.indices) {
                failToken(tokenIndex, "value_index out of range: value_index=$valueIndex, string array size=${strings.size}")
            }
            if (unused16 != 0 || unused32 != 0L) {
                failToken(tokenIndex, "unused fields must be zero: unused16=$unused16, unused32=$unused32")
            }

            val type = ZeroQueryType.fromCode(typeCode)
            val key = strings[keyIndex]
            val previous = previousKey
            if (previous != null && UnicodeCodePointStringComparator.compare(previous, key) > 0) {
                failToken(tokenIndex, "token array is not sorted by key string: previous='$previous', current='$key'")
            }
            previousKey = key

            result += DecodedZeroQueryToken(
                keyIndex = keyIndex,
                valueIndex = valueIndex,
                type = type,
            )
        }
        return result
    }

    private fun Long.toIntInRange(fieldName: String, tokenIndex: Int): Int {
        if (this > Int.MAX_VALUE) {
            failToken(tokenIndex, "$fieldName is too large: $fieldName=$this")
        }
        return toInt()
    }

    private fun failToken(tokenIndex: Int, reason: String): Nothing =
        error("Invalid zero query token array: token index=$tokenIndex, reason=$reason")
}
