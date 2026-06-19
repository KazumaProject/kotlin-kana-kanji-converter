package mozc

import com.kazumaproject.mozc.IdDefConstantsGenerator
import com.kazumaproject.mozc.MozcIdDefParser
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MozcIdDefParserTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val resources: Path = Path.of(
        System.getProperty("mozcDictionaryResourcesDir", repoRoot.resolve("src/main/resources").toString())
    )
    private val idDefPath: Path = resources.resolve("id.def")

    @Test
    fun parsesBundledMozcIdDefWithoutLosingNames() {
        val entries = MozcIdDefParser.parse(idDefPath)

        assertEquals(2672, entries.size)
        assertEquals((0..2671).toList(), entries.map { it.id })
        assertEquals("BOS/EOS,*,*,*,*,*,*", entries[0].name)
        assertEquals("名詞,接尾,一般,*,*,*,下", entries[1951].name)
        assertEquals("名詞,接尾,副詞可能,*,*,*,下", entries[2002].name)
        assertEquals("記号,句点,*,*,*,*,.", entries[2647].name)
        assertEquals("連体詞,*,*,*,*,*,同じ", entries[2670].name)
        assertEquals("連体詞,*,*,*,*,*,我が", entries[2671].name)
    }

    @Test
    fun generatesDeterministicKotlinFromMozcIdDef() {
        val generated = IdDefConstantsGenerator.generate(MozcIdDefParser.parse(idDefPath))

        assertTrue(generated.contains("const val BOS_EOS = (0).toShort()"))
        assertTrue(generated.contains("const val `名詞,接尾,一般,*,*,*,下` = (1951).toShort()"))
        assertTrue(generated.contains("const val `名詞,接尾,副詞可能,*,*,*,下` = (2002).toShort()"))
        assertTrue(generated.contains("const val `記号,句点,*,*,*,*,.` = (2647).toShort()"))
        assertTrue(generated.contains("\"記号,句点,*,*,*,*,.\" to (2647).toShort()"))
        assertTrue(generated.contains("const val `連体詞,*,*,*,*,*,同じ` = (2670).toShort()"))
        assertTrue(generated.contains("const val `連体詞,*,*,*,*,*,我が` = (2671).toShort()"))
        assertEquals(generated, IdDefConstantsGenerator.generate(MozcIdDefParser.parse(idDefPath)))
        assertTrue(generated.endsWith("\n"))
    }

    @Test
    fun rejectsMissingId() {
        val path = writeIdDef(
            """
            0 BOS/EOS,*,*,*,*,*,*
            2 その他,間投,*,*,*,*,*
            """.trimIndent()
        )

        val error = assertFailsWith<IllegalStateException> { MozcIdDefParser.parse(path) }
        assertTrue(error.message!!.contains("expected ID=1"))
        assertTrue(error.message!!.contains(path.toString()))
    }

    @Test
    fun rejectsDuplicateId() {
        val path = writeIdDef(
            """
            0 BOS/EOS,*,*,*,*,*,*
            1 その他,間投,*,*,*,*,*
            1 フィラー,*,*,*,*,*,*
            """.trimIndent()
        )

        val error = assertFailsWith<IllegalStateException> { MozcIdDefParser.parse(path) }
        assertTrue(error.message!!.contains("duplicated ID=1"))
        assertTrue(error.message!!.contains("second line=3"))
    }

    @Test
    fun rejectsDuplicateName() {
        val path = writeIdDef(
            """
            0 BOS/EOS,*,*,*,*,*,*
            1 その他,間投,*,*,*,*,*
            2 その他,間投,*,*,*,*,*
            """.trimIndent()
        )

        val error = assertFailsWith<IllegalStateException> { MozcIdDefParser.parse(path) }
        assertTrue(error.message!!.contains("Duplicate id.def name"))
        assertTrue(error.message!!.contains("その他,間投,*,*,*,*,*"))
    }

    @Test
    fun rejectsInvalidBosEos() {
        val path = writeIdDef(
            """
            0 その他,間投,*,*,*,*,*
            1 フィラー,*,*,*,*,*,*
            """.trimIndent()
        )

        val error = assertFailsWith<IllegalStateException> { MozcIdDefParser.parse(path) }
        assertTrue(error.message!!.contains("Invalid BOS/EOS"))
        assertTrue(error.message!!.contains("expected name=BOS/EOS,*,*,*,*,*,*"))
    }

    @Test
    fun preservesTrailingDotInName() {
        val path = writeIdDef(
            """
            0 BOS/EOS,*,*,*,*,*,*
            1 記号,句点,*,*,*,*,.
            """.trimIndent()
        )

        val entries = MozcIdDefParser.parse(path)
        assertEquals("記号,句点,*,*,*,*,.", entries[1].name)
    }

    private fun writeIdDef(content: String): Path {
        val path = Files.createTempFile("id-def-", ".def")
        path.writeText("$content\n")
        return path
    }
}
