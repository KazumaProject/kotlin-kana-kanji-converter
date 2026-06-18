package mozc_data

import java.io.ByteArrayOutputStream
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MozcDataSetReaderTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun readsRoundTripDataSetAndCreatesSectionMap() {
        val bytes = MozcDataSetWriter().write(
            listOf(
                MozcDataSetInputSection("dict", 32, "dictionary".toByteArray()),
                MozcDataSetInputSection("version", 32, "oss-test".toByteArray()),
            )
        )

        val dataSet = MozcDataSetReader().read(bytes)

        assertEquals(bytes.size.toLong(), dataSet.fileSize)
        assertEquals(listOf("dict", "version"), dataSet.sections.keys.toList())
        assertEquals(8L, dataSet.sections.getValue("dict").offset)
        assertTrue(dataSet.sections.getValue("dict").data.isReadOnly)
        assertEquals(ByteOrder.LITTLE_ENDIAN, dataSet.sections.getValue("dict").data.order())
        assertEquals("oss-test", dataSet.requireSection("version").data.toUtf8String())
    }

    @Test
    fun rejectsInvalidMagic() {
        val bytes = validDataSet().clone()
        bytes[0] = 0

        val error = assertFailsWith<IllegalArgumentException> { MozcDataSetReader().read(bytes) }
        assertTrue(error.message!!.contains("Invalid mozc.data magic"))
    }

    @Test
    fun rejectsFooterFileSizeMismatch() {
        val bytes = validDataSet()
        bytes[bytes.lastIndex] = (bytes[bytes.lastIndex].toInt() xor 0x01).toByte()

        val error = assertFailsWith<IllegalArgumentException> { MozcDataSetReader().read(bytes) }
        assertTrue(error.message!!.contains("file size mismatch"))
    }

    @Test
    fun rejectsMetadataRangeOutsideContent() {
        val bytes = malformedDataSet(
            DataSetMetadata(
                listOf(DataSetMetadata.Entry(name = "bad", offset = 6, size = 1))
            )
        )

        val error = assertFailsWith<IllegalArgumentException> { MozcDataSetReader().read(bytes) }
        assertTrue(error.message!!.contains("section offset is out of range"))
    }

    @Test
    fun readsOfficialMozcDataWhenGenerated() {
        val path = repoRoot.resolve("build/generated/mozc-data/mozc.data")
        assertTrue(Files.isRegularFile(path), "Missing official mozc.data. Run ./gradlew generateOfficialMozcData first: $path")

        val dataSet = MozcDataSetReader().read(path)

        assertTrue(dataSet.sections.containsKey("dict"))
        assertTrue(dataSet.sections.containsKey("version"))
    }

    private fun validDataSet(): ByteArray =
        MozcDataSetWriter().write(
            listOf(MozcDataSetInputSection("version", 32, "oss-test".toByteArray()))
        )

    private fun malformedDataSet(metadata: DataSetMetadata): ByteArray {
        val image = ByteArrayOutputStream()
        image.write(MozcDataVersion.Magic)
        image.write(0)
        image.write(byteArrayOf(1, 2, 3))
        val metadataBytes = DataSetMetadataWriter().write(metadata)
        image.write(metadataBytes)
        image.writeUInt64(metadataBytes.size.toLong())
        image.write(MessageDigest.getInstance("SHA-1").digest(image.toByteArray()))
        image.writeUInt64(image.size().toLong() + Long.SIZE_BYTES)
        return image.toByteArray()
    }
}
