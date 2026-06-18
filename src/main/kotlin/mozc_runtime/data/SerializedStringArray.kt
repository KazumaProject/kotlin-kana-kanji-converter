package mozc_runtime.data

import java.nio.ByteBuffer
import java.nio.ByteOrder

class SerializedStringArray private constructor(
    private val data: ByteBuffer,
    private val size: Int,
) : Iterable<String> {
    operator fun get(index: Int): String {
        require(index in 0 until size) { "SerializedStringArray index out of range: index=$index size=$size" }
        val offset = entryOffset(index)
        val length = entryLength(index)
        val duplicate = data.asReadOnlyBuffer()
        duplicate.position(offset)
        duplicate.limit(offset + length)
        val bytes = ByteArray(length)
        duplicate.get(bytes)
        return bytes.toString(Charsets.UTF_8)
    }

    fun size(): Int = size

    fun verify() {
        verifyData(data.asReadOnlyBuffer())
    }

    override fun iterator(): Iterator<String> = object : Iterator<String> {
        private var index = 0

        override fun hasNext(): Boolean = index < size

        override fun next(): String = get(index++)
    }

    private fun entryOffset(index: Int): Int = data.getInt(4 + index * 8)

    private fun entryLength(index: Int): Int = data.getInt(4 + index * 8 + 4)

    companion object {
        fun from(buffer: ByteBuffer): SerializedStringArray {
            val data = buffer.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            val size = verifyData(data.asReadOnlyBuffer())
            return SerializedStringArray(data, size)
        }

        fun verifyData(buffer: ByteBuffer): Int {
            val data = buffer.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(data.remaining() >= Int.SIZE_BYTES) { "SerializedStringArray size header is missing" }
            val base = 0
            val totalSize = data.remaining()
            val size = data.getInt(base)
            require(size >= 0) { "SerializedStringArray size is negative: $size" }
            val headerSize = Int.SIZE_BYTES + size * 2 * Int.SIZE_BYTES
            require(totalSize >= headerSize) {
                "SerializedStringArray data is too small: required=$headerSize actual=$totalSize"
            }
            var previousEnd = headerSize
            repeat(size) { index ->
                val offset = data.getInt(base + Int.SIZE_BYTES + index * 8)
                val length = data.getInt(base + Int.SIZE_BYTES + index * 8 + Int.SIZE_BYTES)
                require(offset >= previousEnd) {
                    "SerializedStringArray offset is out of order: index=$index offset=$offset previousEnd=$previousEnd"
                }
                require(length >= 0) { "SerializedStringArray length is negative: index=$index length=$length" }
                require(length < totalSize && offset <= totalSize - length) {
                    "SerializedStringArray range is out of bounds: index=$index offset=$offset length=$length totalSize=$totalSize"
                }
                require(offset + length < totalSize) {
                    "SerializedStringArray terminator is out of bounds: index=$index offset=$offset length=$length totalSize=$totalSize"
                }
                require(data.get(base + offset + length).toInt() == 0) {
                    "SerializedStringArray string is not null-terminated: index=$index"
                }
                previousEnd = offset + length + 1
            }
            return size
        }
    }
}
