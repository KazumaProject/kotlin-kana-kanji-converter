package com.kazumaproject.mozc.zeroquery

import java.io.BufferedReader
import java.nio.file.Files
import java.nio.file.Path

object ZeroQuerySymbolParser {
    private val whitespaceSplitRegex = Regex("(?: |\\u3000)+")

    fun parse(path: Path): ZeroQueryEntryMap =
        Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString())
        }

    fun parse(reader: BufferedReader, filePath: String): ZeroQueryEntryMap {
        val result = ZeroQueryEntryMap()
        var headerSeen = false

        reader.lineSequence().forEachIndexed { index, rawLine ->
            val lineNumber = index + 1
            if (rawLine.trim().isEmpty() || rawLine.trimStart().startsWith("#")) {
                return@forEachIndexed
            }

            val columns = splitPreservingEmpty(rawLine, '\t')
            if (!headerSeen) {
                if (columns.size >= 3 && columns[0] == "POS" && columns[1] == "CHAR") {
                    headerSeen = true
                    return@forEachIndexed
                }
                zeroQueryParseError(filePath, lineNumber, rawLine, "symbol.tsv header is missing")
            }

            if (columns.size < 3) {
                zeroQueryParseError(filePath, lineNumber, rawLine, "symbol.tsv must have at least 3 tab-separated columns")
            }

            val symbol = columns[1]
            if (symbol.codePointCount(0, symbol.length) != 1) {
                return@forEachIndexed
            }

            val codePoint = symbol.codePointAt(0)
            if (codePoint !in 0x2600..0x2767) {
                return@forEachIndexed
            }

            whitespaceSplitRegex.split(columns[2].trim()).forEach { reading ->
                if (reading.isNotEmpty()) {
                    result.appendEntry(ZeroQueryEntry(reading, symbol, ZeroQueryType.ZERO_QUERY_NONE))
                }
            }

            columns.getOrNull(3)
                ?.takeIf { it.isNotEmpty() }
                ?.let { description ->
                    result.appendEntry(ZeroQueryEntry(description, symbol, ZeroQueryType.ZERO_QUERY_NONE))
                }
            columns.getOrNull(4)
                ?.takeIf { it.isNotEmpty() }
                ?.let { additionalDescription ->
                    result.appendEntry(ZeroQueryEntry(additionalDescription, symbol, ZeroQueryType.ZERO_QUERY_NONE))
                }
        }

        if (!headerSeen) {
            error("Failed to parse zero query symbol data: file path=$filePath, reason=symbol.tsv header is missing")
        }
        return result
    }
}
