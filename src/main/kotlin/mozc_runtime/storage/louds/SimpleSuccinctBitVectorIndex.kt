package mozc_runtime.storage.louds

import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/storage/louds/simple_succinct_bit_vector_index.*
class SimpleSuccinctBitVectorIndex(
    private val chunkSize: Int = DefaultChunkSize,
) {
    private lateinit var data: ByteBuffer
    private var length: Int = 0
    private var cumulativeOnes: IntArray = intArrayOf()

    init {
        require(chunkSize >= 4 && chunkSize.isPowerOfTwo()) {
            "Bit vector chunk size must be a power of two greater than or equal to 4: $chunkSize"
        }
    }

    fun init(data: ByteBuffer, length: Int = data.remaining()) {
        require(length >= 0) { "Bit vector length is negative: $length" }
        require(length % 4 == 0) { "Bit vector length must be aligned to 32 bits: $length" }
        require(data.remaining() >= length) {
            "Bit vector image is shorter than declared length: declared=$length remaining=${data.remaining()}"
        }
        val slice = data.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        slice.limit(length)
        this.data = slice.asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
        this.length = length
        buildIndex()
    }

    fun reset() {
        length = 0
        cumulativeOnes = intArrayOf()
    }

    fun get(index: Int): Int {
        require(index in 0 until length * 8) {
            "Bit index is out of range: index=$index sizeBits=${length * 8}"
        }
        return (data.get(index / 8).toInt() ushr (index % 8)) and 1
    }

    fun rank0(n: Int): Int = n - rank1(n)

    fun rank1(n: Int): Int {
        require(n in 0..length * 8) {
            "Rank position is out of range: n=$n sizeBits=${length * 8}"
        }
        val bitsPerChunk = chunkSize * 8
        val chunk = n / bitsPerChunk
        var result = cumulativeOnes[chunk]
        var offset = chunk * chunkSize
        val fullWordEnd = (n / 32) * 4
        while (offset < fullWordEnd) {
            result += Integer.bitCount(data.getInt(offset))
            offset += 4
        }
        val partialBits = n % 32
        if (partialBits > 0) {
            val wordOffset = (n / 32) * 4
            val shift = 32 - partialBits
            result += Integer.bitCount(data.getInt(wordOffset) shl shift)
        }
        return result
    }

    fun select0(n: Int): Int {
        require(n in 1..num0Bits()) { "Select0 target is out of range: n=$n zeros=${num0Bits()}" }
        var low = 0
        var high = length * 8 - 1
        while (low < high) {
            val mid = (low + high) ushr 1
            if (rank0(mid + 1) >= n) {
                high = mid
            } else {
                low = mid + 1
            }
        }
        return low
    }

    fun select1(n: Int): Int {
        require(n in 1..num1Bits()) { "Select1 target is out of range: n=$n ones=${num1Bits()}" }
        var low = 0
        var high = length * 8 - 1
        while (low < high) {
            val mid = (low + high) ushr 1
            if (rank1(mid + 1) >= n) {
                high = mid
            } else {
                low = mid + 1
            }
        }
        return low
    }

    fun num1Bits(): Int = if (cumulativeOnes.isEmpty()) 0 else cumulativeOnes.last()

    fun num0Bits(): Int = length * 8 - num1Bits()

    private fun buildIndex() {
        val chunks = (length + chunkSize - 1) / chunkSize
        cumulativeOnes = IntArray(chunks + 1)
        var ones = 0
        repeat(chunks) { chunk ->
            cumulativeOnes[chunk] = ones
            var offset = chunk * chunkSize
            val end = minOf(length, offset + chunkSize)
            while (offset < end) {
                ones += Integer.bitCount(data.getInt(offset))
                offset += 4
            }
        }
        cumulativeOnes[chunks] = ones
    }

    private fun Int.isPowerOfTwo(): Boolean = this > 0 && (this and (this - 1)) == 0

    companion object {
        private const val DefaultChunkSize: Int = 32
    }
}
