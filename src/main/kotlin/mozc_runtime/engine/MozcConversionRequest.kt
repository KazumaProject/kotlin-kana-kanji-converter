package mozc_runtime.engine

import java.time.Instant

data class MozcConversionRequest(
    val requestType: MozcRequestType,
    val input: String,
    val context: String = "",
    val maxCandidates: Int = 20,
    val fixedTime: Instant? = null,
    val enableA11yDescription: Boolean = false,
    val mixedConversion: Boolean = requestType == MozcRequestType.ZERO_QUERY,
    val zeroQuerySuggestion: Boolean = requestType == MozcRequestType.ZERO_QUERY,
    val suggestionsSize: Int = 3,
    val useDictionarySuggest: Boolean = true,
    val useRealtimeConversion: Boolean = true,
    val useSingleKanjiConversion: Boolean = true,
    val useSymbolConversion: Boolean = true,
    val useNumberConversion: Boolean = true,
    val useEmoticonConversion: Boolean = true,
    val useEmojiConversion: Boolean = true,
    val useZipCodeConversion: Boolean = true,
    val useT13NConversion: Boolean = true,
    val useSpellingCorrection: Boolean = true,
    val kanaModifierInsensitiveConversion: Boolean = false,
    val incognitoMode: Boolean = false,
)
