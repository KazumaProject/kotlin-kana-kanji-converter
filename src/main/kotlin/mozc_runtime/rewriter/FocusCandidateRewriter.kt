package mozc_runtime.rewriter

import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedStringArray
import mozc_runtime.dictionary.PosMatcher
import java.nio.ByteBuffer

// Ported from mozc/src/rewriter/focus_candidate_rewriter.cc
// Ported from mozc/src/rewriter/focus_candidate_rewriter.h
class FocusCandidateRewriter(
    counterSuffixData: ByteBuffer,
    private val posMatcher: PosMatcher,
) : Rewriter {
    private val counterSuffixes = SerializedStringArray.from(counterSuffixData).toList()

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean = false

    override fun focus(segments: Segments, segmentIndex: Int, candidateIndex: Int): Boolean {
        if (segmentIndex !in 0 until segments.segmentsSize()) {
            return false
        }
        val segment = segments.segment(segmentIndex)
        if (candidateIndex !in 0 until segment.candidatesSize()) {
            return false
        }
        val value = segment.candidate(candidateIndex).contentValue
        BracketPairs[value]?.let { right ->
            for (index in segmentIndex + 1 until segments.segmentsSize()) {
                val target = segments.mutableSegment(index)
                val found = (0 until target.candidatesSize()).firstOrNull { target.candidate(it).contentValue == right }
                if (found != null) {
                    target.moveCandidate(found, 0)
                    return true
                }
            }
        }
        val left = BracketPairs.entries.firstOrNull { it.value == value }?.key
        if (left != null) {
            for (index in segmentIndex - 1 downTo 0) {
                val target = segments.mutableSegment(index)
                val found = (0 until target.candidatesSize()).firstOrNull { target.candidate(it).contentValue == left }
                if (found != null) {
                    target.moveCandidate(found, 0)
                    return true
                }
            }
        }
        return focusNumberStyle(segments, segmentIndex, candidateIndex)
    }

    private fun focusNumberStyle(segments: Segments, segmentIndex: Int, candidateIndex: Int): Boolean {
        val selected = segments.segment(segmentIndex).candidate(candidateIndex)
        if (!posMatcher.isNumber(selected.lid) && !posMatcher.isKanjiNumber(selected.lid)) {
            return false
        }
        var updated = false
        for (index in segmentIndex + 1 until segments.segmentsSize()) {
            val segment = segments.mutableSegment(index)
            if (segment.candidatesSize() == 0) {
                continue
            }
            if (counterSuffixes.any { suffix -> segment.candidate(0).contentValue.endsWith(suffix) }) {
                continue
            }
            val found = (0 until segment.candidatesSize()).firstOrNull {
                val candidate = segment.candidate(it)
                candidate.lid == selected.lid && candidate.rid == selected.rid
            }
            if (found != null) {
                segment.moveCandidate(found, 0)
                updated = true
            }
        }
        return updated
    }

    companion object {
        private val BracketPairs = mapOf(
            "「" to "」",
            "『" to "』",
            "（" to "）",
            "(" to ")",
            "[" to "]",
            "［" to "］",
            "{" to "}",
            "｛" to "｝",
            "【" to "】",
        )
    }
}
