package com.kazumaproject.mozc.zeroquery

import java.io.BufferedReader
import java.nio.file.Files
import java.nio.file.Path

object ZeroQueryNumberParser {
    fun parse(path: Path): ZeroQueryEntryMap =
        Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString())
        }

    fun parse(reader: BufferedReader, filePath: String): ZeroQueryEntryMap {
        val result = ZeroQueryEntryMap()
        var hasDefault = false

        reader.lineSequence().forEachIndexed { index, rawLine ->
            val lineNumber = index + 1
            if (rawLine.trim().isEmpty() || rawLine.trimStart().startsWith("#")) {
                return@forEachIndexed
            }

            val columns = splitPreservingEmpty(rawLine, '\t')
            if (columns.size != 2) {
                zeroQueryParseError(filePath, lineNumber, rawLine, "expected exactly 2 tab-separated columns")
            }
            val key = columns[0]
            if (key.isEmpty()) {
                zeroQueryParseError(filePath, lineNumber, rawLine, "trigger must not be empty")
            }
            if (key == "default") {
                hasDefault = true
            }

            splitPreservingEmpty(columns[1], ',').forEach { value ->
                if (value.isEmpty()) {
                    zeroQueryParseError(filePath, lineNumber, rawLine, "candidate must not be empty")
                }
                result.appendEntry(
                    ZeroQueryEntry(
                        key = key,
                        value = value,
                        type = ZeroQueryType.ZERO_QUERY_NUMBER_SUFFIX,
                    )
                )
            }
        }

        if (!hasDefault) {
            error("Failed to parse zero query number data: file path=$filePath, reason=missing default key")
        }
        return result
    }
}
