package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/language_aware_rewriter.cc
// Ported from mozc/src/rewriter/language_aware_rewriter.h
class LanguageAwareRewriter(
    private val posMatcher: PosMatcher,
    private val dictionary: DictionaryInterface,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int {
        if (!request.useSpellingCorrection) {
            return Capability.NONE
        }
        return Capability.PREDICTION or Capability.SUGGESTION
    }

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1) {
            return false
        }
        val raw = request.rawText
        val composition = request.compositionText
        if (raw.length <= 3 || raw == composition || asciiToFullWidth(raw) == composition) {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val key = segment.key()
        if (dictionary.hasKey(key) || !dictionary.hasValue(raw)) {
            return false
        }
        val alphabetIds = (0 until segment.candidatesSize())
            .map { segment.candidate(it) }
            .firstOrNull { it.value.all { ch -> ch in 'A'..'Z' || ch in 'a'..'z' } }
        val candidate = Candidate().also {
            it.setKeyValue(raw, raw)
            it.lid = alphabetIds?.lid ?: posMatcher.getUnknownId()
            it.rid = alphabetIds?.rid ?: posMatcher.getUnknownId()
            it.attributes = it.attributes or Attribute.NO_VARIANTS_EXPANSION or Attribute.NO_EXTRA_DESCRIPTION
        }
        val rank = if (request.zeroQuerySuggestion && request.mixedConversion) 2 else 0
        segment.insertCandidateCopy(rank.coerceIn(0, segment.candidatesSize()), candidate)
        return true
    }
}
