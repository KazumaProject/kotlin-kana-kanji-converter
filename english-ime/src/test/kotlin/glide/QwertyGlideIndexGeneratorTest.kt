package glide

import dictionary.Dictionary
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.File
import java.io.FileInputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class QwertyGlideIndexGeneratorTest {
    @Test
    fun buildEntriesKeepsOnlyLowercaseAlphabetWords() {
        val entries = QwertyGlideIndexGenerator.buildEntries(
            listOf(
                dictionary(reading = "ok", cost = 1000, word = "unused1", withUpperCase = false),
                dictionary(reading = "Aq", cost = 1000, word = "aq", withUpperCase = false),
                dictionary(reading = "bad1", cost = 1000, word = "bad", withUpperCase = false),
                dictionary(reading = "bad word", cost = 1000, word = "bad", withUpperCase = false),
                dictionary(reading = "valid", cost = 1000, word = "bad1", withUpperCase = true),
                dictionary(reading = "space", cost = 1000, word = "two words", withUpperCase = true),
                dictionary(reading = "caps", cost = 1000, word = "Camel", withUpperCase = true)
            )
        )

        assertHasWord(entries, "ok", 1000)
        assertHasWord(entries, "camel", 1000)
        assertFalse(entries.any { it.word in setOf("Aq", "aq", "bad1", "bad word", "two words") })
    }

    @Test
    fun buildEntriesUsesLowercasedWordWhenDictionaryHasUppercaseWord() {
        val entries = QwertyGlideIndexGenerator.buildEntries(
            listOf(dictionary(reading = "ios", cost = 1234, word = "iOS", withUpperCase = true))
        )

        assertHasWord(entries, "ios", 1234)
    }

    @Test
    fun buildEntriesUsesReadingWhenDictionaryDoesNotHaveUppercaseWord() {
        val entries = QwertyGlideIndexGenerator.buildEntries(
            listOf(dictionary(reading = "input", cost = 1234, word = "Different", withUpperCase = false))
        )

        assertHasWord(entries, "input", 1234)
        assertFalse(entries.any { it.word == "different" })
    }

    @Test
    fun buildEntriesKeepsLowestCostForDuplicateWords() {
        val entries = QwertyGlideIndexGenerator.buildEntries(
            listOf(
                dictionary(reading = "same", cost = 9000, word = "Same", withUpperCase = true),
                dictionary(reading = "same", cost = 1200, word = "Same", withUpperCase = true),
                dictionary(reading = "same", cost = 3000, word = "unused", withUpperCase = false)
            )
        )

        assertHasWord(entries, "same", 1200)
    }

    @Test
    fun buildEntriesAddsFallbackWords() {
        val entries = QwertyGlideIndexGenerator.buildEntries(emptyList())

        assertHasWord(entries, "hello", 6000)
        assertHasWord(entries, "keyboard", 6000)
        assertHasWord(entries, "something", 6000)
    }

    @Test
    fun buildEntriesKeepsLowerCostWhenFallbackWordAlreadyExists() {
        val entries = QwertyGlideIndexGenerator.buildEntries(
            listOf(
                dictionary(reading = "hello", cost = 7000, word = "unused", withUpperCase = false),
                dictionary(reading = "world", cost = 5000, word = "unused", withUpperCase = false)
            )
        )

        assertHasWord(entries, "hello", 6000)
        assertHasWord(entries, "world", 5000)
    }

    @Test
    fun buildEntriesSortsByFirstCharLastCharLengthWordAndWordCost() {
        val words = listOf("az", "ba", "aab", "ab", "bb", "aa")
        val entries = QwertyGlideIndexGenerator.buildEntries(
            words.mapIndexed { index, word ->
                dictionary(reading = word, cost = (1000 + index).toShort(), word = "unused", withUpperCase = false)
            }
        )

        assertEquals(
            listOf("aa", "ab", "aab", "az", "ba", "bb"),
            entries.filter { it.word in words }.map { it.word }
        )
        assertEquals(
            entries.sortedWith(
                compareBy<QwertyGlideIndexedEntry> { it.firstChar }
                    .thenBy { it.lastChar }
                    .thenBy { it.length }
                    .thenBy { it.word }
                    .thenBy { it.wordCost }
            ),
            entries
        )
    }

    @Test
    fun characterMaskMatchesRuntimeCalculation() {
        val entry = QwertyGlideIndexedEntry.from("coffee", 1000)
        val expectedMask = (1 shl ('c' - 'a')) or
                (1 shl ('o' - 'a')) or
                (1 shl ('f' - 'a')) or
                (1 shl ('e' - 'a'))

        assertEquals(expectedMask, entry.characterMask)
    }

    @Test
    fun transitionMaskMatchesRuntimeCalculation() {
        val entry = QwertyGlideIndexedEntry.from("abca", 1000)
        val ab = (('a' - 'a') * 31 + ('b' - 'a')) and 63
        val bc = (('b' - 'a') * 31 + ('c' - 'a')) and 63
        val ca = (('c' - 'a') * 31 + ('a' - 'a')) and 63
        val expectedMask = (1L shl ab) or (1L shl bc) or (1L shl ca)

        assertEquals(expectedMask, entry.transitionMask)
    }

    @Test
    fun writePersistsFixedBinaryFormatReadableWithDataInputStream() {
        val tempFile = kotlin.io.path.createTempFile(prefix = "qgix", suffix = ".dat").toFile()
        val entries = listOf(
            QwertyGlideIndexedEntry.from("ab", 1000),
            QwertyGlideIndexedEntry.from("coffee", 2000)
        )

        QwertyGlideIndexGenerator.write(entries, tempFile)

        DataInputStream(BufferedInputStream(FileInputStream(tempFile))).use { input ->
            assertEquals("QGIX", input.readUTF())
            assertEquals(1, input.readInt())
            assertEquals(entries.size, input.readInt())
            for (entry in entries) {
                assertEquals(entry.word, input.readUTF())
                assertEquals(entry.wordCost, input.readInt())
                assertEquals(entry.firstChar, input.readChar())
                assertEquals(entry.lastChar, input.readChar())
                assertEquals(entry.length, input.readInt())
                assertEquals(entry.characterMask, input.readInt())
                assertEquals(entry.transitionMask, input.readLong())
            }
        }
    }

    @Test
    fun generateWritesFileAndReturnsNonZeroEntryCount() {
        val outputFile = File(kotlin.io.path.createTempDirectory(prefix = "qgix").toFile(), "qwerty_glide_index.dat")

        val entryCount = QwertyGlideIndexGenerator.generate(
            listOf(dictionary(reading = "sample", cost = 1000, word = "unused", withUpperCase = false)),
            outputFile
        )

        assertTrue(entryCount > 0)
        assertTrue(outputFile.isFile)
        assertTrue(outputFile.length() > 0L)
    }

    private fun dictionary(
        reading: String,
        cost: Int,
        word: String,
        withUpperCase: Boolean
    ): Dictionary {
        return dictionary(reading, cost.toShort(), word, withUpperCase)
    }

    private fun dictionary(
        reading: String,
        cost: Short,
        word: String,
        withUpperCase: Boolean
    ): Dictionary {
        return Dictionary(
            reading = reading,
            cost = cost,
            word = word,
            withUpperCase = withUpperCase
        )
    }

    private fun assertHasWord(entries: List<QwertyGlideIndexedEntry>, word: String, wordCost: Int) {
        val entry = entries.firstOrNull { it.word == word }
        assertNotNull(entry, "Expected entry for $word")
        assertEquals(wordCost, entry.wordCost)
    }
}
