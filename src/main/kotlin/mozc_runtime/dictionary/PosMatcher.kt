package mozc_runtime.dictionary

import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/dictionary/pos_matcher.*
class PosMatcher(
    data: ByteBuffer,
) {
    private val ids: IntArray

    init {
        val buffer = data.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(buffer.remaining() % Short.SIZE_BYTES == 0) {
            "POS matcher data size must be divisible by 2: size=${buffer.remaining()}"
        }
        ids = IntArray(buffer.remaining() / Short.SIZE_BYTES) { index ->
            buffer.getShort(index * Short.SIZE_BYTES).toInt() and 0xffff
        }
        require(ids.isNotEmpty()) { "POS matcher data must contain at least one id" }
    }

    fun idAt(index: Int): Int {
        require(index in ids.indices) { "POS matcher index is out of range: index=$index size=${ids.size}" }
        return ids[index]
    }

    fun size(): Int = ids.size

    fun contains(posId: Int): Boolean = ids.contains(posId)
}
