package mozc_runtime.rewriter

import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/user_boundary_history_rewriter.cc
// Ported from mozc/src/rewriter/user_boundary_history_rewriter.h
class UserBoundaryHistoryRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.resized()) {
            return false
        }
        return false
    }
}
