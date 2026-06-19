package mozc_runtime.rewriter

import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/user_segment_history_rewriter.cc
// Ported from mozc/src/rewriter/user_segment_history_rewriter.h
class UserSegmentHistoryRewriter(
    private val posMatcher: PosMatcher,
    private val posGroup: PosGroup,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean =
        MergerRewriter.markBestCandidatePerSegment(segments)
}
