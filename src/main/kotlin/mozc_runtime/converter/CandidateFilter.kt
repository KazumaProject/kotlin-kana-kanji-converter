package mozc_runtime.converter

import mozc_runtime.dictionary.PosMatcher
import kotlin.math.max

// Ported from mozc/src/converter/candidate_filter.cc
// Ported from mozc/src/converter/candidate_filter.h
class CandidateFilter(
    private val posMatcher: PosMatcher,
    private val suggestionFilter: SuggestionFilter = SuggestionFilter.None,
    private val suppressedEntries: SuppressedEntries = SuppressedEntries.None,
) {
    enum class ResultType {
        GOOD_CANDIDATE,
        BAD_CANDIDATE,
        STOP_ENUMERATION,
    }

    fun interface SuggestionFilter {
        fun isBadSuggestion(text: String): Boolean

        companion object {
            val None = SuggestionFilter { false }
        }
    }

    interface SuppressedEntries {
        fun hasSuppressedEntries(): Boolean
        fun isSuppressedEntry(key: String, value: String): Boolean

        companion object {
            val None = object : SuppressedEntries {
                override fun hasSuppressedEntries(): Boolean = false
                override fun isSuppressedEntry(key: String, value: String): Boolean = false
            }
        }
    }

    private data class CandidateId(
        val value: String,
        val lid: Int,
        val rid: Int,
    ) {
        constructor(candidate: Candidate) : this(candidate.value, candidate.lid, candidate.rid)
    }

    private val seen = LinkedHashSet<CandidateId>()
    private var topCandidate: Candidate? = null
    private val hasSuppressedEntries = suppressedEntries.hasSuppressedEntries()

    fun reset() {
        seen.clear()
        topCandidate = null
    }

    fun filterCandidate(
        options: ConversionOptions,
        originalKey: String,
        candidate: Candidate,
        topNodes: List<Node>,
        nodes: List<Node>,
    ): ResultType {
        return if (options.requestType == RequestType.REVERSE_CONVERSION) {
            if (seen.add(CandidateId(candidate))) ResultType.GOOD_CANDIDATE else ResultType.BAD_CANDIDATE
        } else {
            val result = filterCandidateInternal(options, originalKey, candidate, topNodes, nodes)
            if (result == ResultType.GOOD_CANDIDATE) {
                seen += CandidateId(candidate)
            }
            result
        }
    }

    fun filterCandidates(
        options: ConversionOptions,
        originalKey: String,
        candidates: List<Candidate>,
    ): List<Candidate> {
        reset()
        val result = ArrayList<Candidate>()
        candidates.forEach { candidate ->
            val node = Node().also {
                it.key = candidate.key
                it.value = candidate.value
                it.lid = candidate.lid
                it.rid = candidate.rid
                it.wcost = candidate.wcost
                it.cost = candidate.cost
                it.nodeType = Node.NodeType.NOR_NODE
            }
            when (filterCandidate(options, originalKey, candidate, listOf(node), listOf(node))) {
                ResultType.GOOD_CANDIDATE -> result += candidate
                ResultType.BAD_CANDIDATE -> Unit
                ResultType.STOP_ENUMERATION -> return result
            }
        }
        return result
    }

    private fun checkRequestType(
        options: ConversionOptions,
        originalKey: String,
        candidate: Candidate,
        nodes: List<Node>,
    ): ResultType {
        when (options.requestType) {
            RequestType.PREDICTION -> {
                if (originalKey == candidate.key) {
                    return ResultType.GOOD_CANDIDATE
                }
                if (suggestionFilter.isBadSuggestion(candidate.value)) {
                    return ResultType.BAD_CANDIDATE
                }
                if (nodes.any { suggestionFilter.isBadSuggestion(it.value) }) {
                    return ResultType.BAD_CANDIDATE
                }
            }
            RequestType.SUGGESTION -> {
                if (suggestionFilter.isBadSuggestion(candidate.value)) {
                    return ResultType.BAD_CANDIDATE
                }
                if (nodes.any { suggestionFilter.isBadSuggestion(it.value) }) {
                    return ResultType.BAD_CANDIDATE
                }
            }
            else -> Unit
        }
        return ResultType.GOOD_CANDIDATE
    }

    private fun filterCandidateInternal(
        options: ConversionOptions,
        originalKey: String,
        candidate: Candidate,
        topNodes: List<Node>,
        nodes: List<Node>,
    ): ResultType {
        val requestResult = checkRequestType(options, originalKey, candidate, nodes)
        if (requestResult != ResultType.GOOD_CANDIDATE) {
            return requestResult
        }

        if (candidate.attributes and Attribute.CONTEXT_SENSITIVE != 0) {
            return ResultType.GOOD_CANDIDATE
        }

        if (options.createPartialCandidates && isNoisyNumberCandidate(nodes)) {
            return ResultType.BAD_CANDIDATE
        }

        val candidateSize = seen.size
        if (topCandidate == null || candidateSize == 0) {
            topCandidate = candidate
        }
        val top = topCandidate ?: candidate

        if (nodes.size > 1 && containsIsolatedWordOrGeneralSymbol(nodes)) {
            return ResultType.BAD_CANDIDATE
        }
        if (nodes.isNotEmpty() &&
            isIsolatedWordOrGeneralSymbol(nodes[0].lid) &&
            (isNormalOrConstrainedNode(nodes[0].prev) || isNormalOrConstrainedNode(nodes[0].next))
        ) {
            return ResultType.BAD_CANDIDATE
        }

        if (hasSuppressedEntries &&
            (
                suppressedEntries.isSuppressedEntry(candidate.key, candidate.value) ||
                    (
                        candidate.key != candidate.contentKey &&
                            candidate.value != candidate.contentValue &&
                            suppressedEntries.isSuppressedEntry(candidate.contentKey, candidate.contentValue)
                    )
                )
        ) {
            return ResultType.BAD_CANDIDATE
        }

        if (candidate.attributes and Attribute.USER_DICTIONARY != 0) {
            return ResultType.GOOD_CANDIDATE
        }

        if (candidateSize + 1 >= MaxCandidatesSize) {
            return ResultType.STOP_ENUMERATION
        }
        if (CandidateId(candidate) in seen) {
            return ResultType.BAD_CANDIDATE
        }

        if (nodes.isEmpty()) {
            return ResultType.BAD_CANDIDATE
        }

        if (getScriptType(nodes[0].value) != ScriptType.HIRAGANA) {
            if (nodes.size >= 2) {
                if (posMatcher.isKagyoTaConnectionVerb(nodes[0].rid) &&
                    posMatcher.isVerbSuffix(nodes[1].lid) &&
                    !posMatcher.isTeSuffix(nodes[1].lid)
                ) {
                    return ResultType.BAD_CANDIDATE
                }
                if (posMatcher.isWagyoRenyoConnectionVerb(nodes[0].rid) &&
                    posMatcher.isTeSuffix(nodes[1].lid)
                ) {
                    return ResultType.BAD_CANDIDATE
                }
            }
            if (nodes[0].lid != nodes[0].rid) {
                if (posMatcher.isKagyoTaConnectionVerb(nodes[0].lid) &&
                    posMatcher.isVerbSuffix(nodes[0].rid) &&
                    !posMatcher.isTeSuffix(nodes[0].rid)
                ) {
                    return ResultType.BAD_CANDIDATE
                }
                if (posMatcher.isWagyoRenyoConnectionVerb(nodes[0].lid) &&
                    posMatcher.isTeSuffix(nodes[0].rid)
                ) {
                    return ResultType.BAD_CANDIDATE
                }
            }
        }

        if (nodes.size == 1) {
            return ResultType.GOOD_CANDIDATE
        }
        if (candidate.value.charsLen() == 1) {
            return ResultType.GOOD_CANDIDATE
        }

        val noisyWeakCompound = isNoisyWeakCompound(nodes)
        val connectedWeakCompound = isConnectedWeakCompound(nodes)
        if (noisyWeakCompound && candidateSize >= 1) {
            return ResultType.BAD_CANDIDATE
        }
        if (connectedWeakCompound && candidateSize >= SizeThresholdForWeakCompound) {
            return ResultType.BAD_CANDIDATE
        }

        if (!noisyWeakCompound &&
            top.structureCost == 0 &&
            candidate.lid == top.lid &&
            candidate.rid == top.rid
        ) {
            return ResultType.GOOD_CANDIDATE
        }

        val topNonContentValue = top.value.drop(top.contentValue.length.coerceAtMost(top.value.length))
        val nonContentValue = candidate.value.drop(candidate.contentValue.length.coerceAtMost(candidate.value.length))
        if (!noisyWeakCompound &&
            top !== candidate &&
            top.contentValue != top.value &&
            getScriptType(topNonContentValue) == ScriptType.HIRAGANA &&
            topNonContentValue == nonContentValue
        ) {
            return ResultType.GOOD_CANDIDATE
        }

        if (candidate.attributes and Attribute.REALTIME_CONVERSION == 0) {
            val topEnglishT13n = getScriptType(nodes[0].key) == ScriptType.HIRAGANA &&
                isEnglishTransliteration(nodes[0].value)
            for (index in 1 until nodes.size) {
                if (getScriptType(nodes[index].key) == ScriptType.HIRAGANA &&
                    isEnglishTransliteration(nodes[index].value)
                ) {
                    return ResultType.BAD_CANDIDATE
                }
                if (topEnglishT13n && !posMatcher.isFunctional(nodes[index].lid)) {
                    return ResultType.BAD_CANDIDATE
                }
            }
        }

        val topCost = max(MinCost, top.cost)
        val topStructureCost = max(MinCost, top.structureCost)
        if (isCompoundCandidate(topNodes) &&
            candidateSize < 3 &&
            candidate.cost < topCost + 2302 &&
            candidate.structureCost < 6907
        ) {
            return ResultType.GOOD_CANDIDATE
        }

        val costOffset = if (candidate.lid == posMatcher.getLastNameId() ||
            candidate.lid == posMatcher.getFirstNameId()
        ) {
            Int.MAX_VALUE - topCost
        } else {
            CostOffset
        }

        if (topCost + costOffset < candidate.cost &&
            topStructureCost + MinStructureCostOffset < candidate.structureCost
        ) {
            return if (candidateSize < StopEnumerationCacheSize) {
                ResultType.BAD_CANDIDATE
            } else {
                ResultType.STOP_ENUMERATION
            }
        }

        if (topStructureCost + StructureCostOffset > Int.MAX_VALUE ||
            max(topStructureCost, MinStructureCostOffset) + StructureCostOffset < candidate.structureCost
        ) {
            return ResultType.BAD_CANDIDATE
        }

        if (hasMultipleNumberNodes(nodes)) {
            return ResultType.BAD_CANDIDATE
        }

        return ResultType.GOOD_CANDIDATE
    }

    private fun isNoisyWeakCompound(nodes: List<Node>): Boolean {
        if (nodes.size <= 1) {
            return false
        }
        if (nodes[0].lid != nodes[0].rid) {
            return false
        }
        if (posMatcher.isWeakCompoundFillerPrefix(nodes[0].lid)) {
            return true
        }
        if (nodes[1].lid != nodes[1].rid) {
            val possibleAntiPhraseConnection = posMatcher.isContentNoun(nodes[0].rid) &&
                posMatcher.isAcceptableParticleAtBeginOfSegment(nodes[1].lid)
            if (!possibleAntiPhraseConnection) {
                return true
            }
        }
        if (posMatcher.isWeakCompoundNounPrefix(nodes[0].lid) &&
            !posMatcher.isWeakCompoundNounSuffix(nodes[1].lid)
        ) {
            return true
        }
        if (posMatcher.isWeakCompoundVerbPrefix(nodes[0].lid) &&
            !posMatcher.isWeakCompoundVerbSuffix(nodes[1].lid)
        ) {
            return true
        }
        return false
    }

    private fun isConnectedWeakCompound(nodes: List<Node>): Boolean {
        if (nodes.size <= 1) {
            return false
        }
        if (nodes[0].lid != nodes[0].rid || nodes[1].lid != nodes[1].rid) {
            return false
        }
        if (posMatcher.isWeakCompoundNounPrefix(nodes[0].lid) &&
            posMatcher.isWeakCompoundNounSuffix(nodes[1].lid)
        ) {
            return true
        }
        if (posMatcher.isWeakCompoundVerbPrefix(nodes[0].lid) &&
            posMatcher.isWeakCompoundVerbSuffix(nodes[1].lid)
        ) {
            return true
        }
        return false
    }

    private fun isNoisyNumberCandidate(nodes: List<Node>): Boolean {
        fun isConvertedNumber(node: Node): Boolean {
            if (node.lid != node.rid) {
                return false
            }
            if (!isScriptType(node.key, ScriptType.HIRAGANA)) {
                return false
            }
            return posMatcher.isNumber(node.lid) || posMatcher.isKanjiNumber(node.rid)
        }

        nodes.forEachIndexed { index, node ->
            if (!isConvertedNumber(node)) {
                return@forEachIndexed
            }
            if (index + 1 < nodes.size &&
                !isConvertedNumber(nodes[index + 1]) &&
                !posMatcher.isCounterSuffixWord(nodes[index + 1].lid)
            ) {
                return true
            }
            if (index - 1 >= 0 && posMatcher.isUniqueNoun(nodes[index - 1].rid)) {
                return true
            }
        }
        return false
    }

    private fun hasMultipleNumberNodes(nodes: List<Node>): Boolean {
        if (nodes.size < 2) {
            return false
        }
        var numberNodes = 0
        var previousLid = 0
        nodes.forEach { node ->
            if (isScriptType(node.key, ScriptType.NUMBER)) {
                return@forEach
            }
            val first = node.value.utf8Chars().firstOrNull() ?: return@forEach
            val firstScriptType = getScriptType(first.codePoint)
            if (firstScriptType == ScriptType.NUMBER && previousLid != node.lid) {
                numberNodes += 1
            } else if (firstScriptType == ScriptType.KANJI) {
                val firstKanji = first.text
                val converted = kanjiNumberToArabicNumber(firstKanji)
                if (firstKanji != converted && previousLid != node.lid) {
                    numberNodes += 1
                }
            }
            previousLid = node.lid
        }
        return numberNodes >= 2
    }

    private fun containsIsolatedWordOrGeneralSymbol(nodes: List<Node>): Boolean =
        nodes.any { isIsolatedWordOrGeneralSymbol(it.lid) }

    private fun isIsolatedWordOrGeneralSymbol(posId: Int): Boolean =
        posMatcher.isIsolatedWord(posId) || posMatcher.isGeneralSymbol(posId)

    private fun isNormalOrConstrainedNode(node: Node?): Boolean =
        node != null && (node.nodeType == Node.NodeType.NOR_NODE || node.nodeType == Node.NodeType.CON_NODE)

    private fun isCompoundCandidate(nodes: List<Node>): Boolean =
        nodes.size == 1 && nodes[0].lid != nodes[0].rid

    private fun isEnglishTransliteration(value: String): Boolean =
        value.isNotEmpty() && value.all {
            it == ' ' || it == '!' || it == '\'' || it == '-' ||
                it in 'A'..'Z' || it in 'a'..'z'
        }

    private fun kanjiNumberToArabicNumber(value: String): String =
        buildString {
            value.codePoints().forEachOrdered { codePoint ->
                append(
                    when (codePoint) {
                        0x3007, 0x96f6 -> '0'
                        0x4e00, 0x58f1 -> '1'
                        0x4e8c, 0x5f10 -> '2'
                        0x4e09, 0x53c2 -> '3'
                        0x56db -> '4'
                        0x4e94 -> '5'
                        0x516d -> '6'
                        0x4e03 -> '7'
                        0x516b -> '8'
                        0x4e5d -> '9'
                        0x5341, 0x62fe -> "10"
                        0x767e -> "100"
                        0x5343, 0x9621 -> "1000"
                        0x4e07 -> "10000"
                        0x5104 -> "100000000"
                        0x5146 -> "1000000000000"
                        0x4eac -> "10000000000000000"
                        else -> String(Character.toChars(codePoint))
                    },
                )
            }
        }

    private companion object {
        const val SizeThresholdForWeakCompound: Int = 10
        const val MaxCandidatesSize: Int = 200
        const val MinCost: Int = 100
        const val CostOffset: Int = 6907
        const val StructureCostOffset: Int = 3453
        const val MinStructureCostOffset: Int = 1151
        const val StopEnumerationCacheSize: Int = 30
    }
}
