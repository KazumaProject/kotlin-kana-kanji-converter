package mozc_runtime.converter

import java.nio.charset.StandardCharsets

internal fun String.utf8Size(): Int = toByteArray(StandardCharsets.UTF_8).size

internal fun String.utf8Substring(startByte: Int, byteSize: Int = utf8Size() - startByte): String {
    val bytes = toByteArray(StandardCharsets.UTF_8)
    require(startByte in 0..bytes.size) {
        "UTF-8 start byte is out of range: startByte=$startByte size=${bytes.size}"
    }
    require(byteSize >= 0 && startByte <= bytes.size - byteSize) {
        "UTF-8 byte range is out of range: startByte=$startByte byteSize=$byteSize size=${bytes.size}"
    }
    require(startByte == bytes.size || isUtf8Boundary(bytes, startByte)) {
        "UTF-8 start byte is not a character boundary: startByte=$startByte"
    }
    val endByte = startByte + byteSize
    require(endByte == bytes.size || isUtf8Boundary(bytes, endByte)) {
        "UTF-8 end byte is not a character boundary: endByte=$endByte"
    }
    return String(bytes, startByte, byteSize, StandardCharsets.UTF_8)
}

internal fun String.utf8Prefix(byteSize: Int): String = utf8Substring(0, byteSize)

internal fun String.charsLen(): Int = codePointCount(0, length)

internal data class Utf8Char(
    val text: String,
    val codePoint: Int,
    val startByte: Int,
    val byteSize: Int,
)

internal fun String.utf8Chars(): List<Utf8Char> {
    val result = ArrayList<Utf8Char>()
    var charIndex = 0
    var byteIndex = 0
    while (charIndex < length) {
        val codePoint = codePointAt(charIndex)
        val charText = String(Character.toChars(codePoint))
        val byteSize = charText.utf8Size()
        result += Utf8Char(
            text = charText,
            codePoint = codePoint,
            startByte = byteIndex,
            byteSize = byteSize,
        )
        charIndex += Character.charCount(codePoint)
        byteIndex += byteSize
    }
    return result
}

internal enum class ScriptType {
    UNKNOWN_SCRIPT,
    KATAKANA,
    HIRAGANA,
    KANJI,
    NUMBER,
    ALPHABET,
    EMOJI,
}

internal enum class FormType {
    UNKNOWN_FORM,
    HALF_WIDTH,
    FULL_WIDTH,
}

internal fun getScriptType(codePoint: Int): ScriptType =
    when {
        codePoint in 0x0030..0x0039 || codePoint in 0xff10..0xff19 -> ScriptType.NUMBER
        codePoint in 0x0041..0x005a ||
            codePoint in 0x0061..0x007a ||
            codePoint in 0xff21..0xff3a ||
            codePoint in 0xff41..0xff5a -> ScriptType.ALPHABET
        codePoint == 0x3005 ||
            codePoint in 0x3400..0x4dbf ||
            codePoint in 0x4e00..0x9fff ||
            codePoint in 0xf900..0xfaff ||
            codePoint in 0x20000..0x2a6df ||
            codePoint in 0x2a700..0x2b73f ||
            codePoint in 0x2b740..0x2b81f ||
            codePoint in 0x2f800..0x2fa1f -> ScriptType.KANJI
        codePoint in 0x3041..0x309f || codePoint == 0x1b001 -> ScriptType.HIRAGANA
        codePoint in 0x30a1..0x30ff ||
            codePoint in 0x31f0..0x31ff ||
            codePoint in 0xff65..0xff9f ||
            codePoint == 0x1b000 -> ScriptType.KATAKANA
        codePoint in 0x02300..0x023f3 ||
            codePoint in 0x02700..0x027bf ||
            codePoint in 0x1f000..0x1f02f ||
            codePoint in 0x1f030..0x1f09f ||
            codePoint in 0x1f0a0..0x1f0ff ||
            codePoint in 0x1f100..0x1f2ff ||
            codePoint in 0x1f300..0x1f5ff ||
            codePoint in 0x1f600..0x1f64f ||
            codePoint in 0x1f680..0x1f6ff ||
            codePoint in 0x1f700..0x1f77f ||
            codePoint == 0x26ce -> ScriptType.EMOJI
        else -> ScriptType.UNKNOWN_SCRIPT
    }

internal fun getScriptType(value: String): ScriptType {
    var current: ScriptType? = null
    value.codePoints().forEachOrdered { codePoint ->
        val type = when {
            codePoint == 0x30fc || codePoint == 0x30fb || codePoint in 0x3099..0x309c -> null
            (codePoint == 0xff0e || codePoint == 0x002e) && current == ScriptType.NUMBER -> null
            else -> getScriptType(codePoint)
        }
        if (type != null) {
            current = if (current == null || current == type) type else ScriptType.UNKNOWN_SCRIPT
        }
    }
    return current ?: ScriptType.UNKNOWN_SCRIPT
}

internal fun containsScriptType(value: String, type: ScriptType): Boolean {
    var found = false
    value.codePoints().forEachOrdered { codePoint ->
        if (getScriptType(codePoint) == type) {
            found = true
        }
    }
    return found
}

internal fun isScriptType(value: String, type: ScriptType): Boolean {
    var all = true
    value.codePoints().forEachOrdered { codePoint ->
        if (getScriptType(codePoint) != type && !(codePoint == 0x30fc && type == ScriptType.HIRAGANA)) {
            all = false
        }
    }
    return all
}

internal fun getFormType(codePoint: Int): FormType =
    when {
        codePoint in 0x0020..0x007f ||
            codePoint in 0x27e6..0x27ed ||
            codePoint in 0x2985..0x2986 -> FormType.HALF_WIDTH
        codePoint == 0x00a2 ||
            codePoint == 0x00a3 ||
            codePoint == 0x00a5 ||
            codePoint == 0x00a6 ||
            codePoint == 0x00ac ||
            codePoint == 0x00af -> FormType.HALF_WIDTH
        codePoint == 0x20a9 ||
            codePoint in 0xff61..0xff9f ||
            codePoint in 0xffa0..0xffbe ||
            codePoint in 0xffc2..0xffcf ||
            codePoint in 0xffd2..0xffd7 ||
            codePoint in 0xffda..0xffdc ||
            codePoint in 0xffe8..0xffee -> FormType.HALF_WIDTH
        else -> FormType.FULL_WIDTH
    }

internal fun hiraganaToKatakana(value: String): String {
    val out = StringBuilder()
    value.codePoints().forEachOrdered { codePoint ->
        out.appendCodePoint(if (codePoint in 0x3041..0x3096) codePoint + 0x60 else codePoint)
    }
    return out.toString()
}

internal fun fullWidthAsciiToHalfWidthAscii(value: String): String {
    val out = StringBuilder()
    value.codePoints().forEachOrdered { codePoint ->
        val converted = when (codePoint) {
            0x3000 -> 0x20
            in 0xff01..0xff5e -> codePoint - 0xfee0
            else -> codePoint
        }
        out.appendCodePoint(converted)
    }
    return out.toString()
}

private fun isUtf8Boundary(bytes: ByteArray, index: Int): Boolean =
    index == 0 || index == bytes.size || (bytes[index].toInt() and 0xc0) != 0x80
