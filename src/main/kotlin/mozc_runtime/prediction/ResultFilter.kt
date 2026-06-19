package mozc_runtime.prediction

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Connector
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/prediction/result_filter.h
// Ported from mozc/src/prediction/result_filter.cc
class ResultFilter(
    private val request: PredictionRequest,
    private val posMatcher: PosMatcher,
    private val connector: Connector,
    private val suggestionFilter: SuggestionFilter,
) {
    private val seen = LinkedHashSet<String>()
    private var suffixCount = 0

    fun shouldRemove(result: Result, addedCount: Int): Boolean {
        if (result.removed) return true
        if (result.cost >= Result.InvalidCost) return true
        if (!request.autoPartialSuggestion && result.attributes and Attribute.PARTIALLY_KEY_CONSUMED != 0) return true
        if (selectSuggestionFilterStrategies(result) and FilterByValue != 0 &&
            suggestionFilter.isBadSuggestion(result.value)
        ) {
            return true
        }
        if (selectSuggestionFilterStrategies(result) and FilterByHistoryAndValue != 0 &&
            suggestionFilter.isBadSuggestion(request.historyValue + result.value)
        ) {
            return true
        }
        if (!request.includeExactKey &&
            result.attributes and Attribute.REALTIME_CONVERSION == 0 &&
            request.key == result.value
        ) {
            return true
        }
        if (result.value in seen) return true
        if (result.attributes and Attribute.SPELLING_CORRECTION != 0 &&
            result.key != request.key &&
            request.key.codePointCount(0, request.key.length) <= misspelledPosition(result.key, result.value) + 1
        ) {
            return true
        }
        if (request.historyRid != 0 &&
            result.attributes and Attribute.SUFFIX_DICTIONARY != 0 &&
            request.suffixTransitionCostThreshold > 0 &&
            connector.cost(request.historyRid, result.lid) > request.suffixTransitionCostThreshold
        ) {
            return true
        }
        if (result.attributes and Attribute.SUFFIX_DICTIONARY != 0 && suffixCount++ >= 20) {
            return true
        }
        seen += result.value
        return false
    }

    private fun selectSuggestionFilterStrategies(result: Result): Int {
        if (request.key.isEmpty() || result.key.isEmpty()) return FilterByValue or FilterByHistoryAndValue
        if (request.includeExactKey) return if (result.key == request.key) SkipFilter else FilterByValue
        return FilterByValue
    }

    private fun misspelledPosition(key: String, value: String): Int {
        val hiraganaValue = katakanaToHiragana(value)
        if (!isHiragana(hiraganaValue)) return key.codePointCount(0, key.length)
        val keyPoints = key.codePoints().toArray()
        val valuePoints = hiraganaValue.codePoints().toArray()
        val min = minOf(keyPoints.size, valuePoints.size)
        for (index in 0 until min) {
            if (keyPoints[index] != valuePoints[index]) return index
        }
        return keyPoints.size
    }

    companion object {
        private const val SkipFilter: Int = 0
        private const val FilterByValue: Int = 1
        private const val FilterByHistoryAndValue: Int = 2

        fun removeRedundantResults(results: MutableList<Result>) {
            val kept = ArrayList<Result>()
            val redundant = ArrayList<Result>()
            results.sortedWith(ResultOrdering.wcostComparator()).forEach { candidate ->
                if (kept.size < DeleteTrialCount && kept.any { maybeRedundant(it, candidate) }) {
                    redundant += candidate
                } else {
                    kept += candidate
                }
            }
            results.clear()
            results += kept
            results += redundant.sortedWith(ResultOrdering.wcostComparator()).take(DoNotDeleteCount)
        }

        private const val DeleteTrialCount: Int = 5
        private const val DoNotDeleteCount: Int = 5

        private fun maybeRedundant(reference: Result, target: Result): Boolean {
            if (reference.value == target.value) return true
            if (reference.key == target.key) return false
            if (!target.value.startsWith(reference.value)) return false
            val suffix = target.value.removePrefix(reference.value)
            return suffix.isNotEmpty() && !containsEmoji(suffix)
        }

        private fun containsEmoji(value: String): Boolean =
            value.codePoints().anyMatch { it in 0x1F000..0x1FAFF || it in 0x2600..0x27BF }

        private fun isHiragana(value: String): Boolean =
            value.isNotEmpty() && value.codePoints().allMatch { it in 0x3040..0x309F }

        private fun katakanaToHiragana(value: String): String =
            buildString {
                value.codePoints().forEachOrdered { codePoint ->
                    appendCodePoint(if (codePoint in 0x30A1..0x30F6) codePoint - 0x60 else codePoint)
                }
            }
    }
}
