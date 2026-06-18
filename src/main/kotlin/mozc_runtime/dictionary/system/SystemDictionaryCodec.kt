package mozc_runtime.dictionary.system

import mozc_runtime.dictionary.Token
import java.nio.ByteBuffer

// Ported from mozc/src/dictionary/system/codec.*
class SystemDictionaryCodec {
    fun sectionNameForKey(): String = "k"

    fun sectionNameForValue(): String = "v"

    fun sectionNameForTokens(): String = "t"

    fun sectionNameForPos(): String = "p"

    fun encodeKeyToBytes(src: String): ByteArray = transformKey(src).toByteArray(Charsets.UTF_8)

    fun decodeKey(src: ByteArray): String = transformKey(src.toString(Charsets.UTF_8))

    fun encodeValueToBytes(src: String): ByteArray {
        val out = ArrayList<Byte>(src.length)
        src.codePoints().forEachOrdered { codePoint ->
            when {
                codePoint >= 0x3041 && codePoint < 0x3095 -> {
                    out += (codePoint - 0x3041 + ValueHiraganaOffset).toByte()
                }
                codePoint >= 0x30a1 && codePoint < 0x30fd -> {
                    out += (codePoint - 0x30a1 + ValueKatakanaOffset).toByte()
                }
                codePoint < 0x10000 && ((codePoint ushr 8) and 0xff) == 0 -> {
                    out += ValueCharMarkAscii.toByte()
                    out += (codePoint and 0xff).toByte()
                }
                codePoint < 0x10000 && (codePoint and 0xff) == 0 -> {
                    out += ValueCharMarkXX00.toByte()
                    out += ((codePoint ushr 8) and 0xff).toByte()
                }
                codePoint >= 0x4e00 && codePoint < 0x9800 -> {
                    val high = ((codePoint - 0x4e00) ushr 8) + ValueKanjiOffset
                    out += high.toByte()
                    out += (codePoint and 0xff).toByte()
                }
                codePoint in 0x10000..0x10ffff -> {
                    var left = (codePoint ushr 16) and 0xff
                    val middle = (codePoint ushr 8) and 0xff
                    val right = codePoint and 0xff
                    if (middle == 0) {
                        left = left or ValueCharMarkCodepointMiddle0
                    }
                    if (right == 0) {
                        left = left or ValueCharMarkCodepointRight0
                    }
                    out += ValueCharMarkCodepoint.toByte()
                    out += left.toByte()
                    if (middle != 0) {
                        out += middle.toByte()
                    }
                    if (right != 0) {
                        out += right.toByte()
                    }
                }
                else -> {
                    require(codePoint <= 0x10ffff) { "Invalid Unicode code point: $codePoint" }
                    out += ValueCharMarkOtherUcs2.toByte()
                    out += ((codePoint ushr 8) and 0xff).toByte()
                    out += (codePoint and 0xff).toByte()
                }
            }
        }
        return out.toByteArray()
    }

    fun decodeValue(src: ByteArray): String {
        val out = StringBuilder()
        var index = 0
        while (index < src.size) {
            val marker = src[index].toInt() and 0xff
            val codePoint: Int
            when {
                marker >= ValueHiraganaOffset && marker < ValueKatakanaOffset -> {
                    codePoint = 0x3041 + marker - ValueHiraganaOffset
                    index += 1
                }
                marker >= ValueKatakanaOffset && marker < ValueCharMarkAscii -> {
                    codePoint = 0x30a1 + marker - ValueKatakanaOffset
                    index += 1
                }
                marker == ValueCharMarkAscii -> {
                    require(index + 1 < src.size) { "Encoded value ASCII marker is truncated" }
                    codePoint = src[index + 1].toInt() and 0xff
                    index += 2
                }
                marker == ValueCharMarkXX00 -> {
                    require(index + 1 < src.size) { "Encoded value XX00 marker is truncated" }
                    codePoint = (src[index + 1].toInt() and 0xff) shl 8
                    index += 2
                }
                marker == ValueCharMarkCodepoint -> {
                    require(index + 1 < src.size) { "Encoded value codepoint marker is truncated" }
                    val left = src[index + 1].toInt() and 0xff
                    var cursor = index + 2
                    var value = (left and ValueCharMarkCodepointLeftMask) shl 16
                    if ((left and ValueCharMarkCodepointMiddle0) == 0) {
                        require(cursor < src.size) { "Encoded value codepoint middle byte is truncated" }
                        value += (src[cursor].toInt() and 0xff) shl 8
                        cursor += 1
                    }
                    if ((left and ValueCharMarkCodepointRight0) == 0) {
                        require(cursor < src.size) { "Encoded value codepoint right byte is truncated" }
                        value += src[cursor].toInt() and 0xff
                        cursor += 1
                    }
                    codePoint = value
                    index = cursor
                }
                marker == ValueCharMarkOtherUcs2 -> {
                    require(index + 2 < src.size) { "Encoded value UCS2 marker is truncated" }
                    codePoint = ((src[index + 1].toInt() and 0xff) shl 8) + (src[index + 2].toInt() and 0xff)
                    index += 3
                }
                marker < ValueHiraganaOffset -> {
                    require(index + 1 < src.size) { "Encoded value kanji marker is truncated" }
                    codePoint = (((marker - ValueKanjiOffset) shl 8) + 0x4e00) + (src[index + 1].toInt() and 0xff)
                    index += 2
                }
                else -> error("Invalid encoded value marker: $marker")
            }
            out.appendCodePoint(codePoint)
        }
        return out.toString()
    }

    internal fun decodeToken(tokens: ByteBuffer, offset: Int, tokenInfo: TokenInfo): DecodeResult {
        val flags = readFlags(u8(tokens, offset))
        if ((flags and SpellingCorrectionFlag) != 0) {
            tokenInfo.token.attributes = tokenInfo.token.attributes or Token.Attributes.SpellingCorrection
        }
        var cursor = offset + 1
        cursor = decodePos(tokens, cursor, flags, tokenInfo)
        cursor = decodeCost(tokens, cursor, tokenInfo)
        cursor = decodeValueInfo(tokens, offset, cursor, flags, tokenInfo)
        return DecodeResult(continues = (flags and LastTokenFlag) == 0, readBytes = cursor - offset)
    }

    internal fun readTokenForReverseLookup(tokens: ByteBuffer, offset: Int): ReverseTokenRead {
        val flags = readFlags(u8(tokens, offset))
        var cursor = offset + 1
        cursor += when (flags and PosTypeFlagMask) {
            FrequentPosFlag -> 1
            MonoPosFlag -> 2
            FullPosFlag -> 3
            SameAsPrevPosFlag -> 0
            else -> error("Invalid token POS flag: ${flags and PosTypeFlagMask}")
        }
        cursor += if ((u8(tokens, cursor) and SmallCostFlag) != 0) 1 else 2
        val valueRead = readValueInfo(tokens, offset, cursor, flags)
        return ReverseTokenRead(
            continues = (flags and LastTokenFlag) == 0,
            valueId = valueRead.first,
            readBytes = valueRead.second - offset,
        )
    }

    fun tokensTerminationFlag(): Int = TokenTerminationFlag

    private fun transformKey(src: String): String {
        val out = StringBuilder()
        src.codePoints().forEachOrdered { original ->
            var code = original
            val offset = when {
                (code in 0x0001..0x001f) || (code in 0x3041..0x305f) -> 0x3041 - 0x0001
                (code in 0x0040..0x0075) || (code in 0x3060..0x3095) -> 0x3060 - 0x0040
                (code in 0x0076..0x0077) || (code in 0x30fb..0x30fc) -> 0x30fb - 0x0076
                else -> 0
            }
            code = if (code < 0x80) code + offset else code - offset
            require(code > 0) { "Encoded key contains zero code point" }
            out.appendCodePoint(code)
        }
        return out.toString()
    }

    private fun decodePos(tokens: ByteBuffer, offset: Int, flags: Int, tokenInfo: TokenInfo): Int {
        val token = tokenInfo.token
        return when (flags and PosTypeFlagMask) {
            FrequentPosFlag -> {
                tokenInfo.posType = TokenInfo.PosType.Frequent
                tokenInfo.idInFrequentPosMap = u8(tokens, offset)
                offset + 1
            }
            SameAsPrevPosFlag -> {
                tokenInfo.posType = TokenInfo.PosType.SameAsPrevious
                offset
            }
            MonoPosFlag -> {
                val id = u8(tokens, offset) or (u8(tokens, offset + 1) shl 8)
                token.lid = id
                token.rid = id
                offset + 2
            }
            FullPosFlag -> {
                token.lid = u8(tokens, offset) + ((u8(tokens, offset + 1) and 0x0f) shl 8)
                token.rid = (u8(tokens, offset + 1) ushr 4) + (u8(tokens, offset + 2) shl 4)
                offset + 3
            }
            else -> error("Invalid token POS flag: ${flags and PosTypeFlagMask}")
        }
    }

    private fun decodeCost(tokens: ByteBuffer, offset: Int, tokenInfo: TokenInfo): Int {
        val first = u8(tokens, offset)
        return if ((first and SmallCostFlag) != 0) {
            tokenInfo.token.cost = (first and SmallCostMask) shl 8
            offset + 1
        } else {
            tokenInfo.token.cost = (first shl 8) + u8(tokens, offset + 1)
            offset + 2
        }
    }

    private fun decodeValueInfo(tokens: ByteBuffer, tokenOffset: Int, offset: Int, flags: Int, tokenInfo: TokenInfo): Int =
        when (flags and ValueTypeFlagMask) {
            AsIsHiraganaValueFlag -> {
                tokenInfo.valueType = TokenInfo.ValueType.AsIsHiragana
                offset
            }
            AsIsKatakanaValueFlag -> {
                tokenInfo.valueType = TokenInfo.ValueType.AsIsKatakana
                offset
            }
            SameAsPrevValueFlag -> {
                tokenInfo.valueType = TokenInfo.ValueType.SameAsPrevious
                offset
            }
            NormalValueFlag -> {
                tokenInfo.valueType = TokenInfo.ValueType.Default
                val valueRead = readValueInfo(tokens, tokenOffset, offset, flags)
                tokenInfo.idInValueTrie = valueRead.first
                valueRead.second
            }
            else -> error("Invalid token value flag: ${flags and ValueTypeFlagMask}")
        }

    private fun readValueInfo(tokens: ByteBuffer, tokenOffset: Int, offset: Int, flags: Int): Pair<Int, Int> =
        if ((flags and ValueTypeFlagMask) == NormalValueFlag) {
            var id = u8(tokens, offset) or (u8(tokens, offset + 1) shl 8)
            val nextOffset = if ((flags and CrammedIdFlag) != 0) {
                id = id or ((u8(tokens, tokenOffset) and UpperCrammedIdMask) shl 16)
                offset + 2
            } else {
                id = id or (u8(tokens, offset + 2) shl 16)
                offset + 3
            }
            id to nextOffset
        } else {
            -1 to offset
        }

    private fun readFlags(value: Int): Int =
        if ((value and CrammedIdFlag) != 0) value and UpperFlagsMask else value

    private fun u8(buffer: ByteBuffer, index: Int): Int {
        require(index in 0 until buffer.limit()) {
            "Token byte offset is out of range: offset=$index limit=${buffer.limit()}"
        }
        return buffer.get(index).toInt() and 0xff
    }

    internal data class DecodeResult(val continues: Boolean, val readBytes: Int)

    internal data class ReverseTokenRead(val continues: Boolean, val valueId: Int, val readBytes: Int)

    companion object {
        private const val ValueCharMarkAscii = 0xfc
        private const val ValueCharMarkXX00 = 0xfd
        private const val ValueCharMarkOtherUcs2 = 0xfe
        private const val ValueCharMarkCodepoint = 0xff
        private const val ValueCharMarkCodepointMiddle0 = 0x80
        private const val ValueCharMarkCodepointRight0 = 0x40
        private const val ValueCharMarkCodepointLeftMask = 0x1f
        private const val ValueKanjiOffset = 0x01
        private const val ValueHiraganaOffset = 0x4b
        private const val ValueKatakanaOffset = 0x9f
        private const val SmallCostFlag = 0x80
        private const val SmallCostMask = 0x7f
        private const val TokenTerminationFlag = 0xff
        private const val ValueTypeFlagMask = 0x03
        private const val AsIsHiraganaValueFlag = 0x01
        private const val AsIsKatakanaValueFlag = 0x02
        private const val SameAsPrevValueFlag = 0x03
        private const val NormalValueFlag = 0x00
        private const val PosTypeFlagMask = 0x0c
        private const val FullPosFlag = 0x04
        private const val MonoPosFlag = 0x08
        private const val SameAsPrevPosFlag = 0x0c
        private const val FrequentPosFlag = 0x00
        private const val SpellingCorrectionFlag = 0x10
        private const val CrammedIdFlag = 0x40
        private const val UpperFlagsMask = 0xc0
        private const val UpperCrammedIdMask = 0x3f
        private const val LastTokenFlag = 0x80
    }
}
