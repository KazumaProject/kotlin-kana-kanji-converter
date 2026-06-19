package mozc_runtime.prediction

import mozc_data.MozcDataManager
import mozc_runtime.converter.charsLen
import mozc_runtime.data.SerializedSingleKanjiDictionary
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/prediction/single_kanji_decoder.h
// Ported from mozc/src/prediction/single_kanji_decoder.cc
class SingleKanjiDecoder(
    private val posMatcher: PosMatcher,
    private val dictionary: SerializedSingleKanjiDictionary,
) {
    fun decode(key: String, autoPartialSuggestion: Boolean = false): List<Result> {
        val results = ArrayList<Result>()
        var lookupKey = key
        var offset = 0
        while (lookupKey.isNotEmpty()) {
            if (!autoPartialSuggestion && lookupKey != key) {
                break
            }
            val kanjiList = dictionary.lookupKanjiEntries(lookupKey)
            if (kanjiList.isNotEmpty()) {
                appendResults(lookupKey, key, kanjiList, offset, results)
                offset += ShorterKeyOffset
                if (results.size > MinSingleKanjiSize) {
                    break
                }
            }
            lookupKey = stripLastChar(lookupKey)
        }
        return results
    }

    private fun appendResults(
        kanjiKey: String,
        originalKey: String,
        kanjiList: List<String>,
        offset: Int,
        results: MutableList<Result>,
    ) {
        kanjiList.forEach { kanji ->
            val consumed = kanjiKey.charsLen()
            results += Result(
                key = kanjiKey,
                value = kanji,
                contentKey = kanjiKey,
                contentValue = kanji,
                attributes = PredictionTypes.SingleKanji or
                    if (kanjiKey.toByteArray(Charsets.UTF_8).size < originalKey.toByteArray(Charsets.UTF_8).size) {
                        PredictionTypes.Prefix
                    } else {
                        0
                    },
                wcost = offset + results.size,
                lid = posMatcher.getGeneralSymbolId(),
                rid = posMatcher.getGeneralSymbolId(),
                consumedKeySize = if (kanjiKey.toByteArray(Charsets.UTF_8).size < originalKey.toByteArray(Charsets.UTF_8).size) consumed else 0,
            )
        }
    }

    companion object {
        private const val MinSingleKanjiSize: Int = 5
        private const val ShorterKeyOffset: Int = 3450

        fun fromMozcDataManager(dataManager: MozcDataManager, posMatcher: PosMatcher): SingleKanjiDecoder =
            SingleKanjiDecoder(
                posMatcher,
                SerializedSingleKanjiDictionary(
                    dataManager.section("single_kanji_token"),
                    dataManager.section("single_kanji_string"),
                    dataManager.section("single_kanji_variant_type"),
                    dataManager.section("single_kanji_variant_token"),
                    dataManager.section("single_kanji_variant_string"),
                    dataManager.section("single_kanji_noun_prefix_token"),
                    dataManager.section("single_kanji_noun_prefix_string"),
                ),
            )

        private fun stripLastChar(key: String): String {
            val codePoints = key.codePoints().toArray()
            if (codePoints.size <= 1) {
                return ""
            }
            return String(codePoints, 0, codePoints.size - 1)
        }
    }
}
