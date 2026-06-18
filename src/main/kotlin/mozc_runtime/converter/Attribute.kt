package mozc_runtime.converter

// Ported from mozc/src/converter/attribute.h
object Attribute {
    const val DEFAULT_ATTRIBUTE: Int = 0
    const val BEST_CANDIDATE: Int = 1 shl 0
    const val RERANKED: Int = 1 shl 1
    const val NO_HISTORY_LEARNING: Int = 1 shl 2
    const val NO_SUGGEST_LEARNING: Int = 1 shl 3
    const val NO_LEARNING: Int = NO_HISTORY_LEARNING or NO_SUGGEST_LEARNING
    const val CONTEXT_SENSITIVE: Int = 1 shl 4
    const val SPELLING_CORRECTION: Int = 1 shl 5
    const val NO_VARIANTS_EXPANSION: Int = 1 shl 6
    const val NO_EXTRA_DESCRIPTION: Int = 1 shl 7
    const val REALTIME_CONVERSION: Int = 1 shl 8
    const val USER_DICTIONARY: Int = 1 shl 9
    const val COMMAND_CANDIDATE: Int = 1 shl 10
    const val PARTIALLY_KEY_CONSUMED: Int = 1 shl 11
    const val TYPING_CORRECTION: Int = 1 shl 12
    const val AUTO_PARTIAL_SUGGESTION: Int = 1 shl 13
    const val USER_HISTORY_PREDICTION: Int = 1 shl 14
    const val SUFFIX_DICTIONARY: Int = 1 shl 15
    const val NO_MODIFICATION: Int = 1 shl 16
    const val USER_SEGMENT_HISTORY_REWRITER: Int = 1 shl 17
    const val KEY_EXPANDED_IN_DICTIONARY: Int = 1 shl 18
    const val NO_DELETABLE: Int = 1 shl 19
    const val UNIGRAM: Int = 1 shl 20
    const val BIGRAM: Int = 1 shl 21
    const val ENGLISH: Int = 1 shl 22
    const val NUMBER: Int = 1 shl 23
    const val SINGLE_KANJI: Int = 1 shl 24
    const val TYPING_COMPLETION: Int = 1 shl 25
    const val POST_CORRECTION: Int = 1 shl 26
    const val SUPPLEMENTAL_MODEL: Int = 1 shl 27
    const val WEAK_USER_HISTORY_PREDICTION: Int = 1 shl 28
    const val REALTIME_TOP: Int = 1 shl 29
    const val DISABLE_RESCORING: Int = 1 shl 30

    private val names = listOf(
        BEST_CANDIDATE to "BEST_CANDIDATE",
        RERANKED to "RERANKED",
        NO_HISTORY_LEARNING to "NO_HISTORY_LEARNING",
        NO_SUGGEST_LEARNING to "NO_SUGGEST_LEARNING",
        CONTEXT_SENSITIVE to "CONTEXT_SENSITIVE",
        SPELLING_CORRECTION to "SPELLING_CORRECTION",
        NO_VARIANTS_EXPANSION to "NO_VARIANTS_EXPANSION",
        NO_EXTRA_DESCRIPTION to "NO_EXTRA_DESCRIPTION",
        REALTIME_CONVERSION to "REALTIME_CONVERSION",
        USER_DICTIONARY to "USER_DICTIONARY",
        COMMAND_CANDIDATE to "COMMAND_CANDIDATE",
        PARTIALLY_KEY_CONSUMED to "PARTIALLY_KEY_CONSUMED",
        TYPING_CORRECTION to "TYPING_CORRECTION",
        AUTO_PARTIAL_SUGGESTION to "AUTO_PARTIAL_SUGGESTION",
        USER_HISTORY_PREDICTION to "USER_HISTORY_PREDICTION",
        SUFFIX_DICTIONARY to "SUFFIX_DICTIONARY",
        NO_MODIFICATION to "NO_MODIFICATION",
        USER_SEGMENT_HISTORY_REWRITER to "USER_SEGMENT_HISTORY_REWRITER",
        KEY_EXPANDED_IN_DICTIONARY to "KEY_EXPANDED_IN_DICTIONARY",
        NO_DELETABLE to "NO_DELETABLE",
        UNIGRAM to "UNIGRAM",
        BIGRAM to "BIGRAM",
        ENGLISH to "ENGLISH",
        NUMBER to "NUMBER",
        SINGLE_KANJI to "SINGLE_KANJI",
        TYPING_COMPLETION to "TYPING_COMPLETION",
        POST_CORRECTION to "POST_CORRECTION",
        SUPPLEMENTAL_MODEL to "SUPPLEMENTAL_MODEL",
        WEAK_USER_HISTORY_PREDICTION to "WEAK_USER_HISTORY_PREDICTION",
        REALTIME_TOP to "REALTIME_TOP",
        DISABLE_RESCORING to "DISABLE_RESCORING",
    )

    fun namesOf(attributes: Int): List<String> =
        names.filter { (bit, _) -> attributes and bit != 0 }.map { it.second }

    fun bitsOf(names: List<String>): Int {
        val byName = this.names.associate { it.second to it.first }
        return names.fold(0) { bits, name ->
            bits or (byName[name] ?: error("Unknown converter candidate attribute: $name"))
        }
    }
}
