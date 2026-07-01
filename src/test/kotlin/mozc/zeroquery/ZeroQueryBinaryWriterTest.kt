package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.ZeroQueryBinaryWriter
import com.kazumaproject.mozc.zeroquery.ZeroQueryDict
import com.kazumaproject.mozc.zeroquery.ZeroQueryEntry
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import kotlin.test.Test
import kotlin.test.assertEquals

class ZeroQueryBinaryWriterTest {
    @Test
    fun writesMozcCompatibleTokenArrayAndStringArray() {
        val entries = linkedMapOf(
            "@" to listOf(ZeroQueryEntry("@", "gmail.com", ZeroQueryType.ZERO_QUERY_NONE)),
            "ありがとう" to listOf(
                ZeroQueryEntry("ありがとう", "。", ZeroQueryType.ZERO_QUERY_NONE),
                ZeroQueryEntry("ありがとう", "ございます", ZeroQueryType.ZERO_QUERY_NONE),
            ),
        )

        val binary = ZeroQueryBinaryWriter.toBinary(entries)
        val dict = ZeroQueryDict(binary.tokenBytes, binary.stringBytes)

        assertEquals(3 * 16, binary.tokenBytes.size)
        assertEquals(listOf("gmail.com"), dict.lookup("@").map { it.value })
        assertEquals(listOf("。", "ございます"), dict.lookup("ありがとう").map { it.value })
    }
}
