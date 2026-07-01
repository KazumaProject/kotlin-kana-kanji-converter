package com.kazumaproject.mozc.zeroquery

import java.io.BufferedReader
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.isRegularFile

object ZeroQueryRuleParser {
    fun parse(path: Path): ZeroQueryEntryMap =
        Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString(), rejectDuplicateCandidateForSameTrigger = false)
        }

    fun parseCustom(path: Path): ZeroQueryEntryMap {
        require(path.isRegularFile()) { "Missing custom zero query file: file path=$path" }
        return Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString(), rejectDuplicateCandidateForSameTrigger = true)
        }
    }

    fun parse(
        reader: BufferedReader,
        filePath: String,
        rejectDuplicateCandidateForSameTrigger: Boolean = false,
    ): ZeroQueryEntryMap {
        val result = ZeroQueryEntryMap()
        val seenCandidatesByKey = linkedMapOf<String, MutableSet<String>>()

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

            val values = splitPreservingEmpty(columns[1], ',')
            values.forEach { value ->
                if (value.isEmpty()) {
                    zeroQueryParseError(filePath, lineNumber, rawLine, "candidate must not be empty")
                }
                if (rejectDuplicateCandidateForSameTrigger) {
                    val seen = seenCandidatesByKey.getOrPut(key) { linkedSetOf() }
                    if (!seen.add(value)) {
                        zeroQueryParseError(
                            filePath,
                            lineNumber,
                            rawLine,
                            "duplicate candidate for same trigger in custom file: trigger='$key', candidate='$value'",
                        )
                    }
                }
                result.appendEntry(
                    ZeroQueryEntry(
                        key = key,
                        value = value,
                        type = ZeroQueryType.ZERO_QUERY_NONE,
                    )
                )
            }
        }
        return result
    }
}
