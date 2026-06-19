package mozc_runtime.prediction

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale

// Ported from mozc/src/prediction/suggestion_filter.h
// Ported from mozc/src/prediction/suggestion_filter.cc
class SuggestionFilter private constructor(
    private val bitSize: Int,
    private val expectedElements: Int,
    private val hashCount: Int,
    private val fingerprintType: Int,
    private val words: IntArray,
) {
    fun isBadSuggestion(text: String): Boolean {
        var hash = when (fingerprintType) {
            LegacyFingerprint -> legacyFingerprint(text.lowercase(Locale.ROOT).toByteArray(Charsets.UTF_8))
            CityFingerprint -> CityHash.cityHash64(text.lowercase(Locale.ROOT).toByteArray(Charsets.UTF_8))
            else -> error("Unsupported suggestion filter fingerprint type: $fingerprintType")
        }
        repeat(hashCount) {
            hash = java.lang.Long.rotateLeft(hash, 8)
            val index = java.lang.Long.remainderUnsigned(hash, bitSize.toLong()).toInt()
            if (!bit(index)) {
                return false
            }
        }
        return true
    }

    private fun bit(index: Int): Boolean {
        require(index in 0 until bitSize) {
            "Suggestion filter bit index out of range: index=$index bitSize=$bitSize"
        }
        val word = index ushr 5
        val bit = index and 31
        return ((words[word] ushr bit) and 1) != 0
    }

    companion object {
        private const val HeaderWords: Int = 3
        private const val LegacyFingerprint: Int = 0
        private const val CityFingerprint: Int = 1

        fun from(data: ByteBuffer): SuggestionFilter {
            val buffer = data.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(buffer.remaining() % Int.SIZE_BYTES == 0) {
                "Suggestion filter section size must be divisible by 4: size=${buffer.remaining()}"
            }
            val wordCount = buffer.remaining() / Int.SIZE_BYTES
            require(wordCount >= HeaderWords) {
                "Suggestion filter header is missing: words=$wordCount"
            }
            val bitSize = buffer.getInt(0)
            val expectedElements = buffer.getInt(4)
            val hashAndType = buffer.getInt(8)
            val hashCount = hashAndType and 0xffff
            val fingerprintType = hashAndType ushr 16
            require(bitSize > 0) { "Suggestion filter bit size must be positive: $bitSize" }
            require(expectedElements >= 0) { "Suggestion filter expected elements is negative: $expectedElements" }
            require(hashCount in 1..7) { "Suggestion filter hash count is out of range: $hashCount" }
            require(fingerprintType == LegacyFingerprint || fingerprintType == CityFingerprint) {
                "Suggestion filter fingerprint type is unsupported: $fingerprintType"
            }
            val requiredWords = (bitSize + 31) ushr 5
            require(wordCount - HeaderWords >= requiredWords) {
                "Suggestion filter bitmap is truncated: requiredWords=$requiredWords actualWords=${wordCount - HeaderWords}"
            }
            val words = IntArray(requiredWords) { index ->
                buffer.getInt((HeaderWords + index) * Int.SIZE_BYTES)
            }
            return SuggestionFilter(bitSize, expectedElements, hashCount, fingerprintType, words)
        }

        val None: SuggestionFilter =
            SuggestionFilter(bitSize = 1, expectedElements = 0, hashCount = 1, fingerprintType = LegacyFingerprint, words = intArrayOf(0))

        private fun legacyFingerprint(bytes: ByteArray): Long {
            val high = legacyFingerprint32WithSeed(bytes, 0x6d6f)
            val low = legacyFingerprint32WithSeed(bytes, 0x7a63)
            var result = (high.toLong() shl 32) or (low.toLong() and 0xffffffffL)
            if (high == 0 && low < 2) {
                result = result xor 0x130f9bef94a0a928UL.toLong()
            }
            return result
        }

        private fun legacyFingerprint32WithSeed(bytes: ByteArray, seed: Int): Int {
            var a = 0x9e3779b9.toInt()
            var b = a
            var c = seed
            var offset = 0
            var remaining = bytes.size
            while (remaining >= 12) {
                a += toUInt32(bytes, offset)
                b += toUInt32(bytes, offset + 4)
                c += toUInt32(bytes, offset + 8)
                val mixed = mix(a, b, c)
                a = mixed.first
                b = mixed.second
                c = mixed.third
                offset += 12
                remaining -= 12
            }
            c += bytes.size
            when (remaining) {
                11 -> c += (bytes[offset + 10].toInt() and 0xff) shl 24
            }
            if (remaining >= 10) c += (bytes[offset + 9].toInt() and 0xff) shl 16
            if (remaining >= 9) c += (bytes[offset + 8].toInt() and 0xff) shl 8
            if (remaining >= 8) b += (bytes[offset + 7].toInt() and 0xff) shl 24
            if (remaining >= 7) b += (bytes[offset + 6].toInt() and 0xff) shl 16
            if (remaining >= 6) b += (bytes[offset + 5].toInt() and 0xff) shl 8
            if (remaining >= 5) b += bytes[offset + 4].toInt() and 0xff
            if (remaining >= 4) a += (bytes[offset + 3].toInt() and 0xff) shl 24
            if (remaining >= 3) a += (bytes[offset + 2].toInt() and 0xff) shl 16
            if (remaining >= 2) a += (bytes[offset + 1].toInt() and 0xff) shl 8
            if (remaining >= 1) a += bytes[offset].toInt() and 0xff
            return mix(a, b, c).third
        }

        private fun mix(a0: Int, b0: Int, c0: Int): Triple<Int, Int, Int> {
            var a = a0
            var b = b0
            var c = c0
            a -= b; a -= c; a = a xor (c ushr 13)
            b -= c; b -= a; b = b xor (a shl 8)
            c -= a; c -= b; c = c xor (b ushr 13)
            a -= b; a -= c; a = a xor (c ushr 12)
            b -= c; b -= a; b = b xor (a shl 16)
            c -= a; c -= b; c = c xor (b ushr 5)
            a -= b; a -= c; a = a xor (c ushr 3)
            b -= c; b -= a; b = b xor (a shl 10)
            c -= a; c -= b; c = c xor (b ushr 15)
            return Triple(a, b, c)
        }

        private fun toUInt32(bytes: ByteArray, offset: Int): Int =
            (bytes[offset].toInt() and 0xff) or
                ((bytes[offset + 1].toInt() and 0xff) shl 8) or
                ((bytes[offset + 2].toInt() and 0xff) shl 16) or
                ((bytes[offset + 3].toInt() and 0xff) shl 24)
    }
}

private object CityHash {
    private const val K0: Long = -4348849565147123417L
    private const val K1: Long = -5435081209227447693L
    private const val K2: Long = -7286425919675154353L

    fun cityHash64(bytes: ByteArray): Long {
        val length = bytes.size
        if (length <= 16) return hashLen0to16(bytes)
        if (length <= 32) return hashLen17to32(bytes)
        if (length <= 64) return hashLen33to64(bytes)

        var x = fetch64(bytes, length - 40)
        var y = fetch64(bytes, length - 16) + fetch64(bytes, length - 56)
        var z = hashLen16(fetch64(bytes, length - 48) + length.toLong(), fetch64(bytes, length - 24))
        var v = weakHashLen32WithSeeds(bytes, length - 64, length.toLong(), z)
        var w = weakHashLen32WithSeeds(bytes, length - 32, y + K1, x)
        x = x * K1 + fetch64(bytes, 0)

        var offset = 0
        var remaining = (length - 1) and 63.inv()
        do {
            x = java.lang.Long.rotateRight(x + y + v.first + fetch64(bytes, offset + 8), 37) * K1
            y = java.lang.Long.rotateRight(y + v.second + fetch64(bytes, offset + 48), 42) * K1
            x = x xor w.second
            y += v.first + fetch64(bytes, offset + 40)
            z = java.lang.Long.rotateRight(z + w.first, 33) * K1
            v = weakHashLen32WithSeeds(bytes, offset, v.second * K1, x + w.first)
            w = weakHashLen32WithSeeds(bytes, offset + 32, z + w.second, y + fetch64(bytes, offset + 16))
            val tmp = z
            z = x
            x = tmp
            offset += 64
            remaining -= 64
        } while (remaining != 0)

        return hashLen16(
            hashLen16(v.first, w.first) + shiftMix(y) * K1 + z,
            hashLen16(v.second, w.second) + x,
        )
    }

    private fun hashLen0to16(bytes: ByteArray): Long {
        val length = bytes.size
        if (length >= 8) {
            val mul = K2 + length * 2L
            val a = fetch64(bytes, 0) + K2
            val b = fetch64(bytes, length - 8)
            val c = java.lang.Long.rotateRight(b, 37) * mul + a
            val d = (java.lang.Long.rotateRight(a, 25) + b) * mul
            return hashLen16(c, d, mul)
        }
        if (length >= 4) {
            val mul = K2 + length * 2L
            val a = fetch32(bytes, 0).toLong() and 0xffffffffL
            return hashLen16(length + (a shl 3), fetch32(bytes, length - 4).toLong() and 0xffffffffL, mul)
        }
        if (length > 0) {
            val a = bytes[0].toInt() and 0xff
            val b = bytes[length shr 1].toInt() and 0xff
            val c = bytes[length - 1].toInt() and 0xff
            val y = a + (b shl 8)
            val z = length + (c shl 2)
            return shiftMix(y.toLong() * K2 xor z.toLong() * K0) * K2
        }
        return K2
    }

    private fun hashLen17to32(bytes: ByteArray): Long {
        val length = bytes.size
        val mul = K2 + length * 2L
        val a = fetch64(bytes, 0) * K1
        val b = fetch64(bytes, 8)
        val c = fetch64(bytes, length - 8) * mul
        val d = fetch64(bytes, length - 16) * K2
        return hashLen16(
            java.lang.Long.rotateRight(a + b, 43) + java.lang.Long.rotateRight(c, 30) + d,
            a + java.lang.Long.rotateRight(b + K2, 18) + c,
            mul,
        )
    }

    private fun hashLen33to64(bytes: ByteArray): Long {
        val length = bytes.size
        val mul = K2 + length * 2L
        val a = fetch64(bytes, 0) * K2
        val b = fetch64(bytes, 8)
        val c = fetch64(bytes, length - 24)
        val d = fetch64(bytes, length - 32)
        val e = fetch64(bytes, 16) * K2
        val f = fetch64(bytes, 24) * 9
        val g = fetch64(bytes, length - 8)
        val h = fetch64(bytes, length - 16) * mul
        val u = java.lang.Long.rotateRight(a + g, 43) + (java.lang.Long.rotateRight(b, 30) + c) * 9
        val v = (a + g xor d) + f + 1
        val w = java.lang.Long.reverseBytes((u + v) * mul) + h
        val x = java.lang.Long.rotateRight(e + f, 42) + c
        val y = (java.lang.Long.reverseBytes((v + w) * mul) + g) * mul
        val z = e + f + c
        val a2 = java.lang.Long.reverseBytes((x + z) * mul + y) + b
        val b2 = shiftMix((z + a2) * mul + d + h) * mul
        return b2 + x
    }

    private fun weakHashLen32WithSeeds(bytes: ByteArray, offset: Int, seedA: Long, seedB: Long): Pair<Long, Long> {
        val w = fetch64(bytes, offset)
        val x = fetch64(bytes, offset + 8)
        val y = fetch64(bytes, offset + 16)
        val z = fetch64(bytes, offset + 24)
        var a = seedA + w
        var b = java.lang.Long.rotateRight(seedB + a + z, 21)
        val c = a
        a += x + y
        b += java.lang.Long.rotateRight(a, 44)
        return Pair(a + z, b + c)
    }

    private fun hashLen16(u: Long, v: Long): Long = hashLen16(u, v, -7070675565921424023L)

    private fun hashLen16(u: Long, v: Long, mul: Long): Long {
        var a = (u xor v) * mul
        a = a xor (a ushr 47)
        var b = (v xor a) * mul
        b = b xor (b ushr 47)
        b *= mul
        return b
    }

    private fun shiftMix(value: Long): Long = value xor (value ushr 47)

    private fun fetch64(bytes: ByteArray, offset: Int): Long =
        (bytes[offset].toLong() and 0xffL) or
            ((bytes[offset + 1].toLong() and 0xffL) shl 8) or
            ((bytes[offset + 2].toLong() and 0xffL) shl 16) or
            ((bytes[offset + 3].toLong() and 0xffL) shl 24) or
            ((bytes[offset + 4].toLong() and 0xffL) shl 32) or
            ((bytes[offset + 5].toLong() and 0xffL) shl 40) or
            ((bytes[offset + 6].toLong() and 0xffL) shl 48) or
            ((bytes[offset + 7].toLong() and 0xffL) shl 56)

    private fun fetch32(bytes: ByteArray, offset: Int): Int =
        (bytes[offset].toInt() and 0xff) or
            ((bytes[offset + 1].toInt() and 0xff) shl 8) or
            ((bytes[offset + 2].toInt() and 0xff) shl 16) or
            ((bytes[offset + 3].toInt() and 0xff) shl 24)
}
