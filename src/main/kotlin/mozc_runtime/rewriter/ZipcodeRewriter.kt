package mozc_runtime.rewriter

import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/zipcode_rewriter.cc
// Ported from mozc/src/rewriter/zipcode_rewriter.h
class ZipcodeRewriter(
    private val posMatcher: PosMatcher,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useZipCodeConversion) {
            return false
        }
        var updated = false
        segments.conversionSegments().forEach { segment ->
            for (index in 0 until segment.candidatesSize()) {
                val candidate = segment.mutableCandidate(index)
                if (posMatcher.isZipcode(candidate.lid) && candidate.description.isEmpty()) {
                    candidate.description = candidate.contentKey
                    updated = true
                }
            }
        }
        return updated
    }
}
