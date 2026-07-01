package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryRuleParser
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class ZeroQueryRuleParserTest {
    @Test
    fun parsesRuleFile() {
        val parsed = ZeroQueryRuleParser.parse(
            StringReader(
                """
                # comment

                @	gmail.com
                ありがとう	。,ございます
                """.trimIndent()
            ).buffered(),
            "fixture",
        )

        assertEquals(listOf("gmail.com"), parsed.getValue("@").map { it.value })
        assertEquals(listOf("。", "ございます"), parsed.getValue("ありがとう").map { it.value })
        assertEquals(ZeroQueryType.ZERO_QUERY_NONE, parsed.getValue("ありがとう").first().type)
    }

    @Test
    fun rejectsInvalidRuleRows() {
        assertFailsWith<IllegalStateException> {
            ZeroQueryRuleParser.parse(StringReader("missing-tab\n").buffered(), "fixture")
        }
        assertFailsWith<IllegalStateException> {
            ZeroQueryRuleParser.parse(StringReader("\tvalue\n").buffered(), "fixture")
        }
        assertFailsWith<IllegalStateException> {
            ZeroQueryRuleParser.parse(StringReader("key\t\n").buffered(), "fixture")
        }
    }
}
