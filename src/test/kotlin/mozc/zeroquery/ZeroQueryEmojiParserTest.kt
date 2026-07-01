package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryEmojiParser
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class ZeroQueryEmojiParserTest {
    @Test
    fun parsesEmojiReadingsAndDescriptions() {
        val parsed = ZeroQueryEmojiParser.parse(
            StringReader(
                """
                # codepoints	emoji	readings	unicode name	japanese name	descriptions	version
                1F601	😁	かお	GRINNING FACE	笑顔1（スマイル）	顔/スマイル2	15
                1F600	😀	かお	GRINNING FACE	笑顔2	顔	15
                """.trimIndent()
            ).buffered(),
            "fixture",
        )

        assertEquals(listOf("😀", "😁"), parsed.getValue("かお").map { it.value })
        assertEquals(ZeroQueryType.ZERO_QUERY_EMOJI, parsed.getValue("かお").first().type)
        assertTrue(parsed.getValue("笑顔").map { it.value }.containsAll(listOf("😀", "😁")))
        assertTrue(parsed.getValue("スマイル").map { it.value }.contains("😁"))
    }

    @Test
    fun rejectsInvalidEmojiColumnCount() {
        assertFailsWith<IllegalStateException> {
            ZeroQueryEmojiParser.parse(StringReader("too\tfew\n").buffered(), "fixture")
        }
    }
}
