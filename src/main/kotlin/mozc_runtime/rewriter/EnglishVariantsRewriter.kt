package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/english_variants_rewriter.cc
// Ported from mozc/src/rewriter/english_variants_rewriter.h
class EnglishVariantsRewriter(
    private val posMatcher: PosMatcher,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            updated = expandEnglishVariantsWithSegment(segment) || updated
        }
        return updated
    }

    private fun expandEnglishVariantsWithSegment(segment: Segment): Boolean {
        var updated = false
        for (index in segment.candidatesSize() - 1 downTo 0) {
            val candidate = segment.mutableCandidate(index)
            if (candidate.attributes and Attribute.NO_VARIANTS_EXPANSION != 0 &&
                candidate.attributes and Attribute.USER_DICTIONARY == 0
            ) {
                continue
            }
            if (isEnglishTransliteration(candidate.contentValue) && isHiraganaText(candidate.contentKey)) {
                if (candidate.attributes and Attribute.NO_VARIANTS_EXPANSION == 0) {
                    candidate.attributes = candidate.attributes or Attribute.NO_VARIANTS_EXPANSION
                    updated = true
                }
                if (candidate.lid == candidate.rid &&
                    posMatcher.isUniqueNoun(candidate.lid) &&
                    candidate.value == candidate.value.uppercase()
                ) {
                    continue
                }
                val variants = englishVariants(candidate.contentValue)
                variants.asReversed().forEach { variant ->
                    val newValue = variant + candidate.functionalSuffix()
                    if (newValue != candidate.value && segment.candidates().none { it.value == newValue }) {
                        val copy = candidate.cloneCandidate()
                        copy.value = newValue
                        copy.contentValue = variant
                        copy.attributes = copy.attributes or Attribute.NO_VARIANTS_EXPANSION
                        segment.insertCandidateCopy(index + 1, copy)
                        updated = true
                    }
                }
            } else if (isEnglishTransliteration(candidate.contentValue) && isAlphabetText(candidate.contentKey)) {
                candidate.attributes = candidate.attributes or Attribute.NO_VARIANTS_EXPANSION
                updated = true
            }
        }
        return updated
    }

    private fun englishVariants(input: String): List<String> {
        if (input.isEmpty() || " " in input || input.lowercase() == input.uppercase()) {
            return listOf()
        }
        val lower = input.lowercase()
        val upper = input.uppercase()
        val capitalized = input.lowercase().replaceFirstChar { it.uppercase() }
        if (input != lower && input != upper && input != capitalized) {
            return if (input == lower) listOf() else listOf(lower)
        }
        val result = ArrayList<String>()
        if (input != lower) result += lower
        if (input != capitalized) result += capitalized
        if (input != upper) result += upper
        return result
    }

    private fun isEnglishTransliteration(value: String): Boolean =
        value.isNotEmpty() && value.all { it in 'A'..'Z' || it in 'a'..'z' || it == ' ' }

    private fun isAlphabetText(value: String): Boolean =
        value.isNotEmpty() && value.all { it in 'A'..'Z' || it in 'a'..'z' || it in 'Ａ'..'Ｚ' || it in 'ａ'..'ｚ' }
}
