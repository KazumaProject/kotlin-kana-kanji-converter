package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedDictionary
import mozc_runtime.data.SerializedDictionaryToken

// Ported from mozc/src/rewriter/emoticon_rewriter.cc
// Ported from mozc/src/rewriter/emoticon_rewriter.h
class EmoticonRewriter(
    private val dictionary: SerializedDictionary,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useEmoticonConversion) {
            return false
        }
        var updated = false
        segments.conversionSegments().forEach { segment ->
            val key = segment.key()
            if (key.isEmpty()) {
                return@forEach
            }
            val tokens = when (key) {
                "かお", "かおもじ" -> dictionary.toList()
                "ふくわらい" -> dictionary.toList().take(1)
                else -> dictionary.equalRange(key)
            }
            if (tokens.isNotEmpty()) {
                insertCandidates(tokens, segment, key == "ふくわらい")
                updated = true
            }
        }
        return updated
    }

    private fun insertCandidates(tokens: List<SerializedDictionaryToken>, segment: Segment, noLearning: Boolean) {
        val base = segment.baseCandidate() ?: return
        val sorted = tokens.sortedBy { it.cost }.distinctBy { it.value }
        val initialInsertPosition = when (segment.key()) {
            "かお", "かおもじ" -> calculateInsertPosition(segment, 100)
            "ふくわらい" -> calculateInsertPosition(segment, 4)
            else -> calculateInsertPosition(segment, 6)
        }
        val initialInsertSize = if (segment.key() == "ふくわらい") 1 else sorted.size
        var offset = initialInsertPosition.coerceAtMost(segment.candidatesSize())
        sorted.forEachIndexed { index, token ->
            val candidate = Candidate().also {
                it.key = base.key
                it.contentKey = base.contentKey
                it.value = token.value
                it.contentValue = token.value
                it.lid = token.lid
                it.rid = token.rid
                it.cost = base.cost
                it.attributes = it.attributes or
                    Attribute.NO_EXTRA_DESCRIPTION or
                    Attribute.NO_VARIANTS_EXPANSION or
                    Attribute.CONTEXT_SENSITIVE
                if (noLearning) {
                    it.attributes = it.attributes or Attribute.NO_LEARNING
                }
                it.description = if (token.description.isEmpty()) "顔文字" else "顔文字 ${token.description}"
                it.category = Candidate.Category.SYMBOL
            }
            if (index < initialInsertSize) {
                segment.insertCandidateCopy(offset, candidate)
                offset += 1
            } else {
                segment.appendCandidate(candidate)
            }
        }
    }
}
