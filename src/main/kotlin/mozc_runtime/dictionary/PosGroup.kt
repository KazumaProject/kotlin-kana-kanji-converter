package mozc_runtime.dictionary

import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/dictionary/pos_group.h
class PosGroup(
    data: ByteBuffer,
) {
    private val groups: ByteArray

    init {
        val buffer = data.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(buffer.remaining() > 0) { "POS group data is empty" }
        groups = ByteArray(buffer.remaining())
        buffer.get(groups)
    }

    fun getPosGroup(lid: Int): Int {
        require(lid in groups.indices) {
            "POS group lid is out of range: lid=$lid size=${groups.size}"
        }
        return groups[lid].toInt() and 0xff
    }

    fun size(): Int = groups.size
}
