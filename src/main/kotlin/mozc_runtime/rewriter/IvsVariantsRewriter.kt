package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/ivs_variants_rewriter.cc
// Ported from mozc/src/rewriter/ivs_variants_rewriter.h
class IvsVariantsRewriter : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            for (index in 0 until segment.candidatesSize()) {
                val candidate = segment.mutableCandidate(index)
                if (candidate.value.codePoints().anyMatch { it in 0xe0100..0xe01ef }) {
                    candidate.attributes = candidate.attributes or Attribute.NO_VARIANTS_EXPANSION
                    if (candidate.description.isEmpty()) {
                        candidate.description = "環境依存(IVS)"
                    }
                    updated = true
                }
            }
        }
        return updated
    }
}
