package mozc

import com.kazumaproject.mozc.IdDefConstantsReferenceValidator
import com.kazumaproject.mozc.MozcIdDefParser
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.writeText
import kotlin.streams.toList
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class IdDefConstantsReferenceValidatorTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val resources: Path = Path.of(
        System.getProperty("mozcDictionaryResourcesDir", repoRoot.resolve("src/main/resources").toString())
    )
    private val idDefEntries = MozcIdDefParser.parse(resources.resolve("id.def"))

    @Test
    fun constantsReferencesExistInMozcIdDef() {
        val kotlinFiles = Files.walk(repoRoot.resolve("src/main/kotlin")).use { paths ->
            paths.filter { it.toString().endsWith(".kt") }.toList()
        }

        IdDefConstantsReferenceValidator.validate(kotlinFiles, idDefEntries)
    }

    @Test
    fun rejectsMissingReferenceWithFileLineAndEntryName() {
        val path = Files.createTempFile("missing-iddef-reference-", ".kt")
        path.writeText(
            """
            package fixture
            import com.kazumaproject.IdDefConstants.`存在しない,*,*,*,*,*,*`
            """.trimIndent()
        )

        val error = assertFailsWith<IllegalStateException> {
            IdDefConstantsReferenceValidator.validate(listOf(path), idDefEntries)
        }
        assertTrue(error.message!!.contains(path.toString()))
        assertTrue(error.message!!.contains("line number=2"))
        assertTrue(error.message!!.contains("存在しない,*,*,*,*,*,*"))
    }
}
