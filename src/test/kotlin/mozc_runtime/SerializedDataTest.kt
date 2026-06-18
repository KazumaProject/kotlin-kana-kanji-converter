package mozc_runtime

import mozc_runtime.data.SerializedDictionary
import mozc_runtime.data.SerializedStringArray
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class SerializedDataTest {
    @Test
    fun serializedStringArrayReadsNullTerminatedStrings() {
        val array = SerializedStringArray.from(stringArray("a", "変換", ""))

        assertEquals(3, array.size())
        assertEquals("a", array[0])
        assertEquals("変換", array[1])
        assertEquals("", array[2])
    }

    @Test
    fun serializedStringArrayRejectsOutOfRangeIndex() {
        val array = SerializedStringArray.from(stringArray("a"))

        assertFailsWith<IllegalArgumentException> { array[1] }
    }

    @Test
    fun serializedDictionaryReturnsEqualRangeSortedBySerializedOrder() {
        val strings = stringArray("", "あ", "亜", "説明")
        val tokens = ByteBuffer.allocate(SerializedDictionary.TokenByteLength * 2)
            .order(ByteOrder.LITTLE_ENDIAN)
            .putInt(1).putInt(2).putInt(3).putInt(0).putShort(10).putShort(11).putShort(100).putShort(0)
            .putInt(1).putInt(2).putInt(0).putInt(0).putShort(10).putShort(11).putShort(120).putShort(0)
            .flip() as ByteBuffer

        val dictionary = SerializedDictionary(tokens, strings)
        val range = dictionary.equalRange("あ")

        assertEquals(2, range.size)
        assertEquals("亜", range[0].value)
        assertEquals("説明", range[0].description)
        assertEquals(100, range[0].cost)
        assertEquals(120, range[1].cost)
    }

    private fun stringArray(vararg values: String): ByteBuffer {
        val encoded = values.map { it.toByteArray(Charsets.UTF_8) }
        val headerSize = 4 + values.size * 8
        val totalSize = headerSize + encoded.sumOf { it.size + 1 }
        val buffer = ByteBuffer.allocate(totalSize).order(ByteOrder.LITTLE_ENDIAN)
        buffer.putInt(values.size)
        var offset = headerSize
        encoded.forEach { bytes ->
            buffer.putInt(offset)
            buffer.putInt(bytes.size)
            offset += bytes.size + 1
        }
        encoded.forEach { bytes ->
            buffer.put(bytes)
            buffer.put(0)
        }
        return buffer.flip() as ByteBuffer
    }
}
