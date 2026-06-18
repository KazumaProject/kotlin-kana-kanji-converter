package mozc_data

import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

data class MozcDataSetInputSection(
    val name: String,
    val alignmentBits: Int,
    val data: ByteArray,
)

class MozcDataSetWriter(
    private val magic: ByteArray = MozcDataVersion.Magic,
    private val metadataWriter: DataSetMetadataWriter = DataSetMetadataWriter(),
) {
    fun write(path: Path, sections: List<MozcDataSetInputSection>) {
        path.parent?.let(Files::createDirectories)
        Files.write(path, write(sections))
    }

    fun write(sections: List<MozcDataSetInputSection>): ByteArray {
        require(sections.isNotEmpty()) { "mozc.data must contain at least one section" }
        val seen = mutableSetOf<String>()
        val image = ByteArrayOutputStream()
        image.write(magic)
        val entries = mutableListOf<DataSetMetadata.Entry>()
        sections.forEach { section ->
            require(section.name.isNotEmpty()) { "section name must not be empty" }
            require(seen.add(section.name)) { "duplicated section name: ${section.name}" }
            appendPadding(image, section.alignmentBits)
            entries += DataSetMetadata.Entry(
                name = section.name,
                offset = image.size().toLong(),
                size = section.data.size.toLong(),
            )
            image.write(section.data)
        }
        val metadataBytes = metadataWriter.write(DataSetMetadata(entries))
        image.write(metadataBytes)
        image.writeUInt64(metadataBytes.size.toLong())
        image.write(MessageDigest.getInstance("SHA-1").digest(image.toByteArray()))
        image.writeUInt64(image.size().toLong() + Long.SIZE_BYTES)
        return image.toByteArray()
    }

    private fun appendPadding(image: ByteArrayOutputStream, alignmentBits: Int) {
        require(alignmentBits >= 8 && alignmentBits.isPowerOfTwo()) { "invalid alignment bits: $alignmentBits" }
        val alignmentBytes = alignmentBits / 8
        val remainder = image.size() % alignmentBytes
        if (remainder != 0) {
            repeat(alignmentBytes - remainder) {
                image.write(0)
            }
        }
    }

    private fun Int.isPowerOfTwo(): Boolean = this > 0 && (this and (this - 1)) == 0
}

internal fun ByteArrayOutputStream.writeUInt64(value: Long) {
    require(value >= 0) { "uint64 value exceeds supported range: $value" }
    for (shift in 56 downTo 0 step 8) {
        write(((value ushr shift) and 0xFFL).toInt())
    }
}
