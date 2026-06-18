package mozc_runtime.converter

import mozc_runtime.storage.louds.SimpleSuccinctBitVectorIndex
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/converter/connector.cc
// Ported from mozc/src/converter/connector.h
class Connector(
    connectorData: ByteBuffer,
) {
    val leftSize: Int
    val rightSize: Int
    val resolution: Int

    private val defaultCost: IntArray
    private val rows: Array<Row>

    init {
        val buffer = connectorData.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(buffer.remaining() >= MetadataByteSize) {
            "Connector data header is missing: size=${buffer.remaining()}"
        }

        val magic = buffer.getUnsignedShort(0)
        resolution = buffer.getUnsignedShort(2)
        val rsize = buffer.getUnsignedShort(4)
        val lsize = buffer.getUnsignedShort(6)
        require(magic == ConnectorMagicNumber) {
            "Connector data has unexpected magic number: expected=$ConnectorMagicNumber actual=$magic"
        }
        require(resolution > 0) { "Connector resolution must be positive: $resolution" }
        require(rsize == lsize) { "Connector matrix must be square: rsize=$rsize lsize=$lsize" }

        leftSize = rsize
        rightSize = lsize
        val useOneByteValue = resolution != 1
        val defaultCostArraySize = rsize + (rsize and 1)
        val defaultCostByteSize = defaultCostArraySize * Short.SIZE_BYTES
        var offset = MetadataByteSize
        require(buffer.remaining() >= offset + defaultCostByteSize) {
            "Connector default cost array exceeds data: offset=$offset bytes=$defaultCostByteSize size=${buffer.remaining()}"
        }
        defaultCost = IntArray(defaultCostArraySize) { index ->
            buffer.getUnsignedShort(offset + index * Short.SIZE_BYTES)
        }
        offset += defaultCostByteSize

        val numChunkBits = (lsize + 7) / 8
        val chunkBitsSize = ((numChunkBits + 31) / 32) * Int.SIZE_BYTES
        rows = Array(rsize) { rowIndex ->
            require(buffer.remaining() >= offset + 2 * Short.SIZE_BYTES) {
                "Connector row header exceeds data: row=$rowIndex offset=$offset size=${buffer.remaining()}"
            }
            val compactBitsSize = buffer.getUnsignedShort(offset)
            offset += Short.SIZE_BYTES
            val valuesSize = buffer.getUnsignedShort(offset)
            offset += Short.SIZE_BYTES

            val chunkBits = buffer.sliceAt(offset, chunkBitsSize)
            offset += chunkBitsSize
            val compactBits = buffer.sliceAt(offset, compactBitsSize)
            offset += compactBitsSize
            val values = buffer.sliceAt(offset, valuesSize)
            offset += valuesSize

            Row(
                chunkBits = chunkBits,
                compactBits = compactBits,
                values = values,
                useOneByteValue = useOneByteValue,
            )
        }
        require(offset == buffer.remaining()) {
            "Connector data has trailing or truncated bytes: offset=$offset size=${buffer.remaining()}"
        }
    }

    fun cost(leftId: Int, rightId: Int): Int {
        require(leftId in 0 until leftSize) {
            "Connector left POS id is out of range: leftId=$leftId leftSize=$leftSize"
        }
        require(rightId in 0 until rightSize) {
            "Connector right POS id is out of range: rightId=$rightId rightSize=$rightSize"
        }
        val value = rows[leftId].getValue(rightId)
        return value?.let { it * resolution } ?: defaultCost[leftId]
    }

    private class Row(
        chunkBits: ByteBuffer,
        compactBits: ByteBuffer,
        private val values: ByteBuffer,
        private val useOneByteValue: Boolean,
    ) {
        private val chunkBitsIndex = SimpleSuccinctBitVectorIndex(Int.SIZE_BYTES)
        private val compactBitsIndex = SimpleSuccinctBitVectorIndex(Int.SIZE_BYTES)

        init {
            chunkBitsIndex.init(chunkBits, chunkBits.remaining())
            compactBitsIndex.init(compactBits, compactBits.remaining())
        }

        fun getValue(index: Int): Int? {
            val chunkBitPosition = index / 8
            if (chunkBitsIndex.get(chunkBitPosition) == 0) {
                return null
            }
            val compactBitPosition = chunkBitsIndex.rank1(chunkBitPosition) * 8 + index % 8
            if (compactBitsIndex.get(compactBitPosition) == 0) {
                return null
            }
            val valuePosition = compactBitsIndex.rank1(compactBitPosition)
            return if (useOneByteValue) {
                val value = values.get(valuePosition).toInt() and 0xff
                if (value == InvalidOneByteCostValue) InvalidCost else value
            } else {
                values.getUnsignedShort(valuePosition * Short.SIZE_BYTES)
            }
        }
    }

    companion object {
        const val InvalidCost: Int = 30000

        private const val ConnectorMagicNumber = 0xCDAB
        private const val InvalidOneByteCostValue = 255
        private const val MetadataByteSize = 8
    }
}

private fun ByteBuffer.getUnsignedShort(offset: Int): Int =
    getShort(offset).toInt() and 0xffff

private fun ByteBuffer.sliceAt(offset: Int, byteSize: Int): ByteBuffer {
    require(byteSize >= 0) { "Slice size is negative: $byteSize" }
    require(offset >= 0 && offset <= remaining() - byteSize) {
        "Slice range is out of bounds: offset=$offset size=$byteSize dataSize=${remaining()}"
    }
    val duplicate = asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
    duplicate.position(offset)
    duplicate.limit(offset + byteSize)
    return duplicate.slice().asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
}
