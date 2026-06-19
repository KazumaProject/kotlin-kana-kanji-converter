package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/small_letter_rewriter.cc
// Ported from mozc/src/rewriter/small_letter_rewriter.h
class SmallLetterRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            val small = toSmallKana(segment.key())
            if (small != null && segment.candidates().none { it.value == small }) {
                val base = segment.baseCandidate()
                val candidate = Candidate().also {
                    it.setKeyValue(segment.key(), small)
                    it.lid = base?.lid ?: 0
                    it.rid = base?.rid ?: 0
                    it.cost = base?.cost ?: 0
                    it.description = "小書き文字"
                    it.attributes = it.attributes or Attribute.NO_VARIANTS_EXPANSION
                }
                segment.insertCandidateCopy(calculateInsertPosition(segment, 3), candidate)
                updated = true
            }
        }
        return updated
    }

    private fun toSmallKana(key: String): String? =
        SmallKana[key]

    companion object {
        private val SmallKana = mapOf(
            "あ" to "ぁ",
            "い" to "ぃ",
            "う" to "ぅ",
            "え" to "ぇ",
            "お" to "ぉ",
            "や" to "ゃ",
            "ゆ" to "ゅ",
            "よ" to "ょ",
            "つ" to "っ",
        )
    }
}
