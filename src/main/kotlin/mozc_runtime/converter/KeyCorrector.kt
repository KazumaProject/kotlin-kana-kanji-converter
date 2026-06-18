package mozc_runtime.converter

// Ported from mozc/src/converter/key_corrector.h
// Ported from mozc/src/converter/key_corrector.cc
class KeyCorrector(
    key: String,
    val mode: InputMode,
    historySize: Int,
) {
    enum class InputMode {
        ROMAN,
        KANA,
    }

    private var available: Boolean = false
    private var correctedKeyValue: String = ""
    private var originalKeyValue: String = ""
    private val alignment = ArrayList<Int>()
    private val reverseAlignment = ArrayList<Int>()

    init {
        available = init(key, mode, historySize)
    }

    fun correctedKey(): String = correctedKeyValue

    fun originalKey(): String = originalKeyValue

    fun isAvailable(): Boolean = available

    fun getCorrectedPosition(originalKeyPos: Int): Int =
        alignment.getOrElse(originalKeyPos) { InvalidPosition }

    fun getOriginalPosition(correctedKeyPos: Int): Int =
        reverseAlignment.getOrElse(correctedKeyPos) { InvalidPosition }

    fun getCorrectedPrefix(originalKeyPos: Int): String {
        if (!isAvailable() || mode == InputMode.KANA) {
            return ""
        }
        val correctedKeyPos = getCorrectedPosition(originalKeyPos)
        if (!isValidPosition(correctedKeyPos)) {
            return ""
        }
        val correctedSubstr = correctedKeyValue.utf8Substring(correctedKeyPos)
        val originalSubstr = originalKeyValue.utf8Substring(originalKeyPos)
        return if (correctedSubstr != originalSubstr) correctedSubstr else ""
    }

    fun getOriginalOffset(originalKeyPos: Int, newKeyOffset: Int): Int {
        if (!isAvailable() || mode == InputMode.KANA) {
            return InvalidPosition
        }
        val correctedKeyPos = getCorrectedPosition(originalKeyPos)
        if (!isValidPosition(correctedKeyPos)) {
            return InvalidPosition
        }
        return if (reverseAlignment.size == correctedKeyPos + newKeyOffset) {
            val originalPosition = getOriginalPosition(correctedKeyPos)
            if (isValidPosition(originalPosition)) alignment.size - originalPosition else InvalidPosition
        } else {
            val originalKeyPos2 = getOriginalPosition(correctedKeyPos + newKeyOffset)
            if (isValidPosition(originalKeyPos2) && originalKeyPos2 >= originalKeyPos) {
                originalKeyPos2 - originalKeyPos
            } else {
                InvalidPosition
            }
        }
    }

    private fun init(key: String, mode: InputMode, historySize: Int): Boolean {
        if (mode == InputMode.KANA) {
            return false
        }
        if (key.isEmpty() || key.utf8Size() >= MaxSize) {
            return false
        }

        originalKeyValue = key
        val chars = key.utf8Chars()
        val corrected = StringBuilder()
        var charIndex = 0
        while (charIndex < chars.size) {
            val originalStartByte = chars[charIndex].startByte
            val beforeBytes = corrected.toString().utf8Size()
            val rewrite = if (originalStartByte < historySize) {
                null
            } else {
                rewriteDoubleNN(chars, charIndex)
                    ?: rewriteNN(chars, charIndex)
                    ?: rewriteYu(chars, charIndex)
                    ?: rewriteNI(chars, charIndex)
                    ?: rewriteSmallTsu(chars, charIndex)
                    ?: rewriteM(chars, charIndex)
            }

            val consumedChars: Int
            val output: String
            if (rewrite == null) {
                consumedChars = 1
                output = chars[charIndex].text
            } else {
                consumedChars = rewrite.consumedChars
                output = rewrite.output
            }
            corrected.append(output)

            val consumedBytes = chars.subList(charIndex, charIndex + consumedChars).sumOf { it.byteSize }
            val outputBytes = output.utf8Size()
            if (consumedBytes <= 0 || outputBytes <= 0) {
                return false
            }
            if (consumedBytes == outputBytes) {
                repeat(consumedBytes) { index ->
                    alignment += beforeBytes + index
                    reverseAlignment += originalStartByte + index
                }
            } else {
                alignment += beforeBytes
                repeat(consumedBytes - 1) {
                    alignment += InvalidPosition
                }
                reverseAlignment += originalStartByte
                repeat(outputBytes - 1) {
                    reverseAlignment += InvalidPosition
                }
            }
            charIndex += consumedChars
        }
        correctedKeyValue = corrected.toString()
        return originalKeyValue.utf8Size() == alignment.size && correctedKeyValue.utf8Size() == reverseAlignment.size
    }

    data class Rewrite(
        val consumedChars: Int,
        val output: String,
    )

    companion object {
        private const val MaxSize: Int = 128
        const val InvalidPosition: Int = -1

        fun isValidPosition(pos: Int): Boolean = pos != InvalidPosition

        fun getCorrectedCostPenalty(key: String): Int =
            if ("んん" in key || "っっ" in key) 0 else 3000
    }
}

private fun rewriteNN(chars: List<Utf8Char>, index: Int): KeyCorrector.Rewrite? {
    if (index == 0 || index + 1 >= chars.size || chars[index].codePoint != 0x3093) {
        return null
    }
    val output = when (chars[index + 1].codePoint) {
        0x3042 -> "んな"
        0x3044 -> "んに"
        0x3046 -> "んぬ"
        0x3048 -> "んね"
        0x304a -> "んの"
        else -> return null
    }
    return KeyCorrector.Rewrite(consumedChars = 2, output = output)
}

private fun rewriteDoubleNN(chars: List<Utf8Char>, index: Int): KeyCorrector.Rewrite? {
    if (index + 3 >= chars.size) {
        return null
    }
    val first = chars[index].codePoint
    if (first == 0x3093 || getScriptType(first) != ScriptType.HIRAGANA) {
        return null
    }
    if (chars[index + 1].codePoint != 0x3093 || chars[index + 2].codePoint != 0x3093) {
        return null
    }
    return when (chars[index + 3].codePoint) {
        0x3093 -> null
        0x3042, 0x3044, 0x3046, 0x3048, 0x304a -> KeyCorrector.Rewrite(
            consumedChars = 2,
            output = chars[index].text,
        )
        else -> KeyCorrector.Rewrite(
            consumedChars = 3,
            output = chars[index].text + "ん",
        )
    }
}

private fun rewriteNI(chars: List<Utf8Char>, index: Int): KeyCorrector.Rewrite? {
    if (index + 1 >= chars.size || chars[index].codePoint != 0x306b) {
        return null
    }
    val output = when (chars[index + 1].codePoint) {
        0x3083 -> "んや"
        0x3085 -> "んゆ"
        0x3087 -> "んよ"
        else -> return null
    }
    return KeyCorrector.Rewrite(consumedChars = 2, output = output)
}

private fun rewriteM(chars: List<Utf8Char>, index: Int): KeyCorrector.Rewrite? {
    if (index == 0 || index + 1 >= chars.size) {
        return null
    }
    val current = chars[index].codePoint
    if (current != 0x006d && current != 0xff4d) {
        return null
    }
    val next = chars[index + 1].codePoint
    if (next % 3 != 0 && next in 0x306f..0x307d) {
        return KeyCorrector.Rewrite(consumedChars = 2, output = "ん" + chars[index + 1].text)
    }
    return null
}

private fun rewriteSmallTsu(chars: List<Utf8Char>, index: Int): KeyCorrector.Rewrite? {
    if (index + 3 >= chars.size) {
        return null
    }
    val first = chars[index].codePoint
    val last = chars[index + 3].codePoint
    if (first == 0x3063 || last == 0x3063) {
        return null
    }
    if (getScriptType(first) != ScriptType.HIRAGANA || getScriptType(last) != ScriptType.HIRAGANA) {
        return null
    }
    if (chars[index + 1].codePoint != 0x3063 || chars[index + 2].codePoint != 0x3063) {
        return null
    }
    return KeyCorrector.Rewrite(consumedChars = 4, output = chars[index].text + "っ" + chars[index + 3].text)
}

private fun rewriteYu(chars: List<Utf8Char>, index: Int): KeyCorrector.Rewrite? {
    if (index + 2 >= chars.size) {
        return null
    }
    val first = chars[index].codePoint
    if (first !in setOf(0x304d, 0x3057, 0x3061, 0x306b, 0x3072, 0x308a)) {
        return null
    }
    if (chars[index + 1].codePoint != 0x3085 || chars[index + 2].codePoint == 0x3046) {
        return null
    }
    return KeyCorrector.Rewrite(consumedChars = 2, output = chars[index].text + "ゅう")
}
