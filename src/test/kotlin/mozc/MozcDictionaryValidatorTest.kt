package mozc

import com.kazumaproject.mozc.ConnectionMatrixParser
import com.kazumaproject.mozc.MozcDictionaryValidator
import com.kazumaproject.mozc.MozcIdDefParser
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MozcDictionaryValidatorTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val resources: Path = Path.of(
        System.getProperty("mozcDictionaryResourcesDir", repoRoot.resolve("src/main/resources").toString())
    )

    @Test
    fun bundledMozcDictionaryIdsFitIdDefAndConnectionMatrix() {
        val idDefEntryCount = MozcIdDefParser.parse(resources.resolve("id.def")).size
        val connectionMatrixSize = ConnectionMatrixParser.parse(resources.resolve("connection_single_column.txt")).size
        val dictionaryFiles = (0..9).map { resources.resolve("dictionary%02d.txt".format(it)) } + listOf(resources.resolve("suffix.txt"))

        MozcDictionaryValidator.validateDictionaryFiles(
            dictionaryFiles = dictionaryFiles,
            idDefEntryCount = idDefEntryCount,
            connectionMatrixSize = connectionMatrixSize,
        )
    }

    @Test
    fun rejectsLeftIdOutOfRangeWithContext() {
        val path = writeDictionary("よみ\t2672\t1\t1000\t表記\n")

        val error = assertFailsWith<IllegalStateException> {
            MozcDictionaryValidator.validateDictionaryFiles(listOf(path), idDefEntryCount = 2672, connectionMatrixSize = 2672)
        }
        assertTrue(error.message!!.contains(path.toString()))
        assertTrue(error.message!!.contains("line number=1"))
        assertTrue(error.message!!.contains("surface/yomi=表記/よみ"))
        assertTrue(error.message!!.contains("leftId=2672"))
    }

    @Test
    fun rejectsRightIdOutOfRangeWithContext() {
        val path = writeDictionary("よみ\t1\t2672\t1000\t表記\n")

        val error = assertFailsWith<IllegalStateException> {
            MozcDictionaryValidator.validateDictionaryFiles(listOf(path), idDefEntryCount = 2672, connectionMatrixSize = 2672)
        }
        assertTrue(error.message!!.contains(path.toString()))
        assertTrue(error.message!!.contains("rightId=2672"))
        assertTrue(error.message!!.contains("connectionMatrixSize=2672"))
    }

    private fun writeDictionary(content: String): Path {
        val path = Files.createTempFile("dictionary-", ".txt")
        path.writeText(content)
        return path
    }
}
