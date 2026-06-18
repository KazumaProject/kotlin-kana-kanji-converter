package mozc_runtime.storage.louds

import java.io.ByteArrayOutputStream

// Ported from mozc/src/storage/louds/bit_stream.*
class BitStream {
    private val bytes = ByteArrayOutputStream()
    private var bitCount: Int = 0

    fun pushBit(bit: Int) {
        require(bit == 0 || bit == 1) { "BitStream accepts only 0 or 1: $bit" }
        val shift = bitCount % 8
        if (shift == 0) {
            bytes.write(0)
        }
        if (bit == 1) {
            val image = bytes.toByteArray()
            image[image.lastIndex] = (image.last().toInt() or (1 shl shift)).toByte()
            bytes.reset()
            bytes.write(image)
        }
        bitCount += 1
    }

    fun fillPadding32() {
        val remainder = bytes.size() % 4
        if (remainder != 0) {
            repeat(4 - remainder) {
                bytes.write(0)
            }
        }
        bitCount = bytes.size() * 8
    }

    fun image(): ByteArray = bytes.toByteArray()

    fun numBits(): Int = bitCount

    fun byteSize(): Int = bytes.size()
}
