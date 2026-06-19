package mozc_runtime.rewriter

import mozc_data.MozcDataManager
import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedStringArray
import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/usage_rewriter.cc
// Ported from mozc/src/rewriter/usage_rewriter.h
class UsageRewriter private constructor(
    private val dictionaryEnabled: Boolean,
    private val strings: SerializedStringArray?,
    private val dictionary: DictionaryInterface?,
    private val posMatcher: PosMatcher?,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (dictionaryEnabled) Capability.CONVERSION else Capability.NONE

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        val localStrings = strings ?: return false
        var updated = false
        segments.conversionSegments().forEach { segment ->
            for (index in 0 until segment.candidatesSize()) {
                val candidate = segment.mutableCandidate(index)
                if (candidate.usageId > 0 && candidate.usageTitle.isEmpty()) {
                    val stringIndex = candidate.usageId.coerceIn(0, localStrings.size() - 1)
                    candidate.usageTitle = localStrings[stringIndex]
                    updated = true
                } else if (candidate.usageId == 0 && candidate.usageTitle.isEmpty() && dictionary != null && posMatcher != null) {
                    val comment = dictionary.lookupComment(candidate.key, candidate.value)
                    if (!comment.isNullOrEmpty()) {
                        candidate.usageTitle = comment
                        updated = true
                    }
                }
            }
        }
        return updated
    }

    companion object {
        fun fromMozcDataManager(
            dataManager: MozcDataManager,
            dictionary: DictionaryInterface,
            posMatcher: PosMatcher,
        ): UsageRewriter =
            UsageRewriter(
                dictionaryEnabled = true,
                strings = SerializedStringArray.from(dataManager.section("usage_string_array")),
                dictionary = dictionary,
                posMatcher = posMatcher,
            )

        fun withoutDictionary(): UsageRewriter =
            UsageRewriter(false, null, null, null)
    }
}
