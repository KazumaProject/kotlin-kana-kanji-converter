package mozc_runtime.rewriter

import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.PosMatcher
import java.nio.ByteBuffer

// Ported from mozc/src/rewriter/collocation_rewriter.cc
// Ported from mozc/src/rewriter/collocation_rewriter.h
class CollocationRewriter(
    collocationData: ByteBuffer,
    suppressionData: ByteBuffer,
    private val posMatcher: PosMatcher,
) : Rewriter {
    private val collocationSize = collocationData.remaining()
    private val suppressionSize = suppressionData.remaining()

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() < 2 || collocationSize == 0 && suppressionSize == 0) {
            return false
        }
        var updated = false
        segments.conversionSegments().zipWithNext().forEach { (left, right) ->
            if (left.candidatesSize() > 0 && right.candidatesSize() > 0) {
                val leftCandidate = left.mutableCandidate(0)
                val rightCandidate = right.candidate(0)
                if (posMatcher.isContentNoun(leftCandidate.lid) && posMatcher.isContentNoun(rightCandidate.rid)) {
                    leftCandidate.costBeforeRescoring = leftCandidate.cost
                    updated = true
                }
            }
        }
        return updated
    }
}
