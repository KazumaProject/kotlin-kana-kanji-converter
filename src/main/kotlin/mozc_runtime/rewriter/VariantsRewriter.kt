package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.InnerSegment
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/variants_rewriter.cc
// Ported from mozc/src/rewriter/variants_rewriter.h
class VariantsRewriter(
    private val posMatcher: PosMatcher,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.ALL

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            updated = rewriteSegment(segment) || updated
        }
        return updated
    }

    private fun rewriteSegment(segment: Segment): Boolean {
        var updated = false
        var index = 0
        while (index < segment.candidatesSize()) {
            val candidate = segment.mutableCandidate(index)
            if (candidate.attributes and Attribute.NO_EXTRA_DESCRIPTION != 0) {
                index += 1
                continue
            }
            if (candidate.attributes and Attribute.NO_VARIANTS_EXPANSION != 0) {
                setDescriptionForCandidate(candidate)
                index += 1
                updated = true
                continue
            }
            val alternative = createAlternative(candidate)
            if (alternative == null) {
                setDescriptionForCandidate(candidate)
                index += 1
            } else {
                if (candidate.value == alternative.primaryValue) {
                    val copy = candidate.cloneCandidate()
                    val isNumericBase = candidate.description.isEmpty() && digitsToHalfWidth(candidate.key).allDigitsForVariant()
                    if (isNumericBase) {
                        setSingleInnerSegment(candidate)
                    }
                    setDescriptionWithType(candidate, alternative.primaryDescriptionType)
                    copy.value = alternative.secondaryValue
                    copy.contentValue = alternative.secondaryContentValue
                    if (!isNumericBase) {
                        setSingleInnerSegment(copy)
                    }
                    setDescriptionWithType(copy, alternative.secondaryDescriptionType)
                    segment.insertCandidateCopy(index + 1, copy)
                } else {
                    val copy = candidate.cloneCandidate()
                    copy.value = alternative.primaryValue
                    copy.contentValue = alternative.primaryContentValue
                    setSingleInnerSegment(copy)
                    setDescriptionWithType(copy, alternative.primaryDescriptionType)
                    segment.insertCandidateCopy(index, copy)
                    setDescriptionWithType(segment.mutableCandidate(index + 1), alternative.secondaryDescriptionType)
                }
                index += 2
            }
            updated = true
        }
        return updated
    }

    private fun setSingleInnerSegment(candidate: Candidate) {
        candidate.innerSegments.clear()
        candidate.innerSegments += InnerSegment(
            key = candidate.key,
            value = candidate.value,
            contentKey = candidate.contentKey,
            contentValue = candidate.contentValue,
        )
    }

    fun setDescriptionForCandidate(candidate: Candidate) {
        candidate.description = getDescription(candidate, DescriptionType.FULL_HALF_WIDTH or DescriptionType.CHARACTER_FORM or DescriptionType.ZIPCODE)
        candidate.attributes = candidate.attributes or Attribute.NO_EXTRA_DESCRIPTION
    }

    private fun setDescriptionWithType(candidate: Candidate, descriptionType: Int) {
        candidate.description = getDescription(candidate, descriptionType)
        candidate.attributes = candidate.attributes or Attribute.NO_EXTRA_DESCRIPTION
    }

    private fun getDescription(candidate: Candidate, descriptionType: Int): String {
        var type = descriptionType
        val pieces = ArrayList<String>()
        val script = scriptTypeWithoutSymbols(candidate.value)
        var characterFormMessage = ""
        if (type and DescriptionType.CHARACTER_FORM != 0) {
            when (script) {
                TextScript.HIRAGANA -> {
                    characterFormMessage = "ひらがな"
                    type = type and DescriptionType.FULL_HALF_WIDTH.inv()
                }
                TextScript.KATAKANA -> {
                    characterFormMessage = "カタカナ"
                    type = (type and DescriptionType.FULL_HALF_WIDTH.inv()) or DescriptionType.HALF_WIDTH
                }
                TextScript.NUMBER -> {
                    characterFormMessage = "数字"
                    type = (type and DescriptionType.FULL_HALF_WIDTH.inv()) or DescriptionType.FULL_WIDTH
                }
                TextScript.ALPHABET -> {
                    characterFormMessage = "アルファベット"
                    type = type and DescriptionType.FULL_HALF_WIDTH.inv()
                }
                TextScript.KANJI, TextScript.EMOJI -> type = type and DescriptionType.FULL_HALF_WIDTH.inv()
                TextScript.UNKNOWN -> if (!hasCharacterFormDescription(candidate.value)) {
                    type = type and DescriptionType.FULL_HALF_WIDTH.inv()
                }
            }
        }
        if (candidate.description.isNotEmpty()) {
            characterFormMessage = ""
            if (candidate.attributes and Attribute.NO_VARIANTS_EXPANSION != 0) {
                type = type and DescriptionType.FULL_HALF_WIDTH.inv()
            }
        }
        val form = formType(candidate.value)
        if (type and DescriptionType.FULL_HALF_WIDTH != 0) {
            when (form) {
                TextForm.FULL -> pieces += "[全]"
                TextForm.HALF -> pieces += "[半]"
                TextForm.UNKNOWN -> Unit
            }
        } else if (type and DescriptionType.FULL_WIDTH != 0 && form == TextForm.FULL) {
            pieces += "[全]"
        } else if (type and DescriptionType.HALF_WIDTH != 0 && form == TextForm.HALF) {
            pieces += "[半]"
        } else if (script == TextScript.UNKNOWN && candidate.description == "数字" && form == TextForm.FULL) {
            pieces += "[全]"
        }
        if (characterFormMessage.isNotEmpty()) {
            pieces += characterFormMessage
        }
        when (candidate.value) {
            "\\", "＼" -> pieces += "バックスラッシュ"
            "¥", "￥" -> pieces += "円記号"
            "~" -> pieces += "チルダ"
            else -> if (candidate.description.isNotEmpty()) {
                pieces += candidate.description
            }
        }
        if (type and DescriptionType.ZIPCODE != 0 && posMatcher.isZipcode(candidate.lid) && candidate.lid == candidate.rid) {
            pieces.clear()
            if (candidate.contentKey.isNotEmpty()) {
                pieces += candidate.contentKey
            }
            if (candidate.description.isNotEmpty()) {
                pieces += candidate.description
            }
        }
        return pieces.joinToString(" ")
    }

    private fun createAlternative(candidate: Candidate): AlternativeCandidate? {
        if (candidate.value.length != candidate.contentValue.length) {
            return null
        }
        val value = candidate.value
        if (value == "＼") {
            return null
        }
        val full = toPrimaryForm(value)
        val half = toSecondaryForm(value)
        if (full == half || full == value && half == value) {
            return null
        }
        if (!value.any { isAsciiFormTarget(it) || isFullWidthAsciiFormTarget(it) || it in ExtraFullFormSymbols || it in ExtraHalfFormSymbols }) {
            return null
        }
        return AlternativeCandidate(
            primaryValue = full,
            secondaryValue = half,
            primaryContentValue = toPrimaryForm(candidate.contentValue),
            secondaryContentValue = toSecondaryForm(candidate.contentValue),
            primaryDescriptionType = DescriptionType.FULL_WIDTH or DescriptionType.CHARACTER_FORM or DescriptionType.ZIPCODE,
            secondaryDescriptionType = DescriptionType.HALF_WIDTH or DescriptionType.CHARACTER_FORM or DescriptionType.ZIPCODE,
        )
    }

    private data class AlternativeCandidate(
        val primaryValue: String,
        val secondaryValue: String,
        val primaryContentValue: String,
        val secondaryContentValue: String,
        val primaryDescriptionType: Int,
        val secondaryDescriptionType: Int,
    )

    private object DescriptionType {
        const val FULL_WIDTH: Int = 1
        const val HALF_WIDTH: Int = 2
        const val FULL_HALF_WIDTH: Int = FULL_WIDTH or HALF_WIDTH
        const val CHARACTER_FORM: Int = 4
        const val ZIPCODE: Int = 8
    }
}

private enum class TextScript {
    HIRAGANA,
    KATAKANA,
    KANJI,
    NUMBER,
    ALPHABET,
    EMOJI,
    UNKNOWN,
}

private enum class TextForm {
    FULL,
    HALF,
    UNKNOWN,
}

private fun scriptTypeWithoutSymbols(value: String): TextScript {
    var current: TextScript? = null
    value.codePoints().forEachOrdered { codePoint ->
        val type = when {
            codePoint in 0x3041..0x309f || codePoint == 0x30fc -> TextScript.HIRAGANA
            codePoint in 0x30a1..0x30ff || codePoint in 0x31f0..0x31ff -> TextScript.KATAKANA
            codePoint in 0x30..0x39 || codePoint in 0xff10..0xff19 -> TextScript.NUMBER
            codePoint in 0x41..0x5a || codePoint in 0x61..0x7a || codePoint in 0xff21..0xff3a || codePoint in 0xff41..0xff5a -> TextScript.ALPHABET
            codePoint == 0x3005 || codePoint in 0x3400..0x4dbf || codePoint in 0x4e00..0x9fff || codePoint in 0xf900..0xfaff -> TextScript.KANJI
            codePoint in 0x1f000..0x1faff -> TextScript.EMOJI
            else -> null
        }
        if (type != null) {
            current = if (current == null || current == type) type else TextScript.UNKNOWN
        }
    }
    return current ?: TextScript.UNKNOWN
}

private fun formType(value: String): TextForm {
    var current: TextForm? = null
    value.codePoints().forEachOrdered { codePoint ->
        val form = when {
            codePoint in 0x21..0x7e -> TextForm.HALF
            codePoint in 0xff01..0xff5e || codePoint == 0x3000 -> TextForm.FULL
            codePoint.toChar() in ExtraFullFormSymbols -> TextForm.FULL
            codePoint.toChar() in ExtraHalfFormSymbols -> TextForm.HALF
            else -> null
        }
        if (form != null) {
            current = if (current == null || current == form) form else TextForm.UNKNOWN
        }
    }
    return current ?: TextForm.UNKNOWN
}

private fun hasCharacterFormDescription(value: String): Boolean {
    if (value.isEmpty()) {
        return false
    }
    val form = formType(value)
    if (form == TextForm.UNKNOWN) {
        return false
    }
    return value.codePoints().allMatch { codePoint ->
        (
            isAsciiFormTarget(codePoint.toChar()) ||
                isFullWidthAsciiFormTarget(codePoint.toChar()) ||
                codePoint.toChar() in ExtraFullFormSymbols ||
                codePoint.toChar() in ExtraHalfFormSymbols
            ) &&
            codePoint !in 0x30..0x39 &&
            codePoint !in 0xff10..0xff19 &&
            codePoint !in 0x41..0x5a &&
            codePoint !in 0x61..0x7a &&
            codePoint !in 0xff21..0xff3a &&
            codePoint !in 0xff41..0xff5a
    }
}

private fun isAsciiFormTarget(ch: Char): Boolean = ch.code in 0x21..0x7e

private fun isFullWidthAsciiFormTarget(ch: Char): Boolean = ch.code in 0xff01..0xff5e

private fun String.allDigitsForVariant(): Boolean = isNotEmpty() && all { it in '0'..'9' }

private val ExtraFullFormSymbols = setOf('」', '〜', '’', '”', '−', '￥')

private val ExtraHalfFormSymbols = setOf('¥', '¬', '¯')

private fun toPrimaryForm(value: String): String =
    when (value) {
        "'" -> "’"
        "\"" -> "”"
        "-" -> "−"
        "~" -> "〜"
        "\\" -> "￥"
        else -> asciiToFullWidth(value)
    }

private fun toSecondaryForm(value: String): String =
    when (value) {
        "’" -> "'"
        "”" -> "\""
        "−" -> "-"
        "〜" -> "~"
        "￥" -> "\\"
        "＼" -> "\\"
        else -> asciiToHalfWidth(value)
    }
