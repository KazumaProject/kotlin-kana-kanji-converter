package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/merger_rewriter.h
class MergerRewriter(
    private val rewriters: List<Rewriter>,
) : Rewriter {
    fun rewriterNames(): List<String> = rewriters.map { it::class.simpleName ?: it::class.java.name }

    override fun capability(request: RewriterRequest): Int = Capability.ALL

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        val requestedCapability = capabilityForRequestType(request.requestType)
        var updated = false
        rewriters.forEach { rewriter ->
            if (rewriter.capability(request) and requestedCapability != 0) {
                updated = rewriter.rewrite(request, segments) || updated
            }
        }
        if (request.requestType == RequestType.SUGGESTION &&
            segments.conversionSegmentsSize() == 1 &&
            !request.mixedConversion
        ) {
            val segment = segments.mutableConversionSegment(0)
            while (segment.candidatesSize() > request.suggestionsSize) {
                segment.popBackCandidate()
                updated = true
            }
        }
        return updated
    }

    override fun focus(segments: Segments, segmentIndex: Int, candidateIndex: Int): Boolean {
        var result = false
        rewriters.forEach { rewriter ->
            result = rewriter.focus(segments, segmentIndex, candidateIndex) || result
        }
        return result
    }

    companion object {
        fun markBestCandidatePerSegment(segments: Segments): Boolean {
            var updated = false
            segments.conversionSegments().forEach { segment ->
                if (segment.candidatesSize() > 0 &&
                    segment.candidate(0).attributes and Attribute.BEST_CANDIDATE == 0
                ) {
                    segment.mutableCandidate(0).attributes =
                        segment.candidate(0).attributes or Attribute.BEST_CANDIDATE
                    updated = true
                }
            }
            return updated
        }
    }
}
