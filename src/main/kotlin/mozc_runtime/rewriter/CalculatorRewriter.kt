package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/calculator_rewriter.cc
// Ported from mozc/src/rewriter/calculator_rewriter.h
class CalculatorRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1) {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val expression = segment.key()
        if (!expression.endsWith("=")) {
            return false
        }
        val value = evaluateIntegerExpression(expression.dropLast(1)) ?: return false
        val base = segment.baseCandidate()
        val candidate = Candidate().also {
            it.setKeyValue(expression, value.toString())
            it.lid = base?.lid ?: 0
            it.rid = base?.rid ?: 0
            it.cost = base?.cost ?: 0
            it.description = "計算結果"
            it.attributes = it.attributes or Attribute.NO_VARIANTS_EXPANSION
            it.category = Candidate.Category.OTHER
        }
        segment.insertCandidateCopy(0, candidate)
        return true
    }

    private fun evaluateIntegerExpression(text: String): Long? {
        val parts = text.split("+")
        if (parts.size < 2) {
            return null
        }
        var sum = 0L
        parts.forEach { part ->
            val value = part.toLongOrNull() ?: return null
            sum += value
        }
        return sum
    }
}
