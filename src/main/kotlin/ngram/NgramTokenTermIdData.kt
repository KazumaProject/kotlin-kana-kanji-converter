package com.kazumaproject.ngram

import com.kazumaproject.dictionary.models.Dictionary
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.util.SortedMap
import kotlin.io.path.createDirectories

data class NgramTokenTermIdBuild(
    val termIdsByTokenPosting: IntArray,
    val uniqueTermCount: Int,
    val buildIdHex: String,
) {
    override fun equals(other: Any?): Boolean {
        return other is NgramTokenTermIdBuild &&
                uniqueTermCount == other.uniqueTermCount &&
                buildIdHex == other.buildIdHex &&
                termIdsByTokenPosting.contentEquals(other.termIdsByTokenPosting)
    }

    override fun hashCode(): Int {
        var result = termIdsByTokenPosting.contentHashCode()
        result = 31 * result + uniqueTermCount
        result = 31 * result + buildIdHex.hashCode()
        return result
    }
}

data class LoadedNgramTokenTermIdData(
    val termIdsByTokenPosting: IntArray,
    val uniqueTermCount: Int,
    val buildIdHex: String,
    val contentChecksumHex: String,
) {
    fun termIdAtPosting(index: Int): Int {
        return termIdsByTokenPosting.getOrElse(index) {
            throw IndexOutOfBoundsException("N-gram termId posting index out of bounds: index=$index size=${termIdsByTokenPosting.size}")
        }
    }
}

object NgramTokenTermIdBuilder {
    fun build(dictionaries: List<Dictionary>): NgramTokenTermIdBuild {
        val sorted = dictionaries.toNgramSystemDictionaryMap()
        val termIdByIdentity = stableTermIds(dictionaries)
        val postingTermIds = IntArray(sorted.values.sumOf { it.size })
        var postingIndex = 0
        sorted.forEach { (reading, entries) ->
            entries.forEach { dictionary ->
                postingTermIds[postingIndex] = termIdByIdentity.getValue(TermIdentity(reading, dictionary.tango))
                postingIndex += 1
            }
        }
        return NgramTokenTermIdBuild(
            termIdsByTokenPosting = postingTermIds,
            uniqueTermCount = termIdByIdentity.size,
            buildIdHex = buildId(termIdByIdentity).toHex(),
        )
    }

    internal fun stableTermIds(dictionaries: List<Dictionary>): Map<TermIdentity, Int> {
        return dictionaries
            .map { TermIdentity(it.yomi, it.tango) }
            .distinct()
            .sortedWith(compareBy<TermIdentity> { it.reading.length }
                .thenBy { it.reading }
                .thenBy { it.surface.length }
                .thenBy { it.surface })
            .mapIndexed { index, identity -> identity to index + 1 }
            .toMap()
    }

    internal fun buildId(termIdByIdentity: Map<TermIdentity, Int>): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update("NTI1-term-id-v1".toByteArray(Charsets.US_ASCII))
        termIdByIdentity.entries
            .sortedBy { it.value }
            .forEach { (identity, termId) ->
                digest.updateInt(termId)
                digest.updateUtf8(identity.reading)
                digest.updateUtf8(identity.surface)
            }
        return digest.digest()
    }
}

class NgramTokenTermIdDataWriter {
    fun write(outputPath: Path, build: NgramTokenTermIdBuild): String {
        outputPath.parent?.createDirectories()
        val writer = NgramTokenTermIdLeWriter()
        writer.writeAscii(TOKEN_TERM_ID_MAGIC)
        writer.writeInt(TOKEN_TERM_ID_VERSION)
        writer.writeInt(build.termIdsByTokenPosting.size)
        writer.writeInt(build.uniqueTermCount)
        writer.writeBytes(build.buildIdHex.hexToBytes())
        writer.writeBytes(ByteArray(SHA_256_BYTES))
        build.termIdsByTokenPosting.forEach(writer::writeInt)
        val bytes = writer.toByteArray()
        val checksum = checksum(bytes)
        checksum.copyInto(bytes, TOKEN_TERM_ID_CHECKSUM_OFFSET)
        Files.write(outputPath, bytes)
        return checksum.toHex()
    }
}

class NgramTokenTermIdDataReader {
    fun read(inputPath: Path, verifyChecksum: Boolean = true): LoadedNgramTokenTermIdData {
        require(Files.isRegularFile(inputPath)) { "N-gram token termId data does not exist: $inputPath" }
        return readBytes(Files.readAllBytes(inputPath), verifyChecksum)
    }

    fun readBytes(bytes: ByteArray, verifyChecksum: Boolean = true): LoadedNgramTokenTermIdData {
        require(bytes.size >= TOKEN_TERM_ID_HEADER_SIZE) { "N-gram token termId data is too small: ${bytes.size}" }
        if (verifyChecksum) {
            val expected = bytes.copyOfRange(TOKEN_TERM_ID_CHECKSUM_OFFSET, TOKEN_TERM_ID_CHECKSUM_OFFSET + SHA_256_BYTES)
            val actualInput = bytes.copyOf()
            actualInput.fill(0, TOKEN_TERM_ID_CHECKSUM_OFFSET, TOKEN_TERM_ID_CHECKSUM_OFFSET + SHA_256_BYTES)
            val actual = checksum(actualInput)
            require(expected.contentEquals(actual)) {
                "N-gram token termId checksum mismatch: expected=${expected.toHex()} actual=${actual.toHex()}"
            }
        }

        val reader = NgramTokenTermIdLeReader(bytes)
        require(reader.readAscii(4) == TOKEN_TERM_ID_MAGIC) { "Invalid N-gram token termId magic" }
        val version = reader.readInt()
        require(version == TOKEN_TERM_ID_VERSION) { "Unsupported N-gram token termId version: $version" }
        val postingCount = reader.readInt()
        val uniqueTermCount = reader.readInt()
        val buildId = reader.readBytes(SHA_256_BYTES)
        val contentChecksum = reader.readBytes(SHA_256_BYTES)
        val expectedSize = TOKEN_TERM_ID_HEADER_SIZE + postingCount * Int.SIZE_BYTES
        require(bytes.size == expectedSize) {
            "Invalid N-gram token termId data size: expected=$expectedSize actual=${bytes.size}"
        }
        return LoadedNgramTokenTermIdData(
            termIdsByTokenPosting = IntArray(postingCount) { reader.readInt() },
            uniqueTermCount = uniqueTermCount,
            buildIdHex = buildId.toHex(),
            contentChecksumHex = contentChecksum.toHex(),
        )
    }
}

object NgramTokenTermIdManifestWriter {
    fun write(outputPath: Path, build: NgramTokenTermIdBuild, contentChecksumHex: String, byteSize: Long) {
        outputPath.parent?.createDirectories()
        Files.writeString(
            outputPath,
            buildString {
                appendLine("{")
                appendLine("  \"format\": \"TOKEN_TERM_ID_POSTING_SIDE_CAR\",")
                appendLine("  \"version\": $TOKEN_TERM_ID_VERSION,")
                appendLine("  \"keyMode\": \"$NGRAM_PRESENCE_KEY_MODE\",")
                appendLine("  \"postingCount\": ${build.termIdsByTokenPosting.size},")
                appendLine("  \"uniqueTermCount\": ${build.uniqueTermCount},")
                appendLine("  \"buildId\": \"${build.buildIdHex}\",")
                appendLine("  \"contentChecksum\": \"$contentChecksumHex\",")
                appendLine("  \"byteSize\": $byteSize")
                appendLine("}")
            },
        )
    }
}

internal data class TermIdentity(
    val reading: String,
    val surface: String,
)

internal fun List<Dictionary>.toNgramSystemDictionaryMap(): SortedMap<String, List<Dictionary>> =
    groupBy(Dictionary::yomi).toSortedMap(compareBy({ it.length }, { it }))

private class NgramTokenTermIdLeWriter {
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

    fun toByteArray(): ByteArray = ByteArray(bytes.size) { bytes[it] }
}

private class NgramTokenTermIdLeReader(private val bytes: ByteArray) {
    private var offset = 0

    fun readAscii(length: Int): String = readBytes(length).toString(Charsets.US_ASCII)

    fun readBytes(length: Int): ByteArray {
        require(offset + length <= bytes.size) { "Unexpected end of N-gram token termId data" }
        return bytes.copyOfRange(offset, offset + length).also { offset += length }
    }

    fun readInt(): Int {
        var result = 0
        repeat(Int.SIZE_BYTES) { shift ->
            result = result or ((bytes[offset++].toInt() and 0xff) shl (shift * 8))
        }
        return result
    }
}

private fun MessageDigest.updateInt(value: Int) {
    update(byteArrayOf(
        (value and 0xff).toByte(),
        ((value ushr 8) and 0xff).toByte(),
        ((value ushr 16) and 0xff).toByte(),
        ((value ushr 24) and 0xff).toByte(),
    ))
}

private fun MessageDigest.updateUtf8(value: String) {
    val bytes = value.toByteArray(Charsets.UTF_8)
    updateInt(bytes.size)
    update(bytes)
}

private fun String.hexToBytes(): ByteArray {
    require(length % 2 == 0) { "Invalid hex length: $length" }
    return ByteArray(length / 2) { index ->
        substring(index * 2, index * 2 + 2).toInt(16).toByte()
    }
}

private fun checksum(bytesWithZeroChecksum: ByteArray): ByteArray =
    MessageDigest.getInstance("SHA-256").digest(bytesWithZeroChecksum)

private const val TOKEN_TERM_ID_MAGIC = "NTI1"
private const val TOKEN_TERM_ID_VERSION = 1
private const val SHA_256_BYTES = 32
private const val TOKEN_TERM_ID_CHECKSUM_OFFSET = 4 + Int.SIZE_BYTES * 3 + SHA_256_BYTES
private const val TOKEN_TERM_ID_HEADER_SIZE = 4 + Int.SIZE_BYTES * 3 + SHA_256_BYTES + SHA_256_BYTES
