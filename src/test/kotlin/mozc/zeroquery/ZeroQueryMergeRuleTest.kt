package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryEntry
import com.kazumaproject.mozc.zeroquery.ZeroQueryMerger
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

class ZeroQueryMergeRuleTest {
    @Test
    fun mergesOfficialSourcesInMozcOrderWithDerivedFilters() {
        val rule = mapOf(
            "@" to listOf(entry("@", "gmail.com")),
            "ありがとう" to listOf(entry("ありがとう", "。")),
        )
        val emoji = mapOf(
            "ascii" to listOf(entry("ascii", "😀", ZeroQueryType.ZERO_QUERY_EMOJI)),
            "顔" to listOf(
                entry("顔", "😀", ZeroQueryType.ZERO_QUERY_EMOJI),
                entry("顔", "😁", ZeroQueryType.ZERO_QUERY_EMOJI),
                entry("顔", "😂", ZeroQueryType.ZERO_QUERY_EMOJI),
                entry("顔", "😃", ZeroQueryType.ZERO_QUERY_EMOJI),
            ),
            "ありがとう" to listOf(entry("ありがとう", "😀", ZeroQueryType.ZERO_QUERY_EMOJI)),
        )
        val emoticon = mapOf(
            "ありがとう" to listOf(
                entry("ありがとう", "(1)", ZeroQueryType.ZERO_QUERY_EMOTICON),
                entry("ありがとう", "(2)", ZeroQueryType.ZERO_QUERY_EMOTICON),
                entry("ありがとう", "(3)", ZeroQueryType.ZERO_QUERY_EMOTICON),
                entry("ありがとう", "(4)", ZeroQueryType.ZERO_QUERY_EMOTICON),
            )
        )
        val symbol = mapOf(
            "ありがとう" to listOf(entry("ありがとう", "☀")),
            "記号" to listOf(entry("記号", "☀"), entry("記号", "☁"), entry("記号", "☂"), entry("記号", "☃")),
        )

        val merged = ZeroQueryMerger.mergeOfficial(rule, emoji, emoticon, symbol)

        assertEquals(listOf("gmail.com"), merged.getValue("@").map { it.value })
        assertEquals(listOf("。", "😀", "(1)", "(2)", "(3)", "☀"), merged.getValue("ありがとう").map { it.value })
        assertFalse(merged.containsKey("ascii"))
        assertFalse(merged.containsKey("顔"))
        assertFalse(merged.containsKey("記号"))
    }

    private fun entry(
        key: String,
        value: String,
        type: ZeroQueryType = ZeroQueryType.ZERO_QUERY_NONE,
    ) = ZeroQueryEntry(key, value, type)
}
