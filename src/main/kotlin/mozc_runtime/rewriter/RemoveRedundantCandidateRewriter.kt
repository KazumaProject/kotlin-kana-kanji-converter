package mozc_runtime.rewriter

import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/remove_redundant_candidate_rewriter.cc
// Ported from mozc/src/rewriter/remove_redundant_candidate_rewriter.h
class RemoveRedundantCandidateRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.NONE

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() == 1) {
            val segment = segments.mutableConversionSegment(0)
            if (segment.candidatesSize() == 1 && segment.candidate(0).value == segment.key()) {
                segment.clearCandidates()
                return true
            }
        }
        return false
    }
}
