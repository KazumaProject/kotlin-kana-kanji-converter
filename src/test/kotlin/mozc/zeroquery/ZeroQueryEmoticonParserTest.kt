package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryEmoticonParser
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class ZeroQueryEmoticonParserTest {
    @Test
    fun parsesCategorizedEmoticonData() {
        val parsed = ZeroQueryEmoticonParser.parse(
            StringReader(
                """
                # value	category	description
                (^^)	SMILE	にこにこ えがお
                """.trimIndent()
            ).buffered(),
            "fixture",
        )

        assertEquals(listOf("(^^)"), parsed.getValue("にこにこ").map { it.value })
        assertEquals(listOf("(^^)"), parsed.getValue("えがお").map { it.value })
        assertEquals(ZeroQueryType.ZERO_QUERY_EMOTICON, parsed.getValue("にこにこ").first().type)
    }

    @Test
    fun rejectsInvalidEmoticonColumnCount() {
        assertFailsWith<IllegalStateException> {
            ZeroQueryEmoticonParser.parse(StringReader("(^^)\tSMILE\n").buffered(), "fixture")
        }
    }
}
