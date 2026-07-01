package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryNumberParser
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class ZeroQueryNumberParserTest {
    @Test
    fun parsesNumberSuffixRules() {
        val parsed = ZeroQueryNumberParser.parse(
            StringReader(
                """
                default	年
                12	月
                """.trimIndent()
            ).buffered(),
            "fixture",
        )

        assertEquals(listOf("年"), parsed.getValue("default").map { it.value })
        assertEquals(listOf("月"), parsed.getValue("12").map { it.value })
        assertEquals(ZeroQueryType.ZERO_QUERY_NUMBER_SUFFIX, parsed.getValue("12").first().type)
    }

    @Test
    fun rejectsMissingDefaultKey() {
        assertFailsWith<IllegalStateException> {
            ZeroQueryNumberParser.parse(StringReader("12\t月\n").buffered(), "fixture")
        }
    }
}
