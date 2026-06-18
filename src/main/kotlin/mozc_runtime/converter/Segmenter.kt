package mozc_runtime.converter

import mozc_data.MozcDataManager
import mozc_runtime.dictionary.PosMatcher
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/converter/segmenter.cc
// Ported from mozc/src/converter/segmenter.h
class Segmenter(
    dataManager: MozcDataManager,
    posMatcher: PosMatcher,
) {
    val compressedLeftSize: Int
    val compressedRightSize: Int
    val leftSize: Int
    val rightSize: Int

    private val lTable: IntArray
    private val rTable: IntArray
    private val bitArray: ByteArray
    private val boundaryData: IntArray

    init {
        val sizeInfo = SegmenterSizeInfo.parse(dataManager.segmenterSizeInfo)
        compressedLeftSize = sizeInfo.compressedLeftSize
        compressedRightSize = sizeInfo.compressedRightSize
        lTable = dataManager.segmenterLTable.toUnsignedShortArray("segmenter_ltable")
        rTable = dataManager.segmenterRTable.toUnsignedShortArray("segmenter_rtable")
        bitArray = dataManager.segmenterBitArray.toByteArray()
        boundaryData = dataManager.boundaryData.toUnsignedShortArray("bdry")

        require(lTable.isNotEmpty()) { "Segmenter ltable is empty" }
        require(rTable.isNotEmpty()) { "Segmenter rtable is empty" }
        leftSize = lTable.size - 1
        rightSize = rTable.size - 1
        require(leftSize > 0 && rightSize > 0) {
            "Segmenter original table sizes must be positive: leftSize=$leftSize rightSize=$rightSize"
        }
        require(boundaryData.size >= maxOf(leftSize, rightSize) * 2) {
            "Boundary data is too small: boundaryShorts=${boundaryData.size} leftSize=$leftSize rightSize=$rightSize"
        }
        require(compressedLeftSize > 0 && compressedRightSize > 0) {
            "Segmenter compressed sizes must be positive: l=$compressedLeftSize r=$compressedRightSize"
        }
        require(compressedLeftSize * compressedRightSize <= bitArray.size * 8) {
            "Segmenter bitarray is too small: compressedLeftSize=$compressedLeftSize compressedRightSize=$compressedRightSize bitBytes=${bitArray.size}"
        }
        require(lTable.all { it in 0 until compressedLeftSize }) {
            "Segmenter ltable contains compressed id outside size=$compressedLeftSize"
        }
        require(rTable.all { it in 0 until compressedRightSize }) {
            "Segmenter rtable contains compressed id outside size=$compressedRightSize"
        }
        require(posMatcher.getUnknownId() in 0 until rightSize) {
            "POS matcher data is not aligned with segmenter table: unknownId=${posMatcher.getUnknownId()} rightSize=$rightSize"
        }
    }

    fun getBoundaryType(
        leftPosId: Int,
        rightPosId: Int,
    ): BoundaryType =
        if (isBoundary(leftPosId, rightPosId)) BoundaryType.BOUNDARY else BoundaryType.NO_BOUNDARY

    fun isBoundary(
        leftPosId: Int,
        rightPosId: Int,
        boundaryType: BoundaryType,
    ): Boolean = getBoundaryType(leftPosId, rightPosId) == boundaryType

    fun isBoundary(
        leftNode: Node,
        rightNode: Node,
        isSingleSegment: Boolean,
    ): Boolean {
        if (leftNode.nodeType == Node.NodeType.BOS_NODE || rightNode.nodeType == Node.NodeType.EOS_NODE) {
            return true
        }
        if (isSingleSegment) {
            return false
        }
        if (leftNode.attributes and Node.Attributes.STARTS_WITH_PARTICLE != 0) {
            return false
        }
        return isBoundary(leftNode.rid, rightNode.lid)
    }

    fun isBoundary(leftPosId: Int, rightPosId: Int): Boolean {
        require(leftPosId in 0 until leftSize) {
            "Segmenter left POS id is out of range: leftPosId=$leftPosId leftSize=$leftSize"
        }
        require(rightPosId in 0 until rightSize) {
            "Segmenter right POS id is out of range: rightPosId=$rightPosId rightSize=$rightSize"
        }
        val bitIndex = lTable[leftPosId] + compressedLeftSize * rTable[rightPosId]
        return bitArray.getBit(bitIndex)
    }

    fun getPrefixPenalty(lid: Int): Int {
        require(lid in 0 until rightSize) {
            "Segmenter prefix penalty lid is out of range: lid=$lid rightSize=$rightSize"
        }
        return boundaryData[2 * lid]
    }

    fun getSuffixPenalty(rid: Int): Int {
        require(rid in 0 until leftSize) {
            "Segmenter suffix penalty rid is out of range: rid=$rid leftSize=$leftSize"
        }
        return boundaryData[2 * rid + 1]
    }
}

enum class BoundaryType {
    NO_BOUNDARY,
    BOUNDARY,
}

private data class SegmenterSizeInfo(
    val compressedLeftSize: Int,
    val compressedRightSize: Int,
) {
    companion object {
        fun parse(source: ByteBuffer): SegmenterSizeInfo {
            val buffer = source.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            var left: Long? = null
            var right: Long? = null
            while (buffer.hasRemaining()) {
                val tag = buffer.readVarint()
                val fieldNumber = (tag ushr 3).toInt()
                val wireType = (tag and 0x07).toInt()
                when (fieldNumber) {
                    1 -> {
                        require(wireType == VarintWireType) {
                            "Segmenter compressed_lsize has unsupported wire type: $wireType"
                        }
                        left = buffer.readVarint()
                    }
                    2 -> {
                        require(wireType == VarintWireType) {
                            "Segmenter compressed_rsize has unsupported wire type: $wireType"
                        }
                        right = buffer.readVarint()
                    }
                    else -> buffer.skipProtoField(wireType)
                }
            }
            val leftSize = left ?: error("Segmenter size info is missing compressed_lsize")
            val rightSize = right ?: error("Segmenter size info is missing compressed_rsize")
            require(leftSize in 1..Int.MAX_VALUE.toLong()) {
                "Segmenter compressed_lsize is out of range: $leftSize"
            }
            require(rightSize in 1..Int.MAX_VALUE.toLong()) {
                "Segmenter compressed_rsize is out of range: $rightSize"
            }
            return SegmenterSizeInfo(leftSize.toInt(), rightSize.toInt())
        }
    }
}

private const val VarintWireType: Int = 0
private const val Fixed64WireType: Int = 1
private const val LengthDelimitedWireType: Int = 2
private const val Fixed32WireType: Int = 5

private fun ByteBuffer.readVarint(): Long {
    var shift = 0
    var result = 0L
    while (shift < 64) {
        require(hasRemaining()) { "Truncated protobuf varint" }
        val byte = get().toInt() and 0xff
        result = result or ((byte and 0x7f).toLong() shl shift)
        if (byte and 0x80 == 0) {
            return result
        }
        shift += 7
    }
    error("Protobuf varint exceeds uint64")
}

private fun ByteBuffer.skipProtoField(wireType: Int) {
    when (wireType) {
        VarintWireType -> readVarint()
        Fixed64WireType -> {
            require(remaining() >= Long.SIZE_BYTES) { "Truncated protobuf fixed64 field" }
            position(position() + Long.SIZE_BYTES)
        }
        LengthDelimitedWireType -> {
            val length = readVarint()
            require(length in 0..remaining().toLong()) {
                "Length-delimited protobuf field is out of range: length=$length remaining=${remaining()}"
            }
            position(position() + length.toInt())
        }
        Fixed32WireType -> {
            require(remaining() >= Int.SIZE_BYTES) { "Truncated protobuf fixed32 field" }
            position(position() + Int.SIZE_BYTES)
        }
        else -> error("Unsupported protobuf wire type: $wireType")
    }
}

private fun ByteBuffer.toUnsignedShortArray(name: String): IntArray {
    val buffer = asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    require(buffer.remaining() % Short.SIZE_BYTES == 0) {
        "$name size must be divisible by 2: size=${buffer.remaining()}"
    }
    return IntArray(buffer.remaining() / Short.SIZE_BYTES) { index ->
        buffer.getShort(index * Short.SIZE_BYTES).toInt() and 0xffff
    }
}

private fun ByteBuffer.toByteArray(): ByteArray {
    val buffer = asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    val bytes = ByteArray(buffer.remaining())
    buffer.get(bytes)
    return bytes
}

private fun ByteArray.getBit(index: Int): Boolean {
    require(index in 0 until size * 8) {
        "Bit index is out of range: index=$index bitSize=${size * 8}"
    }
    return ((this[index ushr 3].toInt() ushr (index and 0x07)) and 1) != 0
}
