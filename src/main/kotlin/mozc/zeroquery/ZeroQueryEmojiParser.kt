package com.kazumaproject.mozc.zeroquery

import java.io.BufferedReader
import java.nio.file.Files
import java.nio.file.Path
import java.text.Normalizer

object ZeroQueryEmojiParser {
    private val whitespaceSplitRegex = Regex("(?: |\\u3000)+")
    private val descriptionSplitRegex = Regex("(?:\\(|\\)|/|・)+")
    private val trailingNumberRegex = Regex("^([^0-9]+)[0-9]+$")

    fun parse(path: Path): ZeroQueryEntryMap =
        Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString())
        }

    fun parse(reader: BufferedReader, filePath: String): ZeroQueryEntryMap {
        val result = ZeroQueryEntryMap()

        reader.lineSequence().forEachIndexed { index, rawLine ->
            val lineNumber = index + 1
            if (rawLine.trim().isEmpty() || rawLine.trimStart().startsWith("#")) {
                return@forEachIndexed
            }

            val columns = splitPreservingEmpty(rawLine, '\t')
            if (columns.size != 7) {
                zeroQueryParseError(filePath, lineNumber, rawLine, "emoji_data.tsv must have exactly 7 tab-separated columns")
            }

            val codepoints = columns[0]
            val emoji = columns[1]
            val readings = columns[2]
            val japaneseName = columns[4]
            val descriptions = columns[5]

            if (codepoints.isEmpty()) {
                return@forEachIndexed
            }

            val readingList = mutableListOf<String>()
            whitespaceSplitRegex.split(normalizeString(readings)).forEach { reading ->
                if (reading.isNotEmpty()) {
                    readingList += reading
                }
            }

            readingList += getReadingsFromDescription(japaneseName)
            whitespaceSplitRegex.split(normalizeString(descriptions)).forEach { description ->
                if (description.isNotEmpty()) {
                    readingList += getReadingsFromDescription(description)
                }
            }

            readingList.toSet().forEach { reading ->
                if (reading.isNotEmpty()) {
                    result.appendEntry(
                        ZeroQueryEntry(
                            key = reading,
                            value = emoji,
                            type = ZeroQueryType.ZERO_QUERY_EMOJI,
                        )
                    )
                }
            }
        }

        result.values.forEach { entries ->
            entries.sortWith { left, right -> UnicodeCodePointStringComparator.compare(left.value, right.value) }
        }
        return result
    }

    internal fun normalizeString(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFKC).replace("~", "〜")

    internal fun removeTrailingNumber(value: String): String =
        trailingNumberRegex.replace(value, "$1")

    internal fun getReadingsFromDescription(description: String): List<String> {
        if (description.isEmpty()) {
            return emptyList()
        }
        val normalized = normalizeString(description)
        return descriptionSplitRegex.split(normalized).map { removeTrailingNumber(it) }
    }
}
