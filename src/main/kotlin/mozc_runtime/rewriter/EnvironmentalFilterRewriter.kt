package mozc_runtime.rewriter

import mozc_data.MozcDataManager
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Segments

// Ported from mozc/src/rewriter/environmental_filter_rewriter.cc
// Ported from mozc/src/rewriter/environmental_filter_rewriter.h
class EnvironmentalFilterRewriter(
    private val emojiDictionary: SerializedEmojiDictionary,
) : Rewriter {
    private val versionedEmojiValues = emojiDictionary.valuesByUnicodeVersion(Emoji12_1..Emoji17_0)

    override fun capability(request: RewriterRequest): Int = Capability.ALL

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        val filteredEmojiValues = versionedEmojiValues
            .filterKeys { version -> version !in request.additionalRenderableEmojiVersions }
            .values
            .flatten()
        segments.conversionSegments().forEach { segment ->
            for (index in segment.candidatesSize() - 1 downTo 0) {
                val candidate = segment.mutableCandidate(index)
                if (candidate.attributes and (Attribute.NO_MODIFICATION or Attribute.USER_DICTIONARY) != 0) {
                    continue
                }
                if (
                    candidate.value.any { Character.isISOControl(it) } ||
                    containsNonDefaultRenderableCodePoint(candidate.value) ||
                    filteredEmojiValues.any { emoji -> candidate.value.contains(emoji) }
                ) {
                    segment.eraseCandidate(index)
                    updated = true
                }
            }
        }
        return updated
    }

    companion object {
        fun fromMozcDataManager(dataManager: MozcDataManager): EnvironmentalFilterRewriter =
            EnvironmentalFilterRewriter(
                SerializedEmojiDictionary(dataManager.section("emoji_token"), dataManager.section("emoji_string")),
            )
    }
}

private const val Emoji12_1: Int = 9
private const val Emoji17_0: Int = 16

private fun containsNonDefaultRenderableCodePoint(value: String): Boolean =
    value.codePoints().anyMatch { codePoint ->
        codePoint in 0x1B000..0x1B122 ||
            codePoint in 0x13000..0x1342E ||
            codePoint in 0xE0100..0xE010E
    }
