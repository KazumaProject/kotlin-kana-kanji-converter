package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryRuleParser
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class CustomZeroQueryParserTest {
    @Test
    fun parsesCustomZeroQueryRules() {
        val parsed = ZeroQueryRuleParser.parse(
            StringReader(
                """
                服を	着る
                靴を	履く,買う
                """.trimIndent()
            ).buffered(),
            "custom",
            rejectDuplicateCandidateForSameTrigger = true,
        )

        assertEquals(listOf("着る"), parsed.getValue("服を").map { it.value })
        assertEquals(listOf("履く", "買う"), parsed.getValue("靴を").map { it.value })
        assertEquals(ZeroQueryType.ZERO_QUERY_NONE, parsed.getValue("服を").first().type)
    }

    @Test
    fun rejectsDuplicateCandidateForSameTriggerInCustomFile() {
        assertFailsWith<IllegalStateException> {
            ZeroQueryRuleParser.parse(
                StringReader(
                    """
                    服を	着る
                    服を	着る
                    """.trimIndent()
                ).buffered(),
                "custom",
                rejectDuplicateCandidateForSameTrigger = true,
            )
        }
    }
}
