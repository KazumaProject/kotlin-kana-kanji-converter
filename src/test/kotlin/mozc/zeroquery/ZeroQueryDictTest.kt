package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.SerializedStringArrayWriter
import com.kazumaproject.mozc.zeroquery.ZeroQueryDict
import com.kazumaproject.mozc.zeroquery.ZeroQueryType
import java.io.ByteArrayOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class ZeroQueryDictTest {
    @Test
    fun lookupUsesSortedTokenArray() {
        val strings = listOf("a", "b", "x", "y")
        val tokenBytes = token(0, 2, ZeroQueryType.ZERO_QUERY_NONE.code) +
                token(0, 3, ZeroQueryType.ZERO_QUERY_EMOJI.code) +
                token(1, 2, ZeroQueryType.ZERO_QUERY_EMOTICON.code)
        val dict = ZeroQueryDict(tokenBytes, SerializedStringArrayWriter.toByteArray(strings))

        assertEquals(listOf("x", "y"), dict.lookup("a").map { it.value })
        assertEquals(listOf(ZeroQueryType.ZERO_QUERY_NONE, ZeroQueryType.ZERO_QUERY_EMOJI), dict.lookup("a").map { it.type })
        assertEquals(emptyList(), dict.lookup("missing"))
    }

    @Test
    fun rejectsMalformedTokenArray() {
        val strings = SerializedStringArrayWriter.toByteArray(listOf("a", "x"))

        assertFailsWith<IllegalStateException> {
            ZeroQueryDict(ByteArray(15), strings)
        }
        assertFailsWith<IllegalStateException> {
            ZeroQueryDict(token(99, 1, 0), strings)
        }
        assertFailsWith<IllegalStateException> {
            ZeroQueryDict(token(0, 1, 9), strings)
        }
    }

    @Test
    fun rejectsUnsortedTokenArray() {
        val strings = SerializedStringArrayWriter.toByteArray(listOf("a", "b", "x"))
        val tokenBytes = token(1, 2, 0) + token(0, 2, 0)

        assertFailsWith<IllegalStateException> {
            ZeroQueryDict(tokenBytes, strings)
        }
    }

    private fun token(keyIndex: Int, valueIndex: Int, type: Int): ByteArray =
        ByteArrayOutputStream().use { output ->
            output.writeUInt32LE(keyIndex)
            output.writeUInt32LE(valueIndex)
            output.writeUInt16LE(type)
            output.writeUInt16LE(0)
            output.writeUInt32LE(0)
            output.toByteArray()
        }

    private fun ByteArrayOutputStream.writeUInt32LE(value: Int) {
        write(value and 0xff)
        write((value ushr 8) and 0xff)
        write((value ushr 16) and 0xff)
        write((value ushr 24) and 0xff)
    }

    private fun ByteArrayOutputStream.writeUInt16LE(value: Int) {
        write(value and 0xff)
        write((value ushr 8) and 0xff)
    }
}
