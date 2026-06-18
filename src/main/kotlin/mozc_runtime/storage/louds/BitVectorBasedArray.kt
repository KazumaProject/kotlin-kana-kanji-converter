package mozc_runtime.storage.louds

import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/storage/louds/bit_vector_based_array.*
class BitVectorBasedArray(image: ByteBuffer) {
    private val index = SimpleSuccinctBitVectorIndex()
    private val baseLength: Int
    private val stepLength: Int
    private val data: ByteBuffer

    init {
        val buffer = image.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(buffer.remaining() >= 16) {
            "BitVectorBasedArray header is missing: size=${buffer.remaining()}"
        }
        val indexLength = buffer.getInt()
        baseLength = buffer.getInt()
        stepLength = buffer.getInt()
        val padding = buffer.getInt()
        require(indexLength >= 0) { "BitVectorBasedArray index length is negative: $indexLength" }
        require(baseLength >= 0) { "BitVectorBasedArray base length is negative: $baseLength" }
        require(stepLength >= 0) { "BitVectorBasedArray step length is negative: $stepLength" }
        require(padding == 0) { "BitVectorBasedArray header padding must be zero: $padding" }
        require(buffer.remaining() >= indexLength) {
            "BitVectorBasedArray image is shorter than index: indexLength=$indexLength remaining=${buffer.remaining()}"
        }
        val indexImage = buffer.slice().order(ByteOrder.LITTLE_ENDIAN)
        indexImage.limit(indexLength)
        index.init(indexImage, indexLength)
        buffer.position(buffer.position() + indexLength)
        data = buffer.slice().asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
    }

    fun get(index: Int): ByteBuffer {
        val offsetAndLength = offsetAndLength(index)
        val duplicate = data.asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
        duplicate.position(offsetAndLength.first)
        duplicate.limit(offsetAndLength.first + offsetAndLength.second)
        return duplicate.slice().asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
    }

    fun rawDataFrom(offset: Int): ByteBuffer {
        require(offset in 0..data.remaining()) {
            "BitVectorBasedArray raw offset is out of range: offset=$offset size=${data.remaining()}"
        }
        val duplicate = data.asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
        duplicate.position(offset)
        return duplicate.slice().asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
    }

    fun rawData(): ByteBuffer = data.asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)

    private fun offsetAndLength(arrayIndex: Int): Pair<Int, Int> {
        require(arrayIndex >= 0) { "BitVectorBasedArray index is negative: $arrayIndex" }
        val bitIndex = index.select0(arrayIndex + 1)
        val dataIndex = baseLength * arrayIndex + stepLength * index.rank1(bitIndex)
        var cursor = bitIndex + 1
        while (cursor < index.num0Bits() + index.num1Bits() && index.get(cursor) != 0) {
            cursor += 1
        }
        val length = baseLength + stepLength * (cursor - bitIndex - 1)
        require(dataIndex >= 0 && length >= 0 && dataIndex <= data.remaining() - length) {
            "BitVectorBasedArray element range is out of bounds: index=$arrayIndex offset=$dataIndex length=$length dataSize=${data.remaining()}"
        }
        return dataIndex to length
    }
}
