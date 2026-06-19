package mozc_runtime.rewriter

import mozc_data.MozcDataManager
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.converter.charsLen
import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.data.SerializedDictionary
import mozc_runtime.data.SerializedSingleKanjiDictionary
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

// Ported from mozc/src/rewriter/rewriter.h
// Ported from mozc/src/rewriter/rewriter.cc
interface Rewriter {
    fun capability(request: RewriterRequest): Int = Capability.CONVERSION
    fun rewrite(request: RewriterRequest, segments: Segments): Boolean
    fun focus(segments: Segments, segmentIndex: Int, candidateIndex: Int): Boolean = true

    companion object {
        fun fromMozcDataManager(
            dataManager: MozcDataManager,
            posMatcher: PosMatcher,
            posGroup: PosGroup,
            dictionary: DictionaryInterface,
            clock: Clock = Clock.fixed(Instant.parse(DefaultFixedInstant), ZoneOffset.UTC),
        ): MergerRewriter {
            val singleKanjiDictionary = SerializedSingleKanjiDictionary(
                dataManager.section("single_kanji_token"),
                dataManager.section("single_kanji_string"),
                dataManager.section("single_kanji_variant_type"),
                dataManager.section("single_kanji_variant_token"),
                dataManager.section("single_kanji_variant_string"),
                dataManager.section("single_kanji_noun_prefix_token"),
                dataManager.section("single_kanji_noun_prefix_string"),
            )
            val usageRewriter = if (dataManager.hasUsageDictionary()) {
                UsageRewriter.fromMozcDataManager(dataManager, dictionary, posMatcher)
            } else {
                UsageRewriter.withoutDictionary()
            }
            return MergerRewriter(
                listOf(
                    FocusCandidateRewriter(dataManager.section("counter_suffix"), posMatcher),
                    LanguageAwareRewriter(posMatcher, dictionary),
                    TransliterationRewriter(posMatcher),
                    EnglishVariantsRewriter(posMatcher),
                    NumberRewriter(dataManager.section("counter_suffix"), posMatcher),
                    CollocationRewriter(dataManager.section("coll"), dataManager.section("cols"), posMatcher),
                    SingleKanjiRewriter(posMatcher, singleKanjiDictionary),
                    IvsVariantsRewriter(),
                    EmoticonRewriter(
                        SerializedDictionary(dataManager.section("emoticon_token"), dataManager.section("emoticon_string")),
                    ),
                    EmojiRewriter.fromMozcDataManager(dataManager),
                    CalculatorRewriter(),
                    SymbolRewriter(
                        SerializedDictionary(dataManager.section("symbol_token"), dataManager.section("symbol_string")),
                    ),
                    UnicodeRewriter(),
                    VariantsRewriter(posMatcher),
                    ZipcodeRewriter(posMatcher),
                    DiceRewriter(clock),
                    SmallLetterRewriter(),
                    UserBoundaryHistoryRewriter(),
                    UserSegmentHistoryRewriter(posMatcher, posGroup),
                    DateRewriter(clock),
                    FortuneRewriter(clock),
                    usageRewriter,
                    VersionRewriter(dataManager.version()),
                    CorrectionRewriter.fromMozcDataManager(dataManager, dictionary),
                    T13nPromotionRewriter(),
                    EnvironmentalFilterRewriter.fromMozcDataManager(dataManager),
                    RemoveRedundantCandidateRewriter(),
                    A11yDescriptionRewriter.fromMozcDataManager(dataManager),
                ),
            )
        }

        const val DefaultFixedInstant: String = "2011-04-18T15:06:31Z"
    }
}

object Capability {
    const val NONE: Int = 0
    const val CONVERSION: Int = 1
    const val PREDICTION: Int = 2
    const val SUGGESTION: Int = 4
    const val ALL: Int = CONVERSION or PREDICTION or SUGGESTION
}

data class RewriterRequest(
    val key: String,
    val requestType: RequestType = RequestType.CONVERSION,
    val mixedConversion: Boolean = false,
    val useSingleKanjiConversion: Boolean = true,
    val useSymbolConversion: Boolean = true,
    val useNumberConversion: Boolean = true,
    val useEmoticonConversion: Boolean = true,
    val useEmojiConversion: Boolean = true,
    val useZipCodeConversion: Boolean = true,
    val useT13nConversion: Boolean = true,
    val useSpellingCorrection: Boolean = true,
    val incognitoMode: Boolean = false,
    val skipSlowRewriters: Boolean = false,
    val symbolRewriterCandidatePosition: Int = 3,
    val symbolRewriterPromotionSize: Int = 15,
    val suggestionsSize: Int = 3,
    val emojiRewriterCapability: Int = Capability.CONVERSION,
    val additionalRenderableEmojiVersions: Set<Int> = emptySet(),
    val enableA11yDescription: Boolean = false,
    val zeroQuerySuggestion: Boolean = false,
    val rawText: String = key,
    val compositionText: String = key,
)

internal fun capabilityForRequestType(requestType: RequestType): Int =
    when (requestType) {
        RequestType.CONVERSION -> Capability.CONVERSION
        RequestType.PREDICTION, RequestType.PARTIAL_PREDICTION -> Capability.PREDICTION
        RequestType.SUGGESTION, RequestType.PARTIAL_SUGGESTION -> Capability.SUGGESTION
        RequestType.REVERSE_CONVERSION -> Capability.NONE
    }

internal fun calculateInsertPosition(segment: Segment, offset: Int): Int {
    var historyCandidates = 0
    for (index in 0 until segment.candidatesSize()) {
        val candidate = segment.candidate(index)
        if (candidate.attributes and Attribute.USER_HISTORY_PREDICTION != 0) {
            historyCandidates += 1
        } else if (historyCandidates > 0) {
            break
        }
    }
    return (offset + historyCandidates).coerceAtMost(segment.candidatesSize())
}

internal fun Candidate.cloneCandidate(): Candidate {
    val candidate = Candidate()
    candidate.copyFrom(this)
    return candidate
}

internal fun Segment.insertCandidateCopy(index: Int, source: Candidate): Candidate {
    val candidate = insertCandidate(index)
    candidate.copyFrom(source)
    return candidate
}

internal fun Segment.appendCandidate(source: Candidate): Candidate {
    val candidate = addCandidate()
    candidate.copyFrom(source)
    return candidate
}

internal fun Segment.insertCandidates(index: Int, sources: List<Candidate>) {
    var position = index
    sources.forEach { source ->
        insertCandidateCopy(position, source)
        position += 1
    }
}

internal fun Segment.moveCandidate(fromIndex: Int, toIndex: Int) {
    if (fromIndex !in 0 until candidatesSize()) {
        return
    }
    val copy = candidate(fromIndex).cloneCandidate()
    eraseCandidate(fromIndex)
    insertCandidateCopy(toIndex.coerceIn(0, candidatesSize()), copy)
}

internal fun Segment.baseCandidate(): Candidate? =
    if (candidatesSize() > 0) candidate(0) else null

internal fun Candidate.setKeyValue(keyText: String, valueText: String) {
    key = keyText
    value = valueText
    contentKey = keyText
    contentValue = valueText
}

internal fun Candidate.functionalSuffix(): String =
    if (value.length >= contentValue.length) value.substring(contentValue.length) else ""

internal fun isSingleKanjiText(value: String): Boolean =
    value.charsLen() == 1 && value.codePoints().allMatch { codePoint ->
        codePoint == 0x3005 ||
            codePoint in 0x3400..0x4dbf ||
            codePoint in 0x4e00..0x9fff ||
            codePoint in 0xf900..0xfaff
    }
