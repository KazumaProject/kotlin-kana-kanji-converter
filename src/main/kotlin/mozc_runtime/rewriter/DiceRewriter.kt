package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments
import java.time.Clock

// Ported from mozc/src/rewriter/dice_rewriter.cc
// Ported from mozc/src/rewriter/dice_rewriter.h
class DiceRewriter(
    private val clock: Clock,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1 || segments.conversionSegment(0).key() != "さいころ") {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val base = segment.baseCandidate()
        val number = ((clock.millis() / 1000) % 6 + 1).toInt()
        val candidate = Candidate().also {
            it.setKeyValue("さいころ", number.toString())
            it.lid = base?.lid ?: 0
            it.rid = base?.rid ?: 0
            it.cost = base?.cost ?: 0
            it.description = "出た目の数"
            it.attributes = it.attributes or Attribute.NO_LEARNING
            it.category = Candidate.Category.OTHER
        }
        segment.insertCandidateCopy(0, candidate)
        return true
    }
}
