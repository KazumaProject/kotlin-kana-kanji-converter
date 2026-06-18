package mozc_runtime.dictionary.file

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/dictionary/file/codec.cc
class DictionaryFileCodec {
    private var seed: Int = DefaultSeed

    fun readSections(image: ByteBuffer): List<DictionaryFileSection> {
        val data = image.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(data.remaining() >= 12) {
            "Dictionary file image is too small: actual=${data.remaining()} minimum=12"
        }
        val magic = data.getInt()
        require(magic == FileMagic) {
            "Invalid dictionary file magic: expected=$FileMagic actual=$magic"
        }
        seed = data.getInt()
        val sections = ArrayList<DictionaryFileSection>()
        var sectionIndex = 0
        while (true) {
            require(data.remaining() >= Int.SIZE_BYTES) {
                "Dictionary file section $sectionIndex is missing data size"
            }
            val dataSize = data.getInt()
            if (dataSize == 0) {
                break
            }
            require(dataSize > 0) {
                "Dictionary file section $sectionIndex has invalid data size: $dataSize"
            }
            val paddedDataSize = roundUp4(dataSize)
            require(data.remaining() >= FingerprintByteLength + paddedDataSize) {
                "Dictionary file section $sectionIndex exceeds image: dataSize=$dataSize paddedDataSize=$paddedDataSize remaining=${data.remaining()}"
            }
            val encodedName = ByteArray(FingerprintByteLength)
            data.get(encodedName)
            val sectionOffset = data.position()
            val limit = data.limit()
            data.limit(sectionOffset + dataSize)
            val sectionData = data.slice().asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN)
            data.limit(limit)
            data.position(sectionOffset + paddedDataSize)
            sections += DictionaryFileSection(encodedName, sectionOffset, dataSize, sectionData)
            sectionIndex += 1
        }
        require(!data.hasRemaining()) {
            "Dictionary file has trailing bytes: remaining=${data.remaining()}"
        }
        return sections
    }

    fun getSectionName(name: String): ByteArray =
        legacyFingerprintWithSeed(name.toByteArray(Charsets.UTF_8), seed).toLittleEndianBytes()

    fun writeSections(sections: List<Pair<String, ByteArray>>): ByteArray {
        val out = ByteArrayOutputStream()
        out.writeInt32(FileMagic)
        out.writeInt32(seed)
        val ordered = if (sections.size == 4) listOf(sections[0], sections[2], sections[1], sections[3]) else sections
        ordered.forEach { (name, bytes) ->
            val encodedName = getSectionName(name)
            out.writeInt32(bytes.size)
            out.write(encodedName)
            out.write(bytes)
            repeat(roundUp4(bytes.size) - bytes.size) {
                out.write(0)
            }
        }
        out.writeInt32(0)
        return out.toByteArray()
    }

    private fun ByteArrayOutputStream.writeInt32(value: Int) {
        write(value and 0xff)
        write((value ushr 8) and 0xff)
        write((value ushr 16) and 0xff)
        write((value ushr 24) and 0xff)
    }

    private fun roundUp4(length: Int): Int {
        val remainder = length % 4
        return length + ((4 - remainder) % 4)
    }

    private fun legacyFingerprintWithSeed(bytes: ByteArray, seed: Int): Long {
        val hi = legacyFingerprint32WithSeed(bytes, seed.toLong() and UIntMask)
        val lo = legacyFingerprint32WithSeed(bytes, FingerprintSeed1.toLong())
        var result = (hi shl 32) or lo
        if (hi == 0L && lo < 2L) {
            result = result xor 0x130f9bef94a0a928UL.toLong()
        }
        return result
    }

    private fun legacyFingerprint32WithSeed(bytes: ByteArray, seed: Long): Long {
        val originalSize = bytes.size
        var index = 0
        var remaining = bytes.size
        var a = 0x9e3779b9L
        var b = a
        var c = seed and UIntMask
        while (remaining >= 12) {
            a = (a + toUInt32(bytes, index)) and UIntMask
            b = (b + toUInt32(bytes, index + 4)) and UIntMask
            c = (c + toUInt32(bytes, index + 8)) and UIntMask
            val mixed = mix(a, b, c)
            a = mixed[0]
            b = mixed[1]
            c = mixed[2]
            index += 12
            remaining -= 12
        }
        c = (c + originalSize) and UIntMask
        when (remaining) {
            11 -> {
                c = (c + ((bytes[index + 10].toLong() and 0xffL) shl 24)) and UIntMask
                c = (c + ((bytes[index + 9].toLong() and 0xffL) shl 16)) and UIntMask
                c = (c + ((bytes[index + 8].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + ((bytes[index + 7].toLong() and 0xffL) shl 24)) and UIntMask
                b = (b + ((bytes[index + 6].toLong() and 0xffL) shl 16)) and UIntMask
                b = (b + ((bytes[index + 5].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            10 -> {
                c = (c + ((bytes[index + 9].toLong() and 0xffL) shl 16)) and UIntMask
                c = (c + ((bytes[index + 8].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + ((bytes[index + 7].toLong() and 0xffL) shl 24)) and UIntMask
                b = (b + ((bytes[index + 6].toLong() and 0xffL) shl 16)) and UIntMask
                b = (b + ((bytes[index + 5].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            9 -> {
                c = (c + ((bytes[index + 8].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + ((bytes[index + 7].toLong() and 0xffL) shl 24)) and UIntMask
                b = (b + ((bytes[index + 6].toLong() and 0xffL) shl 16)) and UIntMask
                b = (b + ((bytes[index + 5].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            8 -> {
                b = (b + ((bytes[index + 7].toLong() and 0xffL) shl 24)) and UIntMask
                b = (b + ((bytes[index + 6].toLong() and 0xffL) shl 16)) and UIntMask
                b = (b + ((bytes[index + 5].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            7 -> {
                b = (b + ((bytes[index + 6].toLong() and 0xffL) shl 16)) and UIntMask
                b = (b + ((bytes[index + 5].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            6 -> {
                b = (b + ((bytes[index + 5].toLong() and 0xffL) shl 8)) and UIntMask
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            5 -> {
                b = (b + (bytes[index + 4].toLong() and 0xffL)) and UIntMask
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            4 -> {
                a = (a + ((bytes[index + 3].toLong() and 0xffL) shl 24)) and UIntMask
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            3 -> {
                a = (a + ((bytes[index + 2].toLong() and 0xffL) shl 16)) and UIntMask
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            2 -> {
                a = (a + ((bytes[index + 1].toLong() and 0xffL) shl 8)) and UIntMask
                a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
            }
            1 -> a = (a + (bytes[index].toLong() and 0xffL)) and UIntMask
        }
        return mix(a, b, c)[2]
    }

    private fun toUInt32(bytes: ByteArray, offset: Int): Long =
        (bytes[offset].toLong() and 0xffL) or
            ((bytes[offset + 1].toLong() and 0xffL) shl 8) or
            ((bytes[offset + 2].toLong() and 0xffL) shl 16) or
            ((bytes[offset + 3].toLong() and 0xffL) shl 24)

    private fun mix(a0: Long, b0: Long, c0: Long): LongArray {
        var a = a0
        var b = b0
        var c = c0
        a = (a - b - c) and UIntMask
        a = (a xor (c ushr 13)) and UIntMask
        b = (b - c - a) and UIntMask
        b = (b xor ((a shl 8) and UIntMask)) and UIntMask
        c = (c - a - b) and UIntMask
        c = (c xor (b ushr 13)) and UIntMask
        a = (a - b - c) and UIntMask
        a = (a xor (c ushr 12)) and UIntMask
        b = (b - c - a) and UIntMask
        b = (b xor ((a shl 16) and UIntMask)) and UIntMask
        c = (c - a - b) and UIntMask
        c = (c xor (b ushr 5)) and UIntMask
        a = (a - b - c) and UIntMask
        a = (a xor (c ushr 3)) and UIntMask
        b = (b - c - a) and UIntMask
        b = (b xor ((a shl 10) and UIntMask)) and UIntMask
        c = (c - a - b) and UIntMask
        c = (c xor (b ushr 15)) and UIntMask
        return longArrayOf(a, b, c)
    }

    private fun Long.toLittleEndianBytes(): ByteArray {
        val out = ByteArray(FingerprintByteLength)
        repeat(FingerprintByteLength) { index ->
            out[index] = ((this ushr (index * 8)) and 0xffL).toByte()
        }
        return out
    }

    companion object {
        const val FingerprintByteLength: Int = 8
        private const val FileMagic: Int = 20110701
        private const val DefaultSeed: Int = 2135654146
        private const val FingerprintSeed1: Int = 0x7a63
        private const val UIntMask: Long = 0xffffffffL
    }
}
