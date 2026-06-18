package mozc_data

import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class MozcDataVersionTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun dataManagerReadsVersionSection() {
        val bytes = MozcDataSetWriter().write(
            listOf(MozcDataSetInputSection("version", 32, "oss-test\n".toByteArray()))
        )
        val dataSet = MozcDataSetReader().read(bytes)

        assertEquals("oss-test", dataSet.requireSection("version").data.toUtf8String().trimEnd('\n'))
    }

    @Test
    fun officialVersionSectionMatchesRuntimeExpectationWhenProvided() {
        val path = repoRoot.resolve("build/generated/mozc-data/mozc.data")
        assertTrue(Files.isRegularFile(path), "Missing official mozc.data. Run ./gradlew generateOfficialMozcData first: $path")

        MozcDataVerifier().verify(path, MozcDataVersion.SupportedEngineVersion)
    }
}
