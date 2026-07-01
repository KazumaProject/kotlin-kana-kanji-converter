package com.kazumaproject.ngram

import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.io.path.createDirectories

interface BinaryNgramPresenceDictionary {
    fun contains1(a: Long): Boolean
    fun contains2(a: Long, b: Long): Boolean
    fun contains3(a: Long, b: Long, c: Long): Boolean
    fun contains4(a: Long, b: Long, c: Long, d: Long): Boolean
    fun contains5(a: Long, b: Long, c: Long, d: Long, e: Long): Boolean
}

object EmptyBinaryNgramPresenceDictionary : BinaryNgramPresenceDictionary {
    override fun contains1(a: Long): Boolean = false
    override fun contains2(a: Long, b: Long): Boolean = false
    override fun contains3(a: Long, b: Long, c: Long): Boolean = false
    override fun contains4(a: Long, b: Long, c: Long, d: Long): Boolean = false
    override fun contains5(a: Long, b: Long, c: Long, d: Long, e: Long): Boolean = false
}

data class NgramPresenceWriteResult(
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val sectionPayloadByteSizes: Map<Int, Long>,
)

class NgramPresenceDataWriter {
    fun write(outputPath: Path, sections: List<BdzSectionBuild>): NgramPresenceWriteResult {
        require(sections.size == NGRAM_SECTION_COUNT) {
            "Expected $NGRAM_SECTION_COUNT sections, actual=${sections.size}"
        }
        require(sections.map { it.order } == (1..NGRAM_SECTION_COUNT).toList()) {
            "Sections must be ordered 1..$NGRAM_SECTION_COUNT"
        }
        outputPath.parent?.createDirectories()
        val dictionaryBuildId = dictionaryBuildId(sections)
        val bytes = toByteArray(sections, dictionaryBuildId)
        Files.write(outputPath, bytes)
        return NgramPresenceWriteResult(
            dictionaryBuildIdHex = dictionaryBuildId.toHex(),
            contentChecksumHex = bytes.copyOfRange(CONTENT_CHECKSUM_OFFSET, CONTENT_CHECKSUM_OFFSET + SHA_256_BYTES).toHex(),
            sectionPayloadByteSizes = sections.associate { it.order to it.binaryPayloadByteSize },
        )
    }

    fun toByteArray(sections: List<BdzSectionBuild>, dictionaryBuildId: ByteArray = dictionaryBuildId(sections)): ByteArray {
        require(dictionaryBuildId.size == SHA_256_BYTES)
        val layouts = layoutSections(sections)
        val writer = LeByteWriter()
        writer.writeAscii(MAGIC)
        writer.writeInt(NGRAM_PRESENCE_VERSION)
        writer.writeInt(NGRAM_PRESENCE_FORMAT_ID)
        writer.writeInt(NGRAM_PRESENCE_KEY_MODE_ID)
        writer.writeInt(NGRAM_SECTION_COUNT)
        writer.writeBytes(dictionaryBuildId)
        writer.writeBytes(ByteArray(SHA_256_BYTES))

        sections.forEachIndexed { index, section ->
            val layout = layouts[index]
            writer.writeInt(section.order)
            writer.writeInt(section.entryCount)
            writer.writeInt(section.vertexCount)
            writer.writeLong(section.seed0)
            writer.writeLong(section.seed1)
            writer.writeLong(section.seed2)
            layout.blobs.forEach { blob ->
                writer.writeLong(blob.offset)
                writer.writeLong(blob.length)
            }
        }

        layouts.forEach { layout ->
            layout.payloads.forEach(writer::writeBytes)
        }

        val bytes = writer.toByteArray()
        check(bytes.size.toLong() == layouts.last().endOffset) {
            "Unexpected binary size: actual=${bytes.size} expected=${layouts.last().endOffset}"
        }
        val checksum = contentChecksum(bytes)
        checksum.copyInto(bytes, CONTENT_CHECKSUM_OFFSET)
        return bytes
    }

    private fun layoutSections(sections: List<BdzSectionBuild>): List<SectionLayout> {
        var offset = HEADER_SIZE + SECTION_TABLE_ENTRY_SIZE * NGRAM_SECTION_COUNT.toLong()
        return sections.map { section ->
            val payloads = mutableListOf<ByteArray>()
            payloads += section.g.toByteArray()
            payloads += section.usedVertices.toBitByteArray()
            payloads += section.usedVertices.rankLarge.toLittleEndianBytes()
            payloads += section.usedVertices.rankSmall.toLittleEndianBytes()
            for (keyIndex in 0 until NGRAM_SECTION_COUNT) {
                payloads += section.keyArrays.getOrNull(keyIndex)?.toLittleEndianBytes() ?: ByteArray(0)
            }
            val blobs = payloads.map { payload ->
                BlobLayout(offset = offset, length = payload.size.toLong()).also {
                    offset += payload.size
                }
            }
            SectionLayout(blobs = blobs, payloads = payloads, endOffset = offset)
        }
    }

    private fun dictionaryBuildId(sections: List<BdzSectionBuild>): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update("NGP1-build-v1".toByteArray(Charsets.US_ASCII))
        sections.sortedBy { it.order }.forEach { section ->
            digest.updateInt(section.order)
            digest.updateInt(section.entryCount)
            section.keyArrays.forEach { keys ->
                keys.forEach { digest.updateLong(it) }
            }
        }
        return digest.digest()
    }

    private data class BlobLayout(val offset: Long, val length: Long)

    private data class SectionLayout(
        val blobs: List<BlobLayout>,
        val payloads: List<ByteArray>,
        val endOffset: Long,
    )
}

class NgramPresenceDataReader {
    fun read(inputPath: Path, verifyChecksum: Boolean = true): LoadedNgramPresenceDictionary {
        require(Files.isRegularFile(inputPath)) { "N-gram presence data does not exist: $inputPath" }
        return readBytes(Files.readAllBytes(inputPath), verifyChecksum)
    }

    fun readBytes(bytes: ByteArray, verifyChecksum: Boolean = true): LoadedNgramPresenceDictionary {
        require(bytes.size >= HEADER_SIZE) { "N-gram presence data is too small: ${bytes.size}" }
        if (verifyChecksum) {
            val expected = bytes.copyOfRange(CONTENT_CHECKSUM_OFFSET, CONTENT_CHECKSUM_OFFSET + SHA_256_BYTES)
            val actualInput = bytes.copyOf()
            actualInput.fill(0, CONTENT_CHECKSUM_OFFSET, CONTENT_CHECKSUM_OFFSET + SHA_256_BYTES)
            val actual = contentChecksum(actualInput)
            require(expected.contentEquals(actual)) {
                "N-gram presence data checksum mismatch: expected=${expected.toHex()} actual=${actual.toHex()}"
            }
        }

        val reader = LeByteReader(bytes)
        require(reader.readAscii(4) == MAGIC) { "Invalid N-gram presence magic" }
        val version = reader.readInt()
        val format = reader.readInt()
        val keyMode = reader.readInt()
        val sectionCount = reader.readInt()
        require(version == NGRAM_PRESENCE_VERSION) { "Unsupported N-gram presence version: $version" }
        require(format == NGRAM_PRESENCE_FORMAT_ID) { "Unsupported N-gram presence format: $format" }
        require(keyMode == NGRAM_PRESENCE_KEY_MODE_ID) { "Unsupported N-gram presence key mode: $keyMode" }
        require(sectionCount == NGRAM_SECTION_COUNT) { "Unsupported N-gram section count: $sectionCount" }
        val dictionaryBuildId = reader.readBytes(SHA_256_BYTES)
        val contentChecksum = reader.readBytes(SHA_256_BYTES)

        val sections = arrayOfNulls<NgramPresenceSection>(NGRAM_SECTION_COUNT + 1)
        repeat(sectionCount) {
            val order = reader.readInt()
            val entryCount = reader.readInt()
            val vertexCount = reader.readInt()
            val seed0 = reader.readLong()
            val seed1 = reader.readLong()
            val seed2 = reader.readLong()
            val blobs = List(BLOB_COUNT_PER_SECTION) {
                BlobRef(offset = reader.readLong(), length = reader.readLong())
            }
            val gBytes = bytes.slice(blobs[0])
            val usedBytes = bytes.slice(blobs[1])
            val rankLarge = bytes.slice(blobs[2]).toIntArrayLittleEndian()
            val rankSmall = bytes.slice(blobs[3]).toShortArrayLittleEndian()
            val keyArrays = (0 until NGRAM_SECTION_COUNT).map { keyIndex ->
                bytes.slice(blobs[4 + keyIndex]).toLongArrayLittleEndian()
            }
            val usedVertices = RankBitVector(
                bitCount = vertexCount,
                bitBytes = usedBytes,
                rankLarge = rankLarge,
                rankSmall = rankSmall,
            )
            sections[order] = NgramPresenceSection(
                order = order,
                entryCount = entryCount,
                vertexCount = vertexCount,
                retryCount = 0,
                seed0 = seed0,
                seed1 = seed1,
                seed2 = seed2,
                g = TwoBitArray.fromByteArray(vertexCount, gBytes),
                usedVertices = usedVertices,
                keyA = keyArrays[0],
                keyB = keyArrays[1],
                keyC = keyArrays[2],
                keyD = keyArrays[3],
                keyE = keyArrays[4],
            )
        }

        return LoadedNgramPresenceDictionary(
            sections = sections,
            dictionaryBuildIdHex = dictionaryBuildId.toHex(),
            contentChecksumHex = contentChecksum.toHex(),
            byteSize = bytes.size.toLong(),
        )
    }
}

class LoadedNgramPresenceDictionary(
    private val sections: Array<NgramPresenceSection?>,
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
) : BinaryNgramPresenceDictionary {
    override fun contains1(a: Long): Boolean = sections[1]?.contains(a, 0L, 0L, 0L, 0L) ?: false
    override fun contains2(a: Long, b: Long): Boolean = sections[2]?.contains(a, b, 0L, 0L, 0L) ?: false
    override fun contains3(a: Long, b: Long, c: Long): Boolean = sections[3]?.contains(a, b, c, 0L, 0L) ?: false
    override fun contains4(a: Long, b: Long, c: Long, d: Long): Boolean = sections[4]?.contains(a, b, c, d, 0L) ?: false
    override fun contains5(a: Long, b: Long, c: Long, d: Long, e: Long): Boolean = sections[5]?.contains(a, b, c, d, e) ?: false

    fun section(order: Int): NgramPresenceSection? = sections.getOrNull(order)
}

class NgramPresenceSection(
    val order: Int,
    val entryCount: Int,
    val vertexCount: Int,
    val retryCount: Int,
    private val seed0: Long,
    private val seed1: Long,
    private val seed2: Long,
    private val g: TwoBitArray,
    private val usedVertices: RankBitVector,
    private val keyA: LongArray,
    private val keyB: LongArray,
    private val keyC: LongArray,
    private val keyD: LongArray,
    private val keyE: LongArray,
) {
    fun contains(a: Long, b: Long, c: Long, d: Long, e: Long): Boolean {
        val index = index(a, b, c, d, e)
        if (index !in 0 until entryCount) {
            return false
        }
        if (keyA[index] != a) return false
        if (order >= 2 && keyB[index] != b) return false
        if (order >= 3 && keyC[index] != c) return false
        if (order >= 4 && keyD[index] != d) return false
        if (order >= 5 && keyE[index] != e) return false
        return true
    }

    internal fun index(a: Long, b: Long, c: Long, d: Long, e: Long): Int {
        return BdzRuntime.index(order, a, b, c, d, e, vertexCount, seed0, seed1, seed2, g, usedVertices)
    }
}

private data class BlobRef(val offset: Long, val length: Long)

private fun ByteArray.slice(blob: BlobRef): ByteArray {
    require(blob.offset >= 0 && blob.length >= 0 && blob.offset + blob.length <= size) {
        "Invalid N-gram blob bounds: offset=${blob.offset} length=${blob.length} size=$size"
    }
    return copyOfRange(blob.offset.toInt(), (blob.offset + blob.length).toInt())
}

private class LeByteWriter {
    private val bytes = ArrayList<Byte>()

    fun writeAscii(value: String) {
        writeBytes(value.toByteArray(Charsets.US_ASCII))
    }

    fun writeBytes(value: ByteArray) {
        value.forEach { bytes += it }
    }

    fun writeInt(value: Int) {
        repeat(Int.SIZE_BYTES) { shift ->
            bytes += ((value ushr (shift * 8)) and 0xff).toByte()
        }
    }

    fun writeLong(value: Long) {
        repeat(Long.SIZE_BYTES) { shift ->
            bytes += ((value ushr (shift * 8)) and 0xff).toByte()
        }
    }

    fun toByteArray(): ByteArray = ByteArray(bytes.size) { bytes[it] }
}

private class LeByteReader(private val bytes: ByteArray) {
    private var offset = 0

    fun readAscii(length: Int): String = readBytes(length).toString(Charsets.US_ASCII)

    fun readBytes(length: Int): ByteArray {
        require(offset + length <= bytes.size) { "Unexpected end of N-gram binary" }
        return bytes.copyOfRange(offset, offset + length).also { offset += length }
    }

    fun readInt(): Int {
        var result = 0
        repeat(Int.SIZE_BYTES) { shift ->
            result = result or ((bytes[offset++].toInt() and 0xff) shl (shift * 8))
        }
        return result
    }

    fun readLong(): Long {
        var result = 0L
        repeat(Long.SIZE_BYTES) { shift ->
            result = result or ((bytes[offset++].toLong() and 0xffL) shl (shift * 8))
        }
        return result
    }
}

private fun IntArray.toLittleEndianBytes(): ByteArray {
    val writer = LeByteWriter()
    forEach(writer::writeInt)
    return writer.toByteArray()
}

private fun ShortArray.toLittleEndianBytes(): ByteArray {
    val writer = LeByteWriter()
    forEach { value -> writer.writeInt(value.toInt() and 0xffff) }
    val intBytes = writer.toByteArray()
    val result = ByteArray(size * Short.SIZE_BYTES)
    for (index in indices) {
        result[index * 2] = intBytes[index * 4]
        result[index * 2 + 1] = intBytes[index * 4 + 1]
    }
    return result
}

private fun LongArray.toLittleEndianBytes(): ByteArray {
    val writer = LeByteWriter()
    forEach(writer::writeLong)
    return writer.toByteArray()
}

private fun ByteArray.toIntArrayLittleEndian(): IntArray {
    require(size % Int.SIZE_BYTES == 0) { "Invalid IntArray byte size: $size" }
    val reader = LeByteReader(this)
    return IntArray(size / Int.SIZE_BYTES) { reader.readInt() }
}

private fun ByteArray.toShortArrayLittleEndian(): ShortArray {
    require(size % Short.SIZE_BYTES == 0) { "Invalid ShortArray byte size: $size" }
    val result = ShortArray(size / Short.SIZE_BYTES)
    for (index in result.indices) {
        result[index] = (((this[index * 2].toInt() and 0xff) or ((this[index * 2 + 1].toInt() and 0xff) shl 8))).toShort()
    }
    return result
}

private fun ByteArray.toLongArrayLittleEndian(): LongArray {
    require(size % Long.SIZE_BYTES == 0) { "Invalid LongArray byte size: $size" }
    val reader = LeByteReader(this)
    return LongArray(size / Long.SIZE_BYTES) { reader.readLong() }
}

private fun MessageDigest.updateInt(value: Int) {
    update(byteArrayOf(
        (value and 0xff).toByte(),
        ((value ushr 8) and 0xff).toByte(),
        ((value ushr 16) and 0xff).toByte(),
        ((value ushr 24) and 0xff).toByte(),
    ))
}

private fun MessageDigest.updateLong(value: Long) {
    val bytes = ByteArray(Long.SIZE_BYTES)
    repeat(Long.SIZE_BYTES) { shift ->
        bytes[shift] = ((value ushr (shift * 8)) and 0xff).toByte()
    }
    update(bytes)
}

fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }

private fun contentChecksum(bytesWithZeroChecksum: ByteArray): ByteArray {
    return MessageDigest.getInstance("SHA-256").digest(bytesWithZeroChecksum)
}

private const val MAGIC = "NGP1"
private const val SHA_256_BYTES = 32
private const val CONTENT_CHECKSUM_OFFSET = 4 + Int.SIZE_BYTES * 4 + SHA_256_BYTES
private const val HEADER_SIZE = 4 + Int.SIZE_BYTES * 4 + SHA_256_BYTES + SHA_256_BYTES
private const val BLOB_COUNT_PER_SECTION = 9
private const val SECTION_TABLE_ENTRY_SIZE =
    Int.SIZE_BYTES * 3L + Long.SIZE_BYTES * 3L + BLOB_COUNT_PER_SECTION * Long.SIZE_BYTES * 2L
