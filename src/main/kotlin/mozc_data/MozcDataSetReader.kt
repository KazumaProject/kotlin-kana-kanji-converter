package mozc_data

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

data class MozcDataSet(
    val fileSize: Long,
    val metadataSize: Long,
    val metadataOffset: Long,
    val metadata: DataSetMetadata,
    val storedSha1: ByteArray,
    val computedSha1: ByteArray,
    val sections: Map<String, MozcDataSection>,
) {
    fun requireSection(name: String): MozcDataSection =
        sections[name] ?: error("Missing mozc.data section: $name")

    override fun equals(other: Any?): Boolean =
        other is MozcDataSet &&
            fileSize == other.fileSize &&
            metadataSize == other.metadataSize &&
            metadataOffset == other.metadataOffset &&
            metadata == other.metadata &&
            storedSha1.contentEquals(other.storedSha1) &&
            computedSha1.contentEquals(other.computedSha1) &&
            sections.keys == other.sections.keys

    override fun hashCode(): Int {
        var result = fileSize.hashCode()
        result = 31 * result + metadataSize.hashCode()
        result = 31 * result + metadataOffset.hashCode()
        result = 31 * result + metadata.hashCode()
        result = 31 * result + storedSha1.contentHashCode()
        result = 31 * result + computedSha1.contentHashCode()
        result = 31 * result + sections.keys.hashCode()
        return result
    }
}

class MozcDataSetReader(
    private val magic: ByteArray = MozcDataVersion.Magic,
    private val metadataParser: DataSetMetadataParser = DataSetMetadataParser(),
) {
    fun read(path: Path): MozcDataSet {
        require(Files.isRegularFile(path)) { "mozc.data file does not exist: $path" }
        return read(Files.readAllBytes(path))
    }

    fun read(bytes: ByteArray): MozcDataSet {
        require(bytes.size >= magic.size + MozcDataVersion.FooterSize) {
            "Broken mozc.data: data is too small: actual=${bytes.size}, minimum=${magic.size + MozcDataVersion.FooterSize}"
        }
        require(bytes.copyOfRange(0, magic.size).contentEquals(magic)) {
            "Invalid mozc.data magic: actual=${bytes.copyOfRange(0, magic.size).toHex()}, expected=${magic.toHex()}"
        }

        val actualFileSize = bytes.size.toLong()
        val footerOffset = bytes.size - MozcDataVersion.FooterSize
        val storedFileSize = readBigEndianUInt64(bytes, bytes.size - Long.SIZE_BYTES)
        require(storedFileSize == actualFileSize) {
            "Broken mozc.data: file size mismatch: stored=$storedFileSize actual=$actualFileSize"
        }

        val metadataSize = readBigEndianUInt64(bytes, footerOffset)
        val contentAndMetadataSize = actualFileSize - magic.size - MozcDataVersion.FooterSize
        require(metadataSize > 0) { "Broken mozc.data: metadata size must be positive" }
        require(metadataSize <= contentAndMetadataSize) {
            "Broken mozc.data: metadata exceeds content area: metadataSize=$metadataSize contentAndMetadataSize=$contentAndMetadataSize"
        }
        require(metadataSize <= Int.MAX_VALUE) { "metadata size exceeds supported range: $metadataSize" }

        val metadataOffset = actualFileSize - MozcDataVersion.FooterSize - metadataSize
        require(metadataOffset >= magic.size) {
            "Broken mozc.data: metadata offset is before content: metadataOffset=$metadataOffset"
        }
        val metadataBytes = bytes.copyOfRange(metadataOffset.toInt(), (metadataOffset + metadataSize).toInt())
        val metadata = metadataParser.parse(metadataBytes)
        require(metadata.entries.isNotEmpty()) { "Broken mozc.data: metadata has no entries" }

        val storedSha1 = bytes.copyOfRange(bytes.size - 28, bytes.size - 8)
        val computedSha1 = MessageDigest.getInstance("SHA-1").digest(bytes.copyOfRange(0, bytes.size - 28))
        require(storedSha1.contentEquals(computedSha1)) {
            "Broken mozc.data: SHA1 mismatch: stored=${storedSha1.toHex()} computed=${computedSha1.toHex()}"
        }

        val sections = linkedMapOf<String, MozcDataSection>()
        var previousChunkEnd = magic.size.toLong()
        metadata.entries.forEach { entry ->
            require(entry.name.isNotEmpty()) { "Broken mozc.data: section name is empty" }
            require(entry.name !in sections) { "Broken mozc.data: duplicated section name: ${entry.name}" }
            require(entry.offset >= previousChunkEnd && entry.offset < metadataOffset) {
                "Broken mozc.data: section offset is out of range: name=${entry.name}, offset=${entry.offset}, previousChunkEnd=$previousChunkEnd, metadataOffset=$metadataOffset"
            }
            require(entry.size <= metadataOffset && entry.offset <= metadataOffset - entry.size) {
                "Broken mozc.data: section size exceeds metadata offset: name=${entry.name}, offset=${entry.offset}, size=${entry.size}, metadataOffset=$metadataOffset"
            }
            require(entry.offset % MozcDataVersion.OfficialSectionAlignmentBytes == 0L) {
                "Broken mozc.data: section is not aligned: name=${entry.name}, offset=${entry.offset}, alignment=${MozcDataVersion.OfficialSectionAlignmentBytes}"
            }
            require(entry.offset <= Int.MAX_VALUE && entry.size <= Int.MAX_VALUE) {
                "Section exceeds supported ByteBuffer range: name=${entry.name}, offset=${entry.offset}, size=${entry.size}"
            }
            val duplicate = ByteBuffer.wrap(bytes, entry.offset.toInt(), entry.size.toInt()).slice().asReadOnlyBuffer()
            duplicate.order(ByteOrder.LITTLE_ENDIAN)
            sections[entry.name] = MozcDataSection(entry.name, entry.offset, entry.size, duplicate)
            previousChunkEnd = entry.offset + entry.size
        }

        return MozcDataSet(
            fileSize = actualFileSize,
            metadataSize = metadataSize,
            metadataOffset = metadataOffset,
            metadata = metadata,
            storedSha1 = storedSha1,
            computedSha1 = computedSha1,
            sections = sections.toMap(),
        )
    }

    private fun readBigEndianUInt64(bytes: ByteArray, offset: Int): Long {
        require(offset >= 0 && offset <= bytes.size - Long.SIZE_BYTES) {
            "uint64 read is out of range: offset=$offset size=${bytes.size}"
        }
        var value = 0L
        repeat(Long.SIZE_BYTES) { index ->
            value = (value shl 8) or (bytes[offset + index].toLong() and 0xFFL)
        }
        require(value >= 0) { "uint64 value exceeds signed Long range" }
        return value
    }
}

internal fun ByteArray.toHex(): String = joinToString(separator = "") { "%02X".format(it.toInt() and 0xFF) }
