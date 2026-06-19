package mozc_runtime.rewriter

import mozc_data.MozcDataManager
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedStringArray
import mozc_runtime.dictionary.DictionaryInterface

// Ported from mozc/src/rewriter/correction_rewriter.cc
// Ported from mozc/src/rewriter/correction_rewriter.h
class CorrectionRewriter(
    private val valueArray: SerializedStringArray,
    private val errorArray: SerializedStringArray,
    private val correctionArray: SerializedStringArray,
    private val dictionary: DictionaryInterface,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            for (index in 0 until segment.candidatesSize()) {
                val candidate = segment.mutableCandidate(index)
                if (candidate.attributes and Attribute.SPELLING_CORRECTION != 0 && candidate.description.isEmpty()) {
                    val correction = correctionFor(candidate.key, candidate.value)
                    if (correction != null) {
                        candidate.description = "<もしかして: $correction>"
                        updated = true
                    }
                } else if (candidate.description.startsWith("<もしかして:") && dictionary.hasValue(candidate.value)) {
                    candidate.description = ""
                    updated = true
                }
            }
        }
        return updated
    }

    private fun correctionFor(key: String, value: String): String? {
        val size = minOf(valueArray.size(), minOf(errorArray.size(), correctionArray.size()))
        for (index in 0 until size) {
            if (valueArray[index] == value || errorArray[index] == key) {
                return correctionArray[index]
            }
        }
        return null
    }

    companion object {
        fun fromMozcDataManager(dataManager: MozcDataManager, dictionary: DictionaryInterface): CorrectionRewriter =
            CorrectionRewriter(
                SerializedStringArray.from(dataManager.section("reading_correction_value")),
                SerializedStringArray.from(dataManager.section("reading_correction_error")),
                SerializedStringArray.from(dataManager.section("reading_correction_correction")),
                dictionary,
            )
    }
}
