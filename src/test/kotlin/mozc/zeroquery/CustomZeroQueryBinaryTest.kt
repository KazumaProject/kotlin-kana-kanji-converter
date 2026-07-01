package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryBinaryWriter
import com.kazumaproject.mozc.zeroquery.ZeroQueryDict
import com.kazumaproject.mozc.zeroquery.ZeroQueryEntry
import com.kazumaproject.mozc.zeroquery.ZeroQueryMerger
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import kotlin.test.Test
import kotlin.test.assertTrue

class CustomZeroQueryBinaryTest {
    @Test
    fun customEntryIsIncludedInGeneratedBinary() {
        val official = mapOf(
            "ありがとう" to listOf(entry("ありがとう", "。"))
        )
        val custom = mapOf(
            "服を" to listOf(entry("服を", "着る"))
        )
        val merged = ZeroQueryMerger.mergeWithCustom(
            ruleDict = official,
            emojiDict = emptyMap(),
            emoticonDict = emptyMap(),
            symbolDict = emptyMap(),
            customRuleDict = custom,
        )
        val binary = ZeroQueryBinaryWriter.toBinary(merged)
        val dict = ZeroQueryDict(binary.tokenBytes, binary.stringBytes)

        assertTrue(dict.lookup("服を").map { it.value }.contains("着る"))
    }

    private fun entry(key: String, value: String) =
        ZeroQueryEntry(key, value, ZeroQueryType.ZERO_QUERY_NONE)
}
