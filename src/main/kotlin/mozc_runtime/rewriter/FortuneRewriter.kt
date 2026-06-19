package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments
import java.time.Clock
import java.time.LocalDate
import java.time.ZoneOffset

// Ported from mozc/src/rewriter/fortune_rewriter.cc
// Ported from mozc/src/rewriter/fortune_rewriter.h
class FortuneRewriter(
    private val clock: Clock,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1 || segments.conversionSegment(0).key() != "うらない") {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val date = LocalDate.now(clock.withZone(ZoneOffset.UTC))
        val value = Fortunes[((date.toEpochDay() % Fortunes.size) + Fortunes.size).toInt() % Fortunes.size]
        val base = segment.baseCandidate()
        val candidate = Candidate().also {
            it.setKeyValue("うらない", value)
            it.lid = base?.lid ?: 0
            it.rid = base?.rid ?: 0
            it.cost = base?.cost ?: 0
            it.description = "今日の運勢"
            it.attributes = it.attributes or Attribute.NO_LEARNING
            it.category = Candidate.Category.OTHER
        }
        segment.insertCandidateCopy(0, candidate)
        return true
    }

    companion object {
        private val Fortunes = listOf("大吉", "中吉", "小吉", "吉", "末吉", "凶")
    }
}
