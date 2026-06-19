package mozc_runtime.prediction

import kotlin.math.abs
import kotlin.math.ln
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Connector
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segmenter
import mozc_runtime.converter.charsLen
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/prediction/dictionary_predictor.h
// Ported from mozc/src/prediction/dictionary_predictor.cc
class DictionaryPredictor(
    private val aggregator: DictionaryPredictionAggregator,
    private val realtimeDecoder: RealtimeDecoder,
    private val connector: Connector,
    private val segmenter: Segmenter,
    private val posMatcher: PosMatcher,
    private val suggestionFilter: SuggestionFilter,
) {
    fun predict(request: PredictionRequest): List<Result> {
        if (request.requestType == RequestType.CONVERSION) {
            return listOf()
        }
        val results = if (request.mixedConversion) {
            aggregator.aggregateResultsForMixedConversion(request)
        } else {
            aggregator.aggregateResultsForDesktop(request)
        }.toMutableList()
        rewriteResultsForPrediction(request, results)
        return rerankAndFilterResults(request, results)
    }

    private fun rewriteResultsForPrediction(request: PredictionRequest, results: MutableList<Result>) {
        if (request.mixedConversion) {
            setPredictionCostForMixedConversion(request, results)
        } else {
            setPredictionCost(request, results)
        }
        maybeFixRealtimeTopCost(request, results)
        if (!request.mixedConversion) {
            removeMisspelledCandidates(request, results)
        }
    }

    private fun rerankAndFilterResults(request: PredictionRequest, results: MutableList<Result>): List<Result> {
        val maxCandidates = minOf(request.maxDictionaryPredictionCandidatesSize, results.size)
        val filter = ResultFilter(request, posMatcher, connector, suggestionFilter)
        val finalResults = ArrayList<Result>()
        val mergedTypes = LinkedHashMap<String, Int>()
        results.forEach { result ->
            if (!result.removed) {
                mergedTypes[result.value] = (mergedTypes[result.value] ?: 0) or result.attributes
            }
        }
        results.sortedWith(ResultOrdering.costComparator()).forEach { result ->
            if (finalResults.size >= maxCandidates || result.cost >= Result.InvalidCost) {
                return@forEach
            }
            if (filter.shouldRemove(result, finalResults.size)) {
                return@forEach
            }
            if (result.attributes and Attribute.PARTIALLY_KEY_CONSUMED != 0 && request.autoPartialSuggestion) {
                result.attributes = result.attributes or Attribute.AUTO_PARTIAL_SUGGESTION
            }
            if (result.attributes and Attribute.SUFFIX_DICTIONARY != 0) {
                result.attributes = result.attributes or Attribute.NO_VARIANTS_EXPANSION or Attribute.NO_EXTRA_DESCRIPTION
            }
            val debugDescription = PredictionTypes.debugString(mergedTypes[result.value] ?: 0)
            if (debugDescription.isNotEmpty()) {
                result.description = appendDescription(result.description, debugDescription)
            }
            finalResults += result
        }
        return finalResults
    }

    private fun appendDescription(description: String, value: String): String =
        if (description.isEmpty()) value else "$description $value"

    private fun getLMCost(result: Result, rid: Int): Int {
        val costWithContext = connector.cost(rid, result.lid)
        val lmCost = if (result.attributes and Attribute.SUFFIX_DICTIONARY != 0) {
            costWithContext + result.wcost
        } else {
            val costWithoutContext = connector.cost(0, result.lid)
            minOf(costWithContext, costWithoutContext) + result.wcost
        }
        return if (result.attributes and Attribute.REALTIME_CONVERSION == 0) {
            lmCost + segmenter.getSuffixPenalty(result.rid)
        } else {
            lmCost
        }
    }

    private fun setPredictionCost(request: PredictionRequest, results: MutableList<Result>) {
        val historyRid = request.historyRid
        val isSuggestion = request.requestType == RequestType.SUGGESTION
        val historyKeyLength = request.historyKey.charsLen()
        val requestKeyLength = request.key.charsLen()
        results.forEach { result ->
            val lmCost = getLMCost(result, historyRid)
            var queryLength = requestKeyLength
            var keyLength = result.key.charsLen()
            if (result.attributes and Attribute.BIGRAM != 0) {
                queryLength += historyKeyLength
                keyLength += historyKeyLength
            }
            if (isAggressiveSuggestion(queryLength, keyLength, lmCost, isSuggestion, results.size)) {
                result.cost = Result.InvalidCost
            } else {
                result.cost = lmCost - (CostFactor * ln(1.0 + maxOf(0, keyLength - queryLength))).toInt()
            }
        }
    }

    private fun setPredictionCostForMixedConversion(request: PredictionRequest, results: MutableList<Result>) {
        val historyRid = request.historyRid
        var previousCost = request.historyCost
        if (previousCost == 0) previousCost = 5000
        val singleKanjiOffset = calculateSingleKanjiCostOffset(historyRid, results)
        results.forEach { result ->
            var cost = getLMCost(result, historyRid)
            if (result.lid == result.rid &&
                !posMatcher.isSuffixWord(result.rid) &&
                !posMatcher.isFunctional(result.rid) &&
                !posMatcher.isWeakCompoundVerbSuffix(result.rid)
            ) {
                cost -= segmenter.getSuffixPenalty(result.rid)
            }
            if (suggestionFilter.isBadSuggestion(result.value)) {
                cost += BadSuggestionPenalty
            }
            if (result.attributes and Attribute.BIGRAM != 0) {
                cost += DefaultTransitionCost - BigramBonus - previousCost
                cost = maxOf(1, cost)
            }
            if (result.attributes and Attribute.SINGLE_KANJI != 0) {
                cost += singleKanjiOffset
                if (cost <= 0) cost = result.wcost + 1
            }
            if (result.attributes and Attribute.USER_DICTIONARY != 0 && result.lid != posMatcher.getGeneralSymbolId()) {
                cost = minOf(cost - UserDictionaryPromotionFactor, UserDictionaryCostUpperLimit)
            }
            if (result.attributes and Attribute.SUFFIX_DICTIONARY == 0 &&
                result.key.charsLen() > request.key.charsLen()
            ) {
                val predictedKeyLength = result.key.charsLen() - request.key.charsLen()
                cost += (CostFactor * ln((50 * predictedKeyLength).toDouble())).toInt()
            }
            if (result.attributes and Attribute.PARTIALLY_KEY_CONSUMED != 0) {
                val penalty = calculatePrefixPenalty(request, result)
                result.penalty += penalty
                cost += penalty
            }
            result.cost = maxOf(1, cost)
        }
    }

    private fun calculateSingleKanjiCostOffset(historyRid: Int, results: List<Result>): Int {
        val minCostByValue = LinkedHashMap<String, Int>()
        var fallbackCost = -1
        results.forEach { result ->
            if (result.removed) return@forEach
            if (result.attributes and (Attribute.REALTIME_CONVERSION or Attribute.UNIGRAM or Attribute.PARTIALLY_KEY_CONSUMED or Attribute.NUMBER) == 0) {
                return@forEach
            }
            val lmCost = getLMCost(result, historyRid)
            if (result.value == result.key) {
                fallbackCost = if (fallbackCost == -1) lmCost else minOf(fallbackCost, lmCost)
            }
            if (result.attributes and (Attribute.REALTIME_CONVERSION or Attribute.UNIGRAM) != 0 &&
                result.value.charsLen() != 1
            ) {
                return@forEach
            }
            minCostByValue[result.value] = minOf(minCostByValue[result.value] ?: lmCost, lmCost)
        }
        val singleKanjiMaxCost = maxOf(minCostByValue.values.maxOrNull() ?: 0, fallbackCost)
        val transitionCost = minOf(
            connector.cost(historyRid, posMatcher.getGeneralSymbolId()),
            connector.cost(0, posMatcher.getGeneralSymbolId()),
        )
        return maxOf(0, singleKanjiMaxCost - transitionCost) + SingleKanjiPredictionCostOffset
    }

    private fun calculatePrefixPenalty(request: PredictionRequest, result: Result): Int {
        if (request.key == result.key || request.key.toByteArray(Charsets.UTF_8).size <= result.key.toByteArray(Charsets.UTF_8).size) {
            return 0
        }
        val suffix = request.key.substring(result.key.length)
        val suffixResult = realtimeDecoder.decodeSuffix(suffix, result.rid)
        return (suffixResult?.cost ?: Result.InvalidCost) + PartialCandidateCostPenalty
    }

    private fun maybeFixRealtimeTopCost(request: PredictionRequest, results: MutableList<Result>) {
        var realtimeCostMin = Result.InvalidCost
        var realtimeTop: Result? = null
        results.forEach { result ->
            if (result.attributes and Attribute.REALTIME_TOP != 0) {
                realtimeTop = result
            }
            if (result.attributes and Attribute.REALTIME_CONVERSION != 0 &&
                result.cost < realtimeCostMin &&
                result.key.toByteArray(Charsets.UTF_8).size == request.key.toByteArray(Charsets.UTF_8).size
            ) {
                realtimeCostMin = result.cost
            }
        }
        val top = realtimeTop
        if (top != null && realtimeCostMin != Result.InvalidCost) {
            top.cost = maxOf(0, realtimeCostMin - 10)
        }
    }

    private fun removeMisspelledCandidates(request: PredictionRequest, results: MutableList<Result>) {
        if (results.size <= 1) return
        val requestKeyLength = request.key.charsLen()
        var spellingCorrectionSize = 5
        results.indices.forEach { index ->
            val result = results[index]
            if (result.attributes and Attribute.SPELLING_CORRECTION == 0) return@forEach
            spellingCorrectionSize -= 1
            if (spellingCorrectionSize == 0) return
            val sameKey = ArrayList<Int>()
            val sameValue = ArrayList<Int>()
            results.indices.forEach { targetIndex ->
                if (index == targetIndex) return@forEach
                val target = results[targetIndex]
                if (target.attributes and Attribute.SPELLING_CORRECTION != 0) return@forEach
                if (target.key == result.key) sameKey += targetIndex
                if (target.value == result.value) sameValue += targetIndex
            }
            if (sameKey.isNotEmpty() && sameValue.isNotEmpty()) {
                results[index].removed = true
                sameKey.forEach { results[it].removed = true }
            } else if (sameKey.isEmpty() && sameValue.isNotEmpty()) {
                results[index].removed = true
            } else if (sameKey.isNotEmpty()) {
                sameKey.forEach { results[it].removed = true }
                if (requestKeyLength <= misspelledPosition(result.key, result.value)) {
                    results[index].removed = true
                }
            }
        }
    }

    private fun misspelledPosition(key: String, value: String): Int {
        val hiraganaValue = katakanaToHiragana(value)
        if (hiraganaValue.codePoints().anyMatch { it !in 0x3040..0x309F }) {
            return key.charsLen()
        }
        val keyPoints = key.codePoints().toArray()
        val valuePoints = hiraganaValue.codePoints().toArray()
        val min = minOf(keyPoints.size, valuePoints.size)
        for (index in 0 until min) {
            if (keyPoints[index] != valuePoints[index]) return index
        }
        return keyPoints.size
    }

    private fun katakanaToHiragana(value: String): String =
        buildString {
            value.codePoints().forEachOrdered { codePoint ->
                appendCodePoint(if (codePoint in 0x30A1..0x30F6) codePoint - 0x60 else codePoint)
            }
        }

    private fun isAggressiveSuggestion(
        queryLength: Int,
        keyLength: Int,
        cost: Int,
        isSuggestion: Boolean,
        totalCandidatesSize: Int,
    ): Boolean =
        isSuggestion && totalCandidatesSize >= 10 && keyLength >= 8 && cost >= 5000 &&
            queryLength <= (0.4 * keyLength).toInt()

    companion object {
        private const val CostFactor: Int = 500
        private const val BadSuggestionPenalty: Int = 3453
        private const val DefaultTransitionCost: Int = 1347
        private const val BigramBonus: Int = 800
        private const val UserDictionaryPromotionFactor: Int = 804
        private const val UserDictionaryCostUpperLimit: Int = 1000
        private const val SingleKanjiPredictionCostOffset: Int = 800
        private const val PartialCandidateCostPenalty: Int = 5000
    }
}
