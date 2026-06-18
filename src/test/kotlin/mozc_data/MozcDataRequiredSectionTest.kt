package mozc_data

import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MozcDataRequiredSectionTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun dataManagerRejectsMissingRequiredSection() {
        val sections = requiredSectionMap() - "dict"

        val error = assertFailsWith<IllegalArgumentException> { MozcDataManager(sections) }

        assertTrue(error.message!!.contains("dict"))
    }

    @Test
    fun dataManagerRejectsPartialUsageDictionary() {
        val sections = requiredSectionMap() + mapOf(
            "usage_base_conjugation_suffix" to section("usage_base_conjugation_suffix", "x"),
        )

        val error = assertFailsWith<IllegalArgumentException> { MozcDataManager(sections) }

        assertTrue(error.message!!.contains("usage dictionary sections are incomplete"))
    }

    @Test
    fun officialMozcDataContainsAllRequiredSections() {
        val path = repoRoot.resolve("build/generated/mozc-data/mozc.data")
        assertTrue(Files.isRegularFile(path), "Missing official mozc.data. Run ./gradlew generateOfficialMozcData first: $path")
        val dataSet = MozcDataSetReader().read(path)

        MozcDataManager(dataSet.sections)
    }

    private fun requiredSectionMap(): Map<String, MozcDataSection> =
        MozcDataManager.RequiredSections.associateWith { name ->
            section(name, if (name == "version") "oss-test" else "x")
        }

    private fun section(name: String, value: String): MozcDataSection {
        val buffer = ByteBuffer.wrap(value.toByteArray()).asReadOnlyBuffer()
        return MozcDataSection(name, 8, value.toByteArray().size.toLong(), buffer)
    }
}
