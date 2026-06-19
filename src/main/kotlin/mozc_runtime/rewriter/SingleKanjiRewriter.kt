package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedDictionaryToken
import mozc_runtime.data.SerializedSingleKanjiDictionary
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/rewriter/single_kanji_rewriter.cc
// Ported from mozc/src/rewriter/single_kanji_rewriter.h
class SingleKanjiRewriter(
    private val posMatcher: PosMatcher,
    private val dictionary: SerializedSingleKanjiDictionary,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useSingleKanjiConversion) {
            return false
        }
        var updated = false
        val conversionSegments = segments.conversionSegments()
        val singleSegment = conversionSegments.size == 1
        conversionSegments.forEach { segment ->
            addDescriptionForExistingCandidates(segment)
            if (request.mixedConversion && request.requestType != mozc_runtime.converter.RequestType.CONVERSION) {
                return@forEach
            }
            val kanjiList = dictionary.lookupKanjiEntries(segment.key())
            if (kanjiList.isNotEmpty()) {
                insertCandidates(singleSegment, posMatcher.getGeneralSymbolId(), kanjiList, segment)
                updated = true
            }
        }
        conversionSegments.forEachIndexed { index, segment ->
            if (segment.candidatesSize() == 0) {
                return@forEachIndexed
            }
            if (index + 1 < conversionSegments.size) {
                val right = conversionSegments[index + 1].candidate(0)
                if (!posMatcher.isContentNoun(right.lid)) {
                    return@forEachIndexed
                }
            } else if (conversionSegments.size != 1) {
                return@forEachIndexed
            }
            val tokens = dictionary.lookupNounPrefixEntries(segment.key())
            if (tokens.isNotEmpty()) {
                insertNounPrefix(tokens, segment)
                updated = true
            }
        }
        return updated
    }

    private fun addDescriptionForExistingCandidates(segment: Segment) {
        for (index in 0 until segment.candidatesSize()) {
            val candidate = segment.mutableCandidate(index)
            if (candidate.description.isEmpty()) {
                val description = dictionary.generateDescription(candidate.value)
                if (description != null) {
                    candidate.description = description
                }
            }
        }
    }

    private fun insertCandidates(
        singleSegment: Boolean,
        singleKanjiId: Int,
        kanjiList: List<String>,
        segment: Segment,
    ) {
        val key = if (segment.key().isNotEmpty()) segment.key() else segment.candidate(0).key
        kanjiList.forEachIndexed { index, value ->
            segment.addCandidate().also { candidate ->
                fillCandidate(key, value, OffsetCost + index, singleKanjiId, candidate)
                if (!singleSegment) {
                    candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
                }
            }
        }
    }

    private fun fillCandidate(key: String, value: String, cost: Int, singleKanjiId: Int, candidate: Candidate) {
        candidate.setKeyValue(key, value)
        candidate.lid = singleKanjiId
        candidate.rid = singleKanjiId
        candidate.cost = cost
        candidate.attributes = candidate.attributes or
            Attribute.CONTEXT_SENSITIVE or
            Attribute.NO_VARIANTS_EXPANSION
        val description = dictionary.generateDescription(value)
        if (description != null) {
            candidate.description = description
        }
    }

    private fun insertNounPrefix(tokens: List<SerializedDictionaryToken>, segment: Segment) {
        val key = if (segment.key().isNotEmpty()) segment.key() else segment.candidate(0).key
        tokens.forEach { token ->
            val baseOffset = token.cost + if (segment.candidate(0).attributes and Attribute.CONTEXT_SENSITIVE != 0) 1 else 0
            val insertPosition = calculateInsertPosition(segment, baseOffset)
            segment.insertCandidate(insertPosition).also { candidate ->
                candidate.setKeyValue(key, token.value)
                candidate.lid = posMatcher.getNounPrefixId()
                candidate.rid = posMatcher.getNounPrefixId()
                candidate.cost = 5000
                candidate.attributes = candidate.attributes or
                    Attribute.CONTEXT_SENSITIVE or
                    Attribute.NO_VARIANTS_EXPANSION
            }
        }
    }

    companion object {
        private const val OffsetCost: Int = 8000
    }
}
