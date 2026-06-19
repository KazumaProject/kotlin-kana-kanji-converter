package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/version_rewriter.cc
// Ported from mozc/src/rewriter/version_rewriter.h
class VersionRewriter(
    private val version: String,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1 || segments.conversionSegment(0).key() != "ばーじょん") {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val base = segment.baseCandidate()
        val candidate = Candidate().also {
            it.setKeyValue("ばーじょん", version)
            it.lid = base?.lid ?: 0
            it.rid = base?.rid ?: 0
            it.cost = base?.cost ?: 0
            it.description = "Mozc version"
            it.attributes = it.attributes or Attribute.NO_LEARNING
        }
        segment.insertCandidateCopy(0, candidate)
        return true
    }
}
