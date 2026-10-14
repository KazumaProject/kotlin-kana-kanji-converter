package english

import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.english.EnglishDictionaryBinaryValidator
import java.io.ByteArrayOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import java.nio.file.Files
import java.nio.file.Path
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class EnglishDictionaryBinaryValidatorTest {
    private val rows = listOf(
        row("あいす", "ice", 100),
        row("あいす", "ICE", 120),
        row("あいすくりーむ", "ice cream", 400),
        row("えーぴーあい", "API", 200).copy(leftId = 7, rightId = 8),
        row("かー", "car", 300),
        row("わいふぁい", "Wi-Fi", 350),
    )

    @Test
    fun roundTripsEveryPostingIncludingCaseSpacesHyphensAndNonterminalPrefixes() = fixture { files ->
        val result = files.validate(rows)
        assertEquals(5, result.readingCount)
        assertEquals(6, result.entryCount)
        assertEquals(5, result.maxTermId)
        assertTrue(result.nonTerminalPrefixCount > 0)
    }

    @Test
    fun detectsWrongCostsAndPerReadingPostingOrder() = fixture { files ->
        val wrongCost = rows.toMutableList().apply { this[0] = first().copy(cost = 101) }
        assertTrue(assertFailsWith<IllegalArgumentException> { files.validate(wrongCost) }.message!!.contains("posting differs"))
        val wrongOrder = listOf(rows[1], rows[0]) + rows.drop(2)
        assertTrue(assertFailsWith<IllegalArgumentException> { files.validate(wrongOrder) }.message!!.contains("position=0"))
    }

    @Test
    fun detectsMismatchedSharedPosTable() = fixture { files ->
        ObjectOutputStream(Files.newOutputStream(files.pos)).use {
            it.writeObject(shortArrayOf(90, 91))
            it.writeObject(shortArrayOf(92, 93))
        }
        assertTrue(assertFailsWith<IllegalArgumentException> { files.validate(rows) }.message!!.contains("posting differs"))
    }

    @Test
    fun detectsMissingPostingsAndUnexpectedReadings() = fixture { files ->
        assertTrue(assertFailsWith<IllegalArgumentException> { files.validate(rows.dropLast(1)) }.message!!.contains("posting count"))
        val unknownReading = rows.dropLast(1) + rows.last().copy(yomi = "わーど")
        val message = assertFailsWith<IllegalArgumentException> { files.validate(unknownReading) }.message!!
        assertTrue(message.contains("missing=[わーど]"))
        assertTrue(message.contains("extra=[わいふぁい]"))
    }

    @Test
    fun rejectsTermIdsThatOverflowTheConsumerShortLookup() = fixture { files ->
        val objects = ObjectInputStream(Files.newInputStream(files.yomi)).use { input ->
            List(4) { input.readObject() }
        }
        (objects[3] as IntArray)[0] = Short.MAX_VALUE.toInt() + 1
        ObjectOutputStream(Files.newOutputStream(files.yomi)).use { output -> objects.forEach(output::writeObject) }
        assertTrue(assertFailsWith<IllegalArgumentException> { files.validate(rows) }.message!!.contains("signed Short range"))
    }

    @Test
    fun verifiesTheActualNestedReleaseZipWithoutExtractingIt() = fixture { files ->
        val zip = files.release()
        assertEquals(files.validate(rows), EnglishDictionaryBinaryValidator.validateReleaseZip(rows, zip))
    }

    @Test
    fun rejectsMissingReleaseAssetsAndUnexpectedInnerZipEntries() = fixture { files ->
        val missing = files.release(omitPos = true)
        assertFailsWith<IllegalArgumentException> { EnglishDictionaryBinaryValidator.validateReleaseZip(rows, missing) }
        val extra = files.release(extraInnerEntry = true)
        assertFailsWith<IllegalArgumentException> { EnglishDictionaryBinaryValidator.validateReleaseZip(rows, extra) }
    }

    private fun row(reading: String, surface: String, cost: Int) =
        Dictionary(reading, 5, 6, cost.toShort(), surface)

    private fun fixture(block: (Fixture) -> Unit) {
        val root = Files.createTempDirectory("english-binary-validator-")
        try {
            val files = Fixture(root)
            val grouped = rows.groupBy { it.yomi }.toSortedMap()
            val posForBuild = root.resolve("pos_table_for_build.dat")
            TokenArray().apply {
                buildPOSTable(grouped, mode = 1, outputPath = files.pos.toString())
                buildPOSTableWithIndex(grouped, mode = 1, outputPath = posForBuild.toString())
            }
            buildAndWriteDictionaryArtifacts(
                dictionaryList = grouped,
                yomiOutputPath = files.yomi.toString(),
                tangoOutputPath = files.tango.toString(),
                tokenOutputPath = files.token.toString(),
                skipKanaOnlyTango = true,
                posTableForBuildPath = posForBuild.toString(),
            )
            block(files)
        } finally {
            root.toFile().deleteRecursively()
        }
    }

    private class Fixture(val root: Path) {
        val yomi: Path = root.resolve("yomi.dat")
        val tango: Path = root.resolve("tango.dat")
        val token: Path = root.resolve("token.dat")
        val pos: Path = root.resolve("pos_table.dat")

        fun validate(expected: List<Dictionary>) =
            EnglishDictionaryBinaryValidator.validate(expected, yomi, tango, token, pos)

        fun release(omitPos: Boolean = false, extraInnerEntry: Boolean = false): Path {
            val output = root.resolve("release.zip")
            ZipOutputStream(Files.newOutputStream(output)).use { zip ->
                listOf(yomi, tango, token).forEach { path ->
                    val bytes = ByteArrayOutputStream().also { buffer ->
                        ZipOutputStream(buffer).use { inner ->
                            inner.putNextEntry(ZipEntry(path.fileName.toString()))
                            inner.write(Files.readAllBytes(path))
                            inner.closeEntry()
                            if (extraInnerEntry) {
                                inner.putNextEntry(ZipEntry("unexpected.txt"))
                                inner.write("unexpected".toByteArray())
                                inner.closeEntry()
                            }
                        }
                    }.toByteArray()
                    zip.putNextEntry(ZipEntry("app/src/main/assets/english_reading/${path.fileName}.zip"))
                    zip.write(bytes)
                    zip.closeEntry()
                }
                if (!omitPos) {
                    zip.putNextEntry(ZipEntry("app/src/main/assets/pos_table.dat"))
                    zip.write(Files.readAllBytes(pos))
                    zip.closeEntry()
                }
            }
            return output
        }
    }
}
