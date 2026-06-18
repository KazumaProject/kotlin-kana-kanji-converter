package mozc_runtime

import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

object MozcGoldenTestSupport {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    fun officialData(): Path {
        val path = repoRoot.resolve("build/generated/mozc-data/mozc.data")
        assertTrue(Files.isRegularFile(path), "Missing official mozc.data. Run ./gradlew generateOfficialMozcData first: $path")
        return path
    }

    fun fixture(relativePath: String): Path {
        val path = repoRoot.resolve("src/test/resources/mozc_golden").resolve(relativePath)
        assertTrue(Files.isRegularFile(path), "Missing official Mozc golden fixture: $path")
        assertContainsCandidateFields(path)
        return path
    }

    fun runtimeClass(name: String) {
        val klass = runCatching { Class.forName(name) }.getOrNull()
        assertNotNull(klass, "Missing required Mozc Kotlin runtime class: $name")
    }

    private fun assertContainsCandidateFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "key",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "consumedKeySize",
            "innerSegments",
            "description",
            "category",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "Golden fixture is missing required candidate fields: path=$path missing=${missing.joinToString()}")
    }
}
