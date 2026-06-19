package mozc_runtime.rewriter

import mozc_data.MozcDataManager
import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedDictionary

// Ported from mozc/src/rewriter/a11y_description_rewriter.cc
// Ported from mozc/src/rewriter/a11y_description_rewriter.h
class A11yDescriptionRewriter(
    private val descriptionDictionary: SerializedDictionary,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.enableA11yDescription) Capability.ALL else Capability.NONE

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            for (index in 0 until segment.candidatesSize()) {
                val candidate = segment.mutableCandidate(index)
                val description = a11yDescription(candidate.value)
                if (description != candidate.a11yDescription) {
                    candidate.a11yDescription = description
                    updated = true
                }
            }
        }
        return updated
    }

    private fun a11yDescription(value: String): String {
        val builder = StringBuilder(value)
        value.codePoints().forEachOrdered { codePoint ->
            val text = String(Character.toChars(codePoint))
            val token = descriptionDictionary.equalRange(text).firstOrNull()
            if (token != null) {
                builder.append("。").append(token.value)
            }
        }
        return builder.toString()
    }

    companion object {
        fun fromMozcDataManager(dataManager: MozcDataManager): A11yDescriptionRewriter =
            A11yDescriptionRewriter(
                SerializedDictionary(
                    dataManager.section("a11y_description_token"),
                    dataManager.section("a11y_description_string"),
                ),
            )
    }
}
