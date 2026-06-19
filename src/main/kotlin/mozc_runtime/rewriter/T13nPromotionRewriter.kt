package mozc_runtime.rewriter

import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/t13n_promotion_rewriter.cc
// Ported from mozc/src/rewriter/t13n_promotion_rewriter.h
class T13nPromotionRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.NONE

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            updated = promoteKatakana(segment) || updated
        }
        return updated
    }

    private fun promoteKatakana(segment: Segment): Boolean {
        val katakanaIndex = (0 until segment.candidatesSize()).firstOrNull { isKatakanaText(segment.candidate(it).value) }
            ?: return false
        val insertPosition = calculateInsertPosition(segment, 3)
        if (katakanaIndex <= insertPosition) {
            return false
        }
        segment.moveCandidate(katakanaIndex, insertPosition)
        return true
    }
}
