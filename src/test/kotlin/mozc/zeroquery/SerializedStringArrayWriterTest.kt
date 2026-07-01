package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.SerializedStringArrayReader
import com.kazumaproject.mozc.zeroquery.SerializedStringArrayWriter
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class SerializedStringArrayWriterTest {
    @Test
    fun serializesAndReadsMozcSerializedStringArray() {
        val strings = listOf("", "a", "あ", "ありがとう")

        val bytes = SerializedStringArrayWriter.toByteArray(strings)
        val restored = SerializedStringArrayReader.read(bytes)

        assertEquals(strings, restored)
        assertEquals(4, readUInt32LE(bytes, 0))
        assertEquals(36, readUInt32LE(bytes, 4))
        assertEquals(0, readUInt32LE(bytes, 8))
        assertEquals(37, readUInt32LE(bytes, 12))
        assertEquals(1, readUInt32LE(bytes, 16))
        strings.indices.forEach { index ->
            val offset = readUInt32LE(bytes, 4 + index * 8)
            val length = readUInt32LE(bytes, 4 + index * 8 + 4)
            assertEquals(0, bytes[offset + length].toInt(), "missing null terminator at index=$index")
        }
    }

    @Test
    fun rejectsInvalidStringArray() {
        val bytes = SerializedStringArrayWriter.toByteArray(listOf("a", "b")).toMutableList()
        bytes[4 + 4] = 100.toByte()

        assertFailsWith<IllegalStateException> {
            SerializedStringArrayReader.read(bytes.toByteArray())
        }
    }

    private fun readUInt32LE(bytes: ByteArray, offset: Int): Int =
        (bytes[offset].toInt() and 0xff) or
                ((bytes[offset + 1].toInt() and 0xff) shl 8) or
                ((bytes[offset + 2].toInt() and 0xff) shl 16) or
                ((bytes[offset + 3].toInt() and 0xff) shl 24)
}
