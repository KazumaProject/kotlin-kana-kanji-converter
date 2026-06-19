package mozc_runtime.prediction

import mozc_data.MozcDataManager
import mozc_runtime.converter.Connector
import mozc_runtime.converter.ImmutableConverter
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segmenter
import mozc_runtime.dictionary.DictionaryImpl
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.SuffixDictionary
import mozc_runtime.dictionary.UserDictionary
import mozc_runtime.dictionary.system.SystemDictionary
import mozc_runtime.dictionary.system.ValueDictionary

// Ported from mozc/src/prediction/predictor.h
// Ported from mozc/src/prediction/predictor.cc
class Predictor(
    private val dictionaryPredictor: DictionaryPredictor,
    private val userHistoryPredictor: UserHistoryPredictor,
) {
    fun predict(input: String): List<Result> =
        predict(PredictionRequest(key = input, requestType = RequestType.PREDICTION))

    fun predict(request: PredictionRequest): List<Result> {
        if (request.requestType == RequestType.CONVERSION) {
            return listOf()
        }
        val predictionSize = if (request.requestType == RequestType.SUGGESTION) {
            request.suggestionsSize.coerceIn(1, 9)
        } else {
            PredictionSizeForDesktop
        }
        val requestForPrediction = request.copy(
            maxUserHistoryPredictionCandidatesSize = predictionSize,
            maxUserHistoryPredictionCandidatesSizeForZeroQuery = predictionSize,
        )
        val userHistoryResults = userHistoryPredictor.predict(requestForPrediction)
        val dictionaryResults = if (userHistoryResults.size < predictionSize) {
            dictionaryPredictor.predict(
                requestForPrediction.copy(
                    maxDictionaryPredictionCandidatesSize = predictionSize - userHistoryResults.size,
                ),
            )
        } else {
            listOf()
        }
        return mixCandidates(userHistoryResults, dictionaryResults)
    }

    fun zeroQuery(context: String): List<Result> =
        predict(
            PredictionRequest(
                key = "",
                requestType = RequestType.PREDICTION,
                mixedConversion = true,
                zeroQuerySuggestion = true,
                historyKey = context,
                historyValue = context,
                maxDictionaryPredictionCandidatesSize = PredictionSizeForMixedConversion,
                maxUserHistoryPredictionCandidatesSize = 3,
                maxUserHistoryPredictionCandidatesSizeForZeroQuery = 4,
            ),
        )

    private fun mixCandidates(userHistoryResults: List<Result>, dictionaryResults: List<Result>): List<Result> {
        val userHistory = userHistoryResults.map { it.copy() }.toMutableList()
        if (userHistory.size == 1 && dictionaryResults.isNotEmpty() &&
            userHistory.first().key == dictionaryResults.first().key &&
            userHistory.first().value == dictionaryResults.first().value
        ) {
            userHistory[0].attributes = userHistory[0].attributes or mozc_runtime.converter.Attribute.NO_DELETABLE
        }
        val results = ArrayList<Result>()
        results += userHistory
        results += dictionaryResults
        demoteWeakUserHistory(results)
        return results
    }

    private fun demoteWeakUserHistory(results: MutableList<Result>) {
        if (results.isEmpty() || results.first().attributes and mozc_runtime.converter.Attribute.WEAK_USER_HISTORY_PREDICTION == 0) {
            return
        }
        val firstStrong = results.indexOfFirst {
            it.attributes and mozc_runtime.converter.Attribute.WEAK_USER_HISTORY_PREDICTION == 0
        }
        if (firstStrong >= 0) {
            val strong = results.removeAt(firstStrong)
            results.add(0, strong)
        }
    }

    companion object {
        private const val PredictionSizeForDesktop: Int = 100
        private const val PredictionSizeForMixedConversion: Int = 200

        fun fromMozcDataManager(dataManager: MozcDataManager): Predictor {
            val posMatcher = PosMatcher(dataManager.posMatcherData)
            val posGroup = PosGroup(dataManager.posGroupData)
            val systemDictionary = SystemDictionary.fromMozcDataManager(dataManager)
            val dictionary = DictionaryImpl(
                systemDictionary,
                ValueDictionary(systemDictionary.valueTrie(), posMatcher.getSuggestOnlyWordId()),
                UserDictionary(listOf()),
            )
            val suffixDictionary = SuffixDictionary(listOf())
            val connector = Connector(dataManager.connectorData)
            val segmenter = Segmenter(dataManager, posMatcher)
            val immutableConverter = ImmutableConverter(
                dictionary = dictionary,
                connector = connector,
                segmenter = segmenter,
                posMatcher = posMatcher,
                posGroup = posGroup,
                userDictionary = UserDictionary(listOf()),
            )
            val realtimeDecoder = RealtimeDecoder(immutableConverter)
            val suggestionFilter = SuggestionFilter.from(dataManager.section("sugg"))
            val numberDecoder = NumberDecoder(posMatcher)
            val singleKanjiDecoder = SingleKanjiDecoder.fromMozcDataManager(dataManager, posMatcher)
            val zeroQueryDict = ZeroQueryDict.fromMozcDataManager(dataManager)
            val zeroQueryNumberDict = ZeroQueryDict.numberFromMozcDataManager(dataManager)
            val aggregator = DictionaryPredictionAggregator(
                dictionary = dictionary,
                suffixDictionary = suffixDictionary,
                posMatcher = posMatcher,
                realtimeDecoder = realtimeDecoder,
                numberDecoder = numberDecoder,
                singleKanjiDecoder = singleKanjiDecoder,
                zeroQueryDict = zeroQueryDict,
                zeroQueryNumberDict = zeroQueryNumberDict,
            )
            val dictionaryPredictor = DictionaryPredictor(
                aggregator = aggregator,
                realtimeDecoder = realtimeDecoder,
                connector = connector,
                segmenter = segmenter,
                posMatcher = posMatcher,
                suggestionFilter = suggestionFilter,
            )
            return Predictor(dictionaryPredictor, UserHistoryPredictor(UserHistoryStorage()))
        }
    }
}
