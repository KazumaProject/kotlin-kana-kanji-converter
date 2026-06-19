package mozc_runtime.engine

import mozc_data.MozcDataManager
import mozc_runtime.converter.CandidateFilter
import mozc_runtime.converter.Connector
import mozc_runtime.converter.Converter
import mozc_runtime.converter.HistoryReconstructor
import mozc_runtime.converter.ImmutableConverter
import mozc_runtime.converter.KeyCorrector
import mozc_runtime.converter.Lattice
import mozc_runtime.converter.NBestGenerator
import mozc_runtime.converter.ReverseConverter
import mozc_runtime.converter.Segmenter
import mozc_runtime.dictionary.DictionaryImpl
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.SuffixDictionary
import mozc_runtime.dictionary.UserDictionary
import mozc_runtime.dictionary.UserPos
import mozc_runtime.dictionary.system.SystemDictionary
import mozc_runtime.dictionary.system.ValueDictionary
import mozc_runtime.prediction.DictionaryPredictionAggregator
import mozc_runtime.prediction.DictionaryPredictor
import mozc_runtime.prediction.NumberDecoder
import mozc_runtime.prediction.Predictor
import mozc_runtime.prediction.RealtimeDecoder
import mozc_runtime.prediction.SingleKanjiDecoder
import mozc_runtime.prediction.SuggestionFilter
import mozc_runtime.prediction.UserHistoryPredictor
import mozc_runtime.prediction.UserHistoryStorage
import mozc_runtime.prediction.ZeroQueryDict
import mozc_runtime.rewriter.Rewriter
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

// Ported from mozc/src/engine/modules.cc
// Ported from mozc/src/engine/modules.h
class MozcModules private constructor(
    val dataManager: MozcDataManager,
    val posMatcher: PosMatcher,
    val posGroup: PosGroup,
    val userPos: UserPos,
    val systemDictionary: SystemDictionary,
    val valueDictionary: ValueDictionary,
    val dictionary: DictionaryImpl,
    val userDictionary: UserDictionary,
    val suffixDictionary: SuffixDictionary,
    val connector: Connector,
    val segmenter: Segmenter,
    val immutableConverter: ImmutableConverter,
    val candidateFilter: CandidateFilter,
    val userHistoryStorage: UserHistoryStorage,
    val userHistoryPredictor: UserHistoryPredictor,
    val realtimeDecoder: RealtimeDecoder,
    val suggestionFilter: SuggestionFilter,
    val numberDecoder: NumberDecoder,
    val singleKanjiDecoder: SingleKanjiDecoder,
    val zeroQueryDict: ZeroQueryDict,
    val zeroQueryNumberDict: ZeroQueryDict,
    val dictionaryPredictionAggregator: DictionaryPredictionAggregator,
    val dictionaryPredictor: DictionaryPredictor,
    val predictor: Predictor,
    val rewriter: Rewriter,
    val historyReconstructor: HistoryReconstructor,
    val reverseConverter: ReverseConverter,
    val converter: Converter,
) {
    val keyCorrectorFactory: (String, KeyCorrector.InputMode, Int) -> KeyCorrector =
        { key, mode, historySize -> KeyCorrector(key, mode, historySize) }

    fun nBestGenerator(lattice: Lattice): NBestGenerator =
        NBestGenerator(segmenter, connector, posMatcher, lattice, candidateFilter)

    companion object {
        fun fromMozcDataManager(
            dataManager: MozcDataManager,
            fixedTime: Instant = Instant.parse(Rewriter.DefaultFixedInstant),
        ): MozcModules {
            val clock = Clock.fixed(fixedTime, ZoneOffset.UTC)
            val posMatcher = PosMatcher(dataManager.posMatcherData)
            val posGroup = PosGroup(dataManager.posGroupData)
            val userPos = UserPos(dataManager.userPosTokenData, dataManager.userPosStringData)
            val systemDictionary = SystemDictionary.fromMozcDataManager(dataManager)
            val valueDictionary = ValueDictionary(systemDictionary.valueTrie(), posMatcher.getSuggestOnlyWordId())
            val userDictionary = UserDictionary(listOf())
            val dictionary = DictionaryImpl(systemDictionary, valueDictionary, userDictionary)
            val suffixDictionary = SuffixDictionary.fromMozcDataManager(dataManager)
            val connector = Connector(dataManager.connectorData)
            val segmenter = Segmenter(dataManager, posMatcher)
            val immutableConverter = ImmutableConverter(
                dictionary = dictionary,
                connector = connector,
                segmenter = segmenter,
                posMatcher = posMatcher,
                posGroup = posGroup,
                suffixDictionary = suffixDictionary,
                userDictionary = userDictionary,
            )
            val candidateFilter = CandidateFilter(posMatcher)
            val realtimeDecoder = RealtimeDecoder(immutableConverter)
            val suggestionFilter = SuggestionFilter.from(dataManager.section("sugg"))
            val numberDecoder = NumberDecoder(posMatcher)
            val singleKanjiDecoder = SingleKanjiDecoder.fromMozcDataManager(dataManager, posMatcher)
            val zeroQueryDict = ZeroQueryDict.fromMozcDataManager(dataManager)
            val zeroQueryNumberDict = ZeroQueryDict.numberFromMozcDataManager(dataManager)
            val dictionaryPredictionAggregator = DictionaryPredictionAggregator(
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
                aggregator = dictionaryPredictionAggregator,
                realtimeDecoder = realtimeDecoder,
                connector = connector,
                segmenter = segmenter,
                posMatcher = posMatcher,
                suggestionFilter = suggestionFilter,
            )
            val userHistoryStorage = UserHistoryStorage()
            val userHistoryPredictor = UserHistoryPredictor(userHistoryStorage)
            val predictor = Predictor(dictionaryPredictor, userHistoryPredictor)
            val rewriter = Rewriter.fromMozcDataManager(dataManager, posMatcher, posGroup, dictionary, clock)
            val historyReconstructor = HistoryReconstructor(posMatcher)
            val reverseConverter = ReverseConverter(systemDictionary, immutableConverter)
            val converter = Converter(
                immutableConverter = immutableConverter,
                predictor = predictor,
                rewriter = rewriter,
                historyReconstructor = historyReconstructor,
                reverseConverter = reverseConverter,
            )
            return MozcModules(
                dataManager = dataManager,
                posMatcher = posMatcher,
                posGroup = posGroup,
                userPos = userPos,
                systemDictionary = systemDictionary,
                valueDictionary = valueDictionary,
                dictionary = dictionary,
                userDictionary = userDictionary,
                suffixDictionary = suffixDictionary,
                connector = connector,
                segmenter = segmenter,
                immutableConverter = immutableConverter,
                candidateFilter = candidateFilter,
                userHistoryStorage = userHistoryStorage,
                userHistoryPredictor = userHistoryPredictor,
                realtimeDecoder = realtimeDecoder,
                suggestionFilter = suggestionFilter,
                numberDecoder = numberDecoder,
                singleKanjiDecoder = singleKanjiDecoder,
                zeroQueryDict = zeroQueryDict,
                zeroQueryNumberDict = zeroQueryNumberDict,
                dictionaryPredictionAggregator = dictionaryPredictionAggregator,
                dictionaryPredictor = dictionaryPredictor,
                predictor = predictor,
                rewriter = rewriter,
                historyReconstructor = historyReconstructor,
                reverseConverter = reverseConverter,
                converter = converter,
            )
        }
    }
}
