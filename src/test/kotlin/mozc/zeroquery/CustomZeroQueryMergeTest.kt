package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryEntry
import com.kazumaproject.mozc.zeroquery.ZeroQueryMerger
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import kotlin.test.Test
import kotlin.test.assertEquals

class CustomZeroQueryMergeTest {
    @Test
    fun appendsCustomEntriesAfterOfficialAndRemovesDuplicateCandidate() {
        val official = linkedMapOf(
            "ありがとう" to mutableListOf(
                entry("ありがとう", "。"),
                entry("ありがとう", "ございます"),
            )
        )
        val custom = linkedMapOf(
            "ありがとう" to mutableListOf(
                entry("ありがとう", "ございます"),
                entry("ありがとう", "助かりました"),
            ),
            "服を" to mutableListOf(entry("服を", "着る")),
        )

        ZeroQueryMerger.appendCustom(official, custom)

        assertEquals(listOf("。", "ございます", "助かりました"), official.getValue("ありがとう").map { it.value })
        assertEquals(listOf("着る"), official.getValue("服を").map { it.value })
    }

    private fun entry(key: String, value: String) =
        ZeroQueryEntry(key, value, ZeroQueryType.ZERO_QUERY_NONE)
}
