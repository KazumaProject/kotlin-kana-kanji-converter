package mozc_runtime.prediction

import mozc_runtime.converter.RequestType
import mozc_runtime.converter.charsLen
import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.Token

// Ported from mozc/src/prediction/dictionary_prediction_aggregator.h
// Ported from mozc/src/prediction/dictionary_prediction_aggregator.cc
class DictionaryPredictionAggregator(
    private val dictionary: DictionaryInterface,
    private val suffixDictionary: DictionaryInterface,
    private val posMatcher: PosMatcher,
    private val realtimeDecoder: RealtimeDecoder,
    private val numberDecoder: NumberDecoder,
    private val singleKanjiDecoder: SingleKanjiDecoder,
    private val zeroQueryDict: ZeroQueryDict,
    private val zeroQueryNumberDict: ZeroQueryDict,
) {
    fun aggregateResultsForDesktop(request: PredictionRequest): List<Result> {
        val results = ArrayList<Result>()
        if (request.requestType == RequestType.SUGGESTION && (!request.useDictionarySuggest || isZipCodeRequest(request.key))) {
            return results
        }
        if (shouldAggregateRealtimeConversionResults(request)) {
            results += aggregateRealtime(request, getRealtimeCandidateMaxSize(request))
        }
        if (request.requestType == RequestType.PARTIAL_SUGGESTION || request.requestType == RequestType.PARTIAL_PREDICTION) {
            return results
        }
        aggregateUnigram(request, results)
        if (isNotExceedingCutoffThreshold(request, results)) {
            results += numberDecoder.decodeResults(request.key)
        }
        return results
    }

    fun aggregateResultsForMixedConversion(request: PredictionRequest): List<Result> {
        val results = ArrayList<Result>()
        if (request.isZeroQuerySuggestion()) {
            if (request.zeroQuerySuggestion) {
                results += aggregateZeroQuery(request)
            }
            return results
        }
        if (request.requestType == RequestType.SUGGESTION && (!request.useDictionarySuggest || isZipCodeRequest(request.key))) {
            return results
        }
        results += aggregateRealtime(request, getRealtimeCandidateMaxSize(request))
        if (request.requestType == RequestType.PARTIAL_SUGGESTION || request.requestType == RequestType.PARTIAL_PREDICTION) {
            return results
        }
        aggregateUnigram(request, results)
        if (isNotExceedingCutoffThreshold(request, results)) {
            results += numberDecoder.decodeResults(request.key)
        }
        if (request.autoPartialSuggestion && isNotExceedingCutoffThreshold(request, results)) {
            aggregatePrefix(request, results)
        }
        results += singleKanjiDecoder.decode(request.key, request.autoPartialSuggestion)
        return results
    }

    fun aggregateZeroQuery(request: PredictionRequest): List<Result> {
        val historyValue = request.historyValue.ifEmpty { request.precedingText }
        val historyKey = request.historyKey.ifEmpty { historyValue }
        if (historyValue.isEmpty() || historyKey.isEmpty()) {
            return listOf()
        }
        val results = ArrayList<Result>()
        val numberKey = normalizedArabicNumber(historyValue)
        if (numberKey != null) {
            results += zeroQueryNumberDict.lookup(numberKey, posMatcher.getCounterSuffixWordId(), posMatcher.getCounterSuffixWordId())
            results += zeroQueryNumberDict.lookup("default", posMatcher.getCounterSuffixWordId(), posMatcher.getCounterSuffixWordId())
            if (results.isNotEmpty()) {
                return results
            }
        }
        results += zeroQueryDict.lookup(historyValue)
        if (historyKey.endsWith("@") && historyKey == historyValue) {
            results += zeroQueryDict.lookup("@")
        }
        if (request.historyRid == 0) {
            return results
        }
        if (results.isEmpty() || !request.disableZeroQuerySuffixPrediction) {
            getPredictiveResultsForUnigram(suffixDictionary, request.copy(key = ""), PredictionTypes.Suffix, PredictionMaxResultsSize, results)
        }
        return results
    }

    private fun aggregateRealtime(request: PredictionRequest, size: Int): List<Result> =
        realtimeDecoder.decode(
            key = request.key,
            requestType = request.requestType,
            maxCandidatesSize = size,
            createPartialCandidates = request.createPartialCandidates,
            kanaModifierInsensitiveConversion = request.kanaModifierInsensitiveConversion,
        )

    private fun aggregateUnigram(request: PredictionRequest, results: MutableList<Result>) {
        if (request.key.isEmpty()) {
            return
        }
        val minKeyLength = if (request.requestType == RequestType.PREDICTION || request.mixedConversion) 1 else 3
        if (request.key.charsLen() < minKeyLength) {
            return
        }
        val before = results.size
        val cutoff = getCandidateCutoffThreshold(request.requestType)
        getPredictiveResultsForUnigram(
            dictionary = dictionary,
            request = request,
            types = PredictionTypes.Unigram,
            lookupLimit = cutoff,
            results = results,
        )
        if (results.size - before >= cutoff) {
            results.subList(before, results.size).clear()
        }
        if (request.mixedConversion) {
            val raw = results.subList(before, results.size).toMutableList()
            ResultFilter.removeRedundantResults(raw)
            results.subList(before, results.size).clear()
            results += raw
        }
    }

    private fun aggregatePrefix(request: PredictionRequest, results: MutableList<Result>) {
        val requestKeyLength = request.key.charsLen()
        if (requestKeyLength <= 1) {
            return
        }
        val lookupKey = String(request.key.codePoints().toArray(), 0, requestKeyLength - 1)
        val limit = getCandidateCutoffThreshold(request.requestType)
        dictionary.lookupPrefixWithOptions(lookupKey, request.kanaModifierInsensitiveConversion) { token ->
            if (token.attributes and Token.Attributes.UserDictionary != 0 && token.lid == posMatcher.getUnknownId()) {
                return@lookupPrefixWithOptions
            }
            if (token.lid == posMatcher.getKanjiNumberId() && token.rid == posMatcher.getKanjiNumberId()) {
                return@lookupPrefixWithOptions
            }
            if (token.value.charsLen() < 2 || token.value.all { it in '0'..'9' }) {
                return@lookupPrefixWithOptions
            }
            val result = Result()
            result.initializeByTokenAndTypes(token, PredictionTypes.Prefix)
            if (token.key.charsLen() < requestKeyLength) {
                result.attributes = result.attributes or PredictionTypes.Prefix
                result.consumedKeySize = token.key.charsLen()
            }
            results += result
        }
        if (results.size > limit) {
            results.subList(limit, results.size).clear()
        }
    }

    private fun getPredictiveResultsForUnigram(
        dictionary: DictionaryInterface,
        request: PredictionRequest,
        types: Int,
        lookupLimit: Int,
        results: MutableList<Result>,
    ) {
        val lookupKey = request.predictionLookupKey
        if (lookupKey.isEmpty()) {
            return
        }
        val originalKeyByteSize = lookupKey.toByteArray(Charsets.UTF_8).size
        val before = results.size
        dictionary.lookupPredictive(lookupKey) { token ->
            if (results.size - before >= lookupLimit) {
                return@lookupPredictive
            }
            if ((token.attributes and Token.Attributes.UserDictionary != 0 && token.lid == posMatcher.getUnknownId()) ||
                token.lid == posMatcher.getZipcodeId()
            ) {
                if (token.key != lookupKey) return@lookupPredictive
            }
            if (isNoisyNumberToken(lookupKey, token)) {
                return@lookupPredictive
            }
            val result = Result()
            result.initializeByTokenAndTypes(token, types)
            if (token.attributes and Token.Attributes.KeyExpanded != 0) {
                result.wcost += SpatialCostPenalty
                result.attributes = result.attributes or PredictionTypes.KeyExpandedInDictionary
            }
            if (token.key.toByteArray(Charsets.UTF_8).size < originalKeyByteSize) {
                result.attributes = result.attributes or PredictionTypes.Prefix
                result.consumedKeySize = token.key.charsLen()
            }
            results += result
        }
    }

    private fun isNoisyNumberToken(key: String, token: Token): Boolean {
        if (key.isEmpty() || !key.all { it in '0'..'9' }) return false
        val keySuffix = token.key.removePrefix(key)
        if (keySuffix.isEmpty()) return false
        if (keySuffix.firstOrNull()?.isDigit() == true) return true
        if (!token.value.startsWith(key)) return false
        val valueSuffix = token.value.removePrefix(key)
        if (valueSuffix.isEmpty()) return false
        if (valueSuffix.firstOrNull()?.isDigit() == true) return true
        return valueSuffix.charsLen() >= 3
    }

    private fun shouldAggregateRealtimeConversionResults(request: PredictionRequest): Boolean {
        val keyBytes = request.key.toByteArray(Charsets.UTF_8).size
        if (request.key.isEmpty() || keyBytes >= MaxRealtimeKeySize) return false
        return request.requestType == RequestType.PARTIAL_SUGGESTION || request.useRealtimeConversion || request.mixedConversion
    }

    private fun getRealtimeCandidateMaxSize(request: PredictionRequest): Int {
        if (request.key.isEmpty()) return 0
        val sizeLimit = request.maxDictionaryPredictionCandidatesSize
        var maxSize = sizeLimit
        if (request.createPartialCandidates) maxSize = 20
        var defaultSize = 10
        if (request.key.charsLen() >= FewResultThreshold) {
            maxSize = 8
            defaultSize = 5
        }
        maxSize = minOf(maxSize, sizeLimit)
        defaultSize = minOf(defaultSize, sizeLimit)
        return when (request.requestType) {
            RequestType.PREDICTION -> if (request.mixedConversion) maxSize else defaultSize
            RequestType.SUGGESTION -> if (request.mixedConversion) defaultSize else 1
            RequestType.PARTIAL_PREDICTION -> maxSize
            RequestType.PARTIAL_SUGGESTION -> defaultSize
            else -> 0
        }
    }

    private fun isNotExceedingCutoffThreshold(request: PredictionRequest, results: List<Result>): Boolean =
        results.size <= getCandidateCutoffThreshold(request.requestType)

    private fun getCandidateCutoffThreshold(requestType: RequestType): Int =
        if (requestType == RequestType.PREDICTION) PredictionMaxResultsSize else SuggestionMaxResultsSize

    private fun isZipCodeRequest(key: String): Boolean =
        key.isNotEmpty() && key.all { it in '0'..'9' || it == '-' }

    private fun normalizedArabicNumber(value: String): String? {
        if (value.isEmpty()) return null
        val normalized = buildString {
            value.forEach { ch ->
                when (ch) {
                    in '0'..'9' -> append(ch)
                    in '０'..'９' -> append('0' + (ch - '０'))
                    else -> return null
                }
            }
        }
        return normalized
    }

    companion object {
        private const val SuggestionMaxResultsSize: Int = 256
        private const val PredictionMaxResultsSize: Int = 100000
        private const val MaxRealtimeKeySize: Int = 300
        private const val FewResultThreshold: Int = 8
        private const val SpatialCostPenalty: Int = 2500
    }
}

data class PredictionRequest(
    val key: String,
    val requestType: RequestType = RequestType.PREDICTION,
    val predictionLookupKey: String = "",
    val mixedConversion: Boolean = false,
    val zeroQuerySuggestion: Boolean = false,
    val historyKey: String = "",
    val historyValue: String = "",
    val historyRid: Int = 0,
    val historyCost: Int = 0,
    val precedingText: String = "",
    val maxDictionaryPredictionCandidatesSize: Int = 20,
    val maxUserHistoryPredictionCandidatesSize: Int = 3,
    val maxUserHistoryPredictionCandidatesSizeForZeroQuery: Int = 4,
    val suggestionsSize: Int = 3,
    val useDictionarySuggest: Boolean = true,
    val useRealtimeConversion: Boolean = true,
    val autoPartialSuggestion: Boolean = false,
    val includeExactKey: Boolean = mixedConversion,
    val createPartialCandidates: Boolean = false,
    val kanaModifierInsensitiveConversion: Boolean = false,
    val disableZeroQuerySuffixPrediction: Boolean = false,
    val suffixTransitionCostThreshold: Int = 0,
) {
    fun isZeroQuerySuggestion(): Boolean = key.isEmpty()
}
