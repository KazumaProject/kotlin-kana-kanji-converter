package mozc_data

import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MozcDataChecksumTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun verifiesSha1Checksum() {
        val bytes = MozcDataSetWriter().write(
            listOf(MozcDataSetInputSection("version", 32, "oss-test".toByteArray()))
        )
        val corrupted = bytes.clone()
        corrupted[8] = (corrupted[8].toInt() xor 0x01).toByte()

        val error = assertFailsWith<IllegalArgumentException> { MozcDataSetReader().read(corrupted) }

        assertTrue(error.message!!.contains("SHA1 mismatch"))
    }

    @Test
    fun manifestSha256MatchesSourceBytes() {
        val bytes = MozcDataSetWriter().write(
            listOf(MozcDataSetInputSection("version", 32, "oss-test".toByteArray()))
        )
        val dataSet = MozcDataSetReader().read(bytes)
        val manifest = MozcDataManifestWriter().create(dataSet, bytes)
        val expectedSha256 = MessageDigest.getInstance("SHA-256").digest(bytes).toHex()

        assertEquals(expectedSha256, manifest.sha256)
    }

    @Test
    fun officialManifestSha256CanBeComputedWhenDataExists() {
        val path = repoRoot.resolve("build/generated/mozc-data/mozc.data")
        assertTrue(Files.isRegularFile(path), "Missing official mozc.data. Run ./gradlew generateOfficialMozcData first: $path")
        val bytes = Files.readAllBytes(path)
        val dataSet = MozcDataSetReader().read(bytes)
        val manifest = MozcDataManifestWriter().create(dataSet, bytes)

        assertEquals(MessageDigest.getInstance("SHA-256").digest(bytes).toHex(), manifest.sha256)
    }
}
