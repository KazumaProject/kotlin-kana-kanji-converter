package mozc_runtime.prediction

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.InnerSegment
import mozc_runtime.dictionary.Token

// Ported from mozc/src/prediction/result.h
// Ported from mozc/src/prediction/result.cc
data class Result(
    var key: String = "",
    var value: String = "",
    var contentKey: String = "",
    var contentValue: String = "",
    var description: String = "",
    var displayValue: String = "",
    var attributes: Int = Attribute.DEFAULT_ATTRIBUTE,
    var wcost: Int = 0,
    var cost: Int = 0,
    var structureCost: Int = 0,
    var lid: Int = 0,
    var rid: Int = 0,
    var consumedKeySize: Int = 0,
    var penalty: Int = 0,
    var costBeforeRescoring: Int = 0,
    var removed: Boolean = false,
    var candidateSource: String = "",
    val innerSegments: MutableList<InnerSegment> = ArrayList(),
) {
    fun initializeByTokenAndTypes(token: Token, types: Int) {
        setTypesAndTokenAttributes(types, token.attributes)
        key = token.key
        value = token.value
        contentKey = token.key
        contentValue = token.value
        wcost = token.cost
        lid = token.lid
        rid = token.rid
    }

    fun setTypesAndTokenAttributes(types: Int, tokenAttributes: Int) {
        attributes = types
        if (attributes and Attribute.REALTIME_TOP != 0) {
            attributes = attributes or Attribute.NO_VARIANTS_EXPANSION
        }
        if (tokenAttributes and Token.Attributes.SpellingCorrection != 0) {
            attributes = attributes or Attribute.SPELLING_CORRECTION
        }
        if (tokenAttributes and Token.Attributes.UserDictionary != 0) {
            attributes = attributes or Attribute.USER_DICTIONARY or
                Attribute.NO_MODIFICATION or Attribute.NO_VARIANTS_EXPANSION
        }
        if (tokenAttributes and Token.Attributes.KeyExpanded != 0) {
            attributes = attributes or Attribute.KEY_EXPANDED_IN_DICTIONARY
        }
        if (tokenAttributes and Token.Attributes.SuffixDictionary != 0) {
            attributes = attributes or Attribute.SUFFIX_DICTIONARY
        }
    }

    fun predictionTypeNames(): List<String> = PredictionTypes.namesOf(attributes and PredictionTypes.MaskForTesting)

    fun candidateAttributeNames(): List<String> =
        Attribute.namesOf(attributes and PredictionTypes.MaskForTesting.inv())

    companion object {
        const val InvalidCost: Int = 2 shl 20
    }
}

object PredictionTypes {
    const val Unigram: Int = Attribute.UNIGRAM
    const val Bigram: Int = Attribute.BIGRAM
    const val Realtime: Int = Attribute.REALTIME_CONVERSION
    const val Suffix: Int = Attribute.SUFFIX_DICTIONARY
    const val English: Int = Attribute.ENGLISH
    const val TypingCorrection: Int = Attribute.TYPING_CORRECTION
    const val Prefix: Int = Attribute.PARTIALLY_KEY_CONSUMED
    const val Number: Int = Attribute.NUMBER
    const val SingleKanji: Int = Attribute.SINGLE_KANJI
    const val TypingCompletion: Int = Attribute.TYPING_COMPLETION
    const val PostCorrection: Int = Attribute.POST_CORRECTION
    const val SupplementalModel: Int = Attribute.SUPPLEMENTAL_MODEL
    const val WeakUserHistoryPrediction: Int = Attribute.WEAK_USER_HISTORY_PREDICTION
    const val RealtimeTop: Int = Attribute.REALTIME_TOP
    const val KeyExpandedInDictionary: Int = Attribute.KEY_EXPANDED_IN_DICTIONARY
    const val DisableRescoring: Int = Attribute.DISABLE_RESCORING

    const val MaskForTesting: Int =
        Unigram or Bigram or Realtime or Suffix or English or TypingCorrection or Prefix or Number or
            SingleKanji or TypingCompletion or PostCorrection or SupplementalModel or WeakUserHistoryPrediction or
            RealtimeTop or KeyExpandedInDictionary or DisableRescoring

    private val names = listOf(
        Unigram to "UNIGRAM",
        Bigram to "BIGRAM",
        Realtime to "REALTIME",
        Suffix to "SUFFIX",
        English to "ENGLISH",
        TypingCorrection to "TYPING_CORRECTION",
        Prefix to "PREFIX",
        Number to "NUMBER",
        SingleKanji to "SINGLE_KANJI",
        TypingCompletion to "TYPING_COMPLETION",
        PostCorrection to "POST_CORRECTION",
        SupplementalModel to "SUPPLEMENTAL_MODEL",
        WeakUserHistoryPrediction to "WEAK_USER_HISTORY_PREDICTION",
        RealtimeTop to "REALTIME_TOP",
        KeyExpandedInDictionary to "KEY_EXPANDED_IN_DICTIONARY",
        DisableRescoring to "DISABLE_RESCORING",
    )

    fun namesOf(types: Int): List<String> =
        names.filter { (bit, _) -> types and bit != 0 }.map { it.second }

    fun debugString(types: Int): String = buildString {
        if (types and Unigram != 0) append('U')
        if (types and Bigram != 0) append('B')
        if (types and RealtimeTop != 0) {
            append("R1")
        } else if (types and Realtime != 0) {
            append('R')
        }
        if (types and Suffix != 0) append('S')
        if (types and English != 0) append('E')
        if (types and TypingCorrection != 0) append('T')
        if (types and TypingCompletion != 0) append('C')
        if (types and SupplementalModel != 0) append('X')
        if (types and KeyExpandedInDictionary != 0) append('K')
    }

    fun bitsOf(names: List<String>): Int {
        val byName = this.names.associate { it.second to it.first }
        return names.fold(0) { bits, name ->
            bits or (byName[name] ?: error("Unknown prediction type: $name"))
        }
    }
}

object ResultOrdering {
    fun costComparator(): Comparator<Result> =
        compareBy<Result> { it.cost }
            .then(valueComparator())
            .thenBy { it.key }
            .thenBy { it.attributes and PredictionTypes.MaskForTesting.inv() }
            .thenBy { it.wcost }
            .thenBy { it.lid }
            .thenBy { it.rid }
            .thenBy { it.consumedKeySize }
            .thenBy { it.penalty }
            .thenBy { it.costBeforeRescoring }
            .thenBy { it.description }
            .thenBy { it.displayValue }

    fun wcostComparator(): Comparator<Result> =
        compareBy<Result> { it.wcost }
            .then(valueComparator())
            .thenBy { it.key }

    private fun valueComparator(): Comparator<Result> =
        Comparator { left, right -> compareValuesByLengthThenText(left.value, right.value) }

    private fun compareValuesByLengthThenText(left: String, right: String): Int {
        val leftPoints = left.codePoints().toArray()
        val rightPoints = right.codePoints().toArray()
        val min = minOf(leftPoints.size, rightPoints.size)
        for (index in 0 until min) {
            if (leftPoints[index] != rightPoints[index]) {
                val lengthDiff = leftPoints.size - rightPoints.size
                return if (lengthDiff != 0) lengthDiff else leftPoints[index].compareTo(rightPoints[index])
            }
        }
        return leftPoints.size - rightPoints.size
    }
}
