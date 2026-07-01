package com.kazumaproject.mozc.zeroquery

import java.io.BufferedReader
import java.nio.file.Files
import java.nio.file.Path

object ZeroQueryEmoticonParser {
    private val whitespaceSplitRegex = Regex("(?: |\\u3000)+")

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
            if (columns.size != 3) {
                zeroQueryParseError(filePath, lineNumber, rawLine, "emoticon categorized.tsv must have exactly 3 tab-separated columns")
            }

            val value = columns[0]
            val description = columns[2].trim()
            whitespaceSplitRegex.split(description).forEach { reading ->
                if (reading.isNotEmpty()) {
                    result.appendEntry(
                        ZeroQueryEntry(
                            key = reading,
                            value = value,
                            type = ZeroQueryType.ZERO_QUERY_EMOTICON,
                        )
                    )
                }
            }
        }
        return result
    }
}
