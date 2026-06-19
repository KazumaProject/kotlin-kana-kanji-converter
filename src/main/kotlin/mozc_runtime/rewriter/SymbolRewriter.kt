package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.converter.charsLen
import mozc_runtime.data.SerializedDictionary
import mozc_runtime.data.SerializedDictionaryToken

// Ported from mozc/src/rewriter/symbol_rewriter.cc
// Ported from mozc/src/rewriter/symbol_rewriter.h
class SymbolRewriter(
    private val dictionary: SerializedDictionary,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useSymbolConversion) {
            return false
        }
        if (rewriteEntireCandidate(request, segments)) {
            return true
        }
        return rewriteEachCandidate(request, segments)
    }

    private fun rewriteEntireCandidate(request: RewriterRequest, segments: Segments): Boolean {
        if (segments.conversionSegmentsSize() != 1) {
            return false
        }
        val segment = segments.mutableConversionSegment(0)
        val tokens = dictionary.equalRange(segment.key())
        if (tokens.isEmpty()) {
            return false
        }
        insertCandidates(
            request = request,
            segment = segment,
            tokens = tokens,
            contextSensitive = false,
        )
        return true
    }

    private fun rewriteEachCandidate(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            val tokens = dictionary.equalRange(segment.key())
            if (tokens.isNotEmpty()) {
                insertCandidates(
                    request = request,
                    segment = segment,
                    tokens = tokens,
                    contextSensitive = !isSymbolKey(segment.key()),
                )
                updated = true
            }
        }
        return updated
    }

    private fun insertCandidates(
        request: RewriterRequest,
        segment: Segment,
        tokens: List<SerializedDictionaryToken>,
        contextSensitive: Boolean,
    ) {
        val base = segment.baseCandidate() ?: return
        expandSpace(segment)
        addDescriptionForCurrentCandidates(tokens, segment)
        val candidateKey = if (segment.key().isNotEmpty()) segment.key() else base.key
        var offset = if (candidateKey == "かおもじ") {
            segment.candidatesSize()
        } else {
            calculateInsertPosition(segment, getOffset(request, candidateKey))
        }
        while (offset < segment.candidatesSize()) {
            val value = segment.candidate(offset).value
            if (isSingleKanjiText(value) || isHiraganaText(value) || isKatakanaText(value)) {
                offset += 1
            } else {
                break
            }
        }
        val normalTokens = ArrayList<SerializedDictionaryToken>()
        val rareTokens = ArrayList<SerializedDictionaryToken>()
        var rareStarted = false
        tokens.forEach { token ->
            if (!rareStarted && isRareSymbolForDemotion(candidateKey, token)) {
                rareStarted = true
            }
            if (rareStarted) {
                rareTokens += token
            } else {
                normalTokens += token
            }
        }
        val firstPart = selectPromotedTokens(normalTokens, request.symbolRewriterPromotionSize)
        val secondStart = if (firstPart.size < normalTokens.size) firstPart.size - 1 else firstPart.size
        val secondPart = normalTokens.drop(secondStart.coerceAtLeast(0)) + rareTokens
        segment.insertCandidates(offset, firstPart.map { createCandidate(base, candidateKey, it, contextSensitive) })
        if (secondPart.isNotEmpty()) {
            segment.insertCandidates(segment.candidatesSize(), secondPart.map { createCandidate(base, candidateKey, it, contextSensitive) })
        }
    }

    private fun selectPromotedTokens(tokens: List<SerializedDictionaryToken>, promotionSize: Int): List<SerializedDictionaryToken> {
        if (tokens.size <= promotionSize) {
            return tokens
        }
        for (index in tokens.indices) {
            val insertedCount = index + 1
            val rest = tokens.size - insertedCount
            if (insertedCount < promotionSize || rest < 5) {
                continue
            }
            val next = tokens.getOrNull(index + 1)
            if (next != null &&
                tokens[index].description.isNotEmpty() &&
                tokens[index].description == next.description
            ) {
                continue
            }
            return tokens.take(insertedCount)
        }
        return tokens
    }

    private fun createCandidate(
        base: Candidate,
        key: String,
        token: SerializedDictionaryToken,
        contextSensitive: Boolean,
    ): Candidate =
        Candidate().also { candidate ->
            candidate.key = key
            candidate.contentKey = key
            candidate.value = token.value
            candidate.contentValue = token.value
            candidate.lid = token.lid
            candidate.rid = token.rid
            candidate.cost = base.cost
            candidate.structureCost = base.structureCost
            if (contextSensitive) {
                candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
            }
            if (candidate.value == "“”" || candidate.value == "‘’" || candidate.value == "w" || candidate.value == "www") {
                candidate.attributes = candidate.attributes or Attribute.NO_VARIANTS_EXPANSION
            }
            candidate.category = Candidate.Category.SYMBOL
            candidate.description = symbolDescription(token)
        }

    private fun addDescriptionForCurrentCandidates(tokens: List<SerializedDictionaryToken>, segment: Segment) {
        for (index in 0 until segment.candidatesSize()) {
            val candidate = segment.mutableCandidate(index)
            val full = asciiToFullWidth(candidate.value)
            val half = asciiToHalfWidth(candidate.value)
            val token = tokens.firstOrNull { it.value == candidate.value || it.value == full || it.value == half }
            if (token != null) {
                candidate.description = symbolDescription(token)
            }
        }
    }

    private fun expandSpace(segment: Segment) {
        for (index in 0 until segment.candidatesSize()) {
            val value = segment.candidate(index).value
            if (value == " " || value == "　") {
                val copy = segment.candidate(index).cloneCandidate()
                val newValue = if (value == " ") "　" else " "
                copy.value = newValue
                copy.contentValue = newValue
                copy.innerSegments.clear()
                segment.insertCandidateCopy(index + 1, copy)
                return
            }
        }
    }

    private fun getOffset(request: RewriterRequest, key: String): Int {
        val isSymbolKey = key.charsLen() == 1 && isSymbolKey(key)
        return if (request.mixedConversion && isSymbolKey) 1 else request.symbolRewriterCandidatePosition
    }

    private fun symbolDescription(token: SerializedDictionaryToken): String =
        when {
            token.description.isEmpty() -> ""
            token.additionalDescription.isEmpty() -> token.description
            else -> "${token.description}(${token.additionalDescription})"
        }

    private fun isRareSymbolForDemotion(key: String, token: SerializedDictionaryToken): Boolean {
        if ("ヒエログリフ" in token.description && key != "ひえろぐりふ") {
            return true
        }
        return listOf("変体仮名", "濁点付き仮名", "鼻濁音", "アイヌ語カナ").any { it in token.description }
    }
}

internal fun asciiToFullWidth(value: String): String =
    buildString {
        value.codePoints().forEachOrdered { codePoint ->
            appendCodePoint(if (codePoint in 0x21..0x7e) codePoint + 0xfee0 else codePoint)
        }
    }

internal fun asciiToHalfWidth(value: String): String =
    buildString {
        value.codePoints().forEachOrdered { codePoint ->
            appendCodePoint(if (codePoint in 0xff01..0xff5e) codePoint - 0xfee0 else codePoint)
        }
    }

internal fun isSymbolKey(key: String): Boolean =
    key.codePoints().allMatch { codePoint -> codePoint !in 0x3041..0x309f }

internal fun isHiraganaText(value: String): Boolean =
    value.isNotEmpty() && value.codePoints().allMatch { it in 0x3041..0x309f || it == 0x30fc }

internal fun isKatakanaText(value: String): Boolean =
    value.isNotEmpty() && value.codePoints().allMatch {
        it in 0x30a1..0x30ff || it in 0x31f0..0x31ff || it == 0x30fc
    }
