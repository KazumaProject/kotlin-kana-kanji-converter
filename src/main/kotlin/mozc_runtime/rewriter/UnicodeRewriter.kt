package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/unicode_rewriter.cc
// Ported from mozc/src/rewriter/unicode_rewriter.h
class UnicodeRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1) {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val code = parseUnicodeKey(segment.key()) ?: return false
        val value = runCatching { String(Character.toChars(code)) }.getOrNull() ?: return false
        val base = segment.baseCandidate()
        val candidate = Candidate().also {
            it.setKeyValue(segment.key(), value)
            it.lid = base?.lid ?: 0
            it.rid = base?.rid ?: 0
            it.cost = base?.cost ?: 0
            it.description = "Unicode 変換 (${segment.key()})"
            it.attributes = it.attributes or Attribute.NO_VARIANTS_EXPANSION
            it.category = Candidate.Category.SYMBOL
        }
        segment.insertCandidateCopy(0, candidate)
        return true
    }

    private fun parseUnicodeKey(key: String): Int? {
        val normalized = key.removePrefix("U+").removePrefix("u+")
        if (normalized.length !in 4..6 || normalized.any { it !in '0'..'9' && it !in 'a'..'f' && it !in 'A'..'F' }) {
            return null
        }
        return normalized.toIntOrNull(16)
    }
}
