package mozc_runtime.prediction

import mozc_data.MozcDataManager
import mozc_runtime.data.SerializedZeroQueryDictionary
import mozc_runtime.data.ZeroQueryType

// Ported from mozc/src/prediction/zero_query_dict.h
class ZeroQueryDict(
    private val dictionary: SerializedZeroQueryDictionary,
) {
    fun lookup(context: String, lid: Int = 0, rid: Int = 0): List<Result> {
        val entries = dictionary.equalRange(context)
        if (entries.isEmpty()) {
            return listOf()
        }
        val keyIsOneCharAndNotKanji = context.codePointCount(0, context.length) == 1 &&
            context.codePoints().noneMatch { it in 0x4E00..0x9FFF }
        val results = ArrayList<Result>()
        var cost = 0
        entries.forEach { entry ->
            if (entry.type == ZeroQueryType.EMOJI && keyIsOneCharAndNotKanji) {
                return@forEach
            }
            results += Result(
                key = entry.value,
                value = entry.value,
                contentKey = entry.value,
                contentValue = entry.value,
                attributes = PredictionTypes.Suffix,
                wcost = cost,
                lid = lid,
                rid = rid,
            )
            cost += SuffixPenalty
        }
        return results
    }

    companion object {
        private const val SuffixPenalty: Int = 10

        fun fromMozcDataManager(dataManager: MozcDataManager): ZeroQueryDict =
            ZeroQueryDict(
                SerializedZeroQueryDictionary(
                    dataManager.section("zero_query_token_array"),
                    dataManager.section("zero_query_string_array"),
                ),
            )

        fun numberFromMozcDataManager(dataManager: MozcDataManager): ZeroQueryDict =
            ZeroQueryDict(
                SerializedZeroQueryDictionary(
                    dataManager.section("zero_query_number_token_array"),
                    dataManager.section("zero_query_number_string_array"),
                ),
            )
    }
}
