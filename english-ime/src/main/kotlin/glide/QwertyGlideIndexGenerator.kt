package glide

import dictionary.Dictionary
import java.io.BufferedOutputStream
import java.io.DataOutputStream
import java.io.File
import java.io.FileOutputStream

private const val MIN_WORD_LENGTH = 2
private const val MAX_WORD_LENGTH = 24
private const val FALLBACK_WORD_COST = 6000

object QwertyGlideIndexGenerator {
    private const val MAGIC = "QGIX"
    private const val SCHEMA_VERSION = 1

    private val fallbackWords = listOf(
        "hello",
        "good",
        "test",
        "word",
        "world",
        "keyboard",
        "android",
        "sumire",
        "coffee",
        "letter",
        "people",
        "glide",
        "time",
        "home",
        "something"
    )

    fun generate(dictList: List<Dictionary>, outputFile: File): Int {
        val entries = buildEntries(dictList)
        write(entries, outputFile)
        return entries.size
    }

    fun buildEntries(dictList: List<Dictionary>): List<QwertyGlideIndexedEntry> {
        val wordCosts = mutableMapOf<String, Int>()

        for (dictionary in dictList) {
            val reading = dictionary.reading
            if (!reading.isLowercaseAlphabetWord()) {
                continue
            }

            val word = if (dictionary.withUpperCase) {
                dictionary.word.lowercase()
            } else {
                reading
            }
            if (!word.isLowercaseAlphabetWord()) {
                continue
            }

            wordCosts.mergeMin(word, dictionary.cost.toInt())
        }

        for (fallbackWord in fallbackWords) {
            wordCosts.mergeMin(fallbackWord, FALLBACK_WORD_COST)
        }

        return wordCosts
            .map { (word, wordCost) -> QwertyGlideIndexedEntry.from(word, wordCost) }
            .sortedWith(
                compareBy<QwertyGlideIndexedEntry> { it.firstChar }
                    .thenBy { it.lastChar }
                    .thenBy { it.length }
                    .thenBy { it.word }
                    .thenBy { it.wordCost }
            )
    }

    fun write(entries: List<QwertyGlideIndexedEntry>, outputFile: File) {
        outputFile.parentFile?.mkdirs()
        DataOutputStream(BufferedOutputStream(FileOutputStream(outputFile))).use { output ->
            output.writeUTF(MAGIC)
            output.writeInt(SCHEMA_VERSION)
            output.writeInt(entries.size)
            for (entry in entries) {
                output.writeUTF(entry.word)
                output.writeInt(entry.wordCost)
                output.writeChar(entry.firstChar.code)
                output.writeChar(entry.lastChar.code)
                output.writeInt(entry.length)
                output.writeInt(entry.characterMask)
                output.writeLong(entry.transitionMask)
            }
        }
    }
}

private fun String.isLowercaseAlphabetWord(): Boolean {
    return length in MIN_WORD_LENGTH..MAX_WORD_LENGTH && all { it in 'a'..'z' }
}

private fun MutableMap<String, Int>.mergeMin(word: String, wordCost: Int) {
    val currentCost = this[word]
    if (currentCost == null || wordCost < currentCost) {
        this[word] = wordCost
    }
}
