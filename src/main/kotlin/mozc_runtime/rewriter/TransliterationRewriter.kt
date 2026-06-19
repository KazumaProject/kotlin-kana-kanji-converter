package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/transliteration_rewriter.cc
// Ported from mozc/src/rewriter/transliteration_rewriter.h
class TransliterationRewriter(
    private val posMatcher: PosMatcher,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useT13nConversion || request.skipSlowRewriters || segments.conversionSegmentsSize() != 1) {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val raw = digitsToHalfWidth(request.rawText)
        if (!raw.allDigitsForTransliteration()) {
            return false
        }
        var updated = false
        val values = listOf(raw, toFullWidthDigits(raw))
        values.forEach { value ->
            if (segment.candidates().none { it.value == value }) {
                val candidate = Candidate().also {
                    it.setKeyValue(raw, value)
                    it.lid = posMatcher.getUnknownId()
                    it.rid = posMatcher.getUnknownId()
                    it.attributes = it.attributes or Attribute.NO_VARIANTS_EXPANSION
                }
                segment.appendCandidate(candidate)
                updated = true
            }
        }
        return updated
    }
}

private fun String.allDigitsForTransliteration(): Boolean = isNotEmpty() && all { it in '0'..'9' }
