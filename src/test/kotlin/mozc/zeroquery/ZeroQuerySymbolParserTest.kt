package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQuerySymbolParser
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

class ZeroQuerySymbolParserTest {
    @Test
    fun parsesEmojiSymbolRangeOnly() {
        val parsed = ZeroQuerySymbolParser.parse(
            StringReader(
                """
                POS	CHAR	Reading (space separated)	description	additional description	category	memo	unicode
                記号	☀	てんき はれ	天気	太陽	OTHER
                記号	？？	はてな	疑問符		OTHER
                記号	あ	あ	ひらがな		OTHER
                """.trimIndent()
            ).buffered(),
            "fixture",
        )

        assertEquals(listOf("☀"), parsed.getValue("てんき").map { it.value })
        assertEquals(listOf("☀"), parsed.getValue("天気").map { it.value })
        assertEquals(listOf("☀"), parsed.getValue("太陽").map { it.value })
        assertEquals(ZeroQueryType.ZERO_QUERY_NONE, parsed.getValue("てんき").first().type)
        assertFalse(parsed.containsKey("はてな"))
        assertFalse(parsed.containsKey("ひらがな"))
    }

    @Test
    fun rejectsMissingHeader() {
        assertFailsWith<IllegalStateException> {
            ZeroQuerySymbolParser.parse(StringReader("記号\t☀\tてんき\n").buffered(), "fixture")
        }
    }
}
