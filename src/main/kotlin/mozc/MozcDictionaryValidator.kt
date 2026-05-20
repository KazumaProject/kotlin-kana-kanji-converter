package com.kazumaproject.mozc

import java.nio.file.Files
import java.nio.file.Path

object MozcDictionaryValidator {
    fun validateDictionaryFiles(
        dictionaryFiles: List<Path>,
        idDefEntryCount: Int,
        connectionMatrixSize: Int,
    ) {
        dictionaryFiles.forEach { path ->
            Files.newBufferedReader(path).use { reader ->
                reader.lineSequence().forEachIndexed { index, rawLine ->
                    val lineNumber = index + 1
                    if (rawLine.isEmpty()) {
                        return@forEachIndexed
                    }
                    val columns = rawLine.split('\t')
                    if (columns.size < 4) {
                        error(
                            "Invalid dictionary line: file path=$path, line number=$lineNumber, " +
                                    "surface/yomi=${columns.firstOrNull().orEmpty()}, reason=expected at least 4 tab-separated columns"
                        )
                    }
                    val leftId = columns[1].toIntOrNull()
                    val rightId = columns[2].toIntOrNull()
                    if (leftId == null || rightId == null) {
                        failOutOfRange(path, lineNumber, columns, leftId, rightId, idDefEntryCount, connectionMatrixSize, "leftId/rightId must be Int")
                    }
                    if (
                        leftId < 0 ||
                        rightId < 0 ||
                        leftId >= idDefEntryCount ||
                        rightId >= idDefEntryCount ||
                        leftId >= connectionMatrixSize ||
                        rightId >= connectionMatrixSize
                    ) {
                        failOutOfRange(path, lineNumber, columns, leftId, rightId, idDefEntryCount, connectionMatrixSize, "leftId/rightId out of range")
                    }
                }
            }
        }
    }

    private fun failOutOfRange(
        path: Path,
        lineNumber: Int,
        columns: List<String>,
        leftId: Int?,
        rightId: Int?,
        idDefEntryCount: Int,
        connectionMatrixSize: Int,
        reason: String,
    ): Nothing {
        val yomi = columns.getOrNull(0).orEmpty()
        val surface = columns.getOrNull(4).orEmpty()
        error(
            "Dictionary ID validation failed: file path=$path, line number=$lineNumber, " +
                    "surface/yomi=$surface/$yomi, leftId=$leftId, rightId=$rightId, " +
                    "idDefEntryCount=$idDefEntryCount, connectionMatrixSize=$connectionMatrixSize, reason=$reason"
        )
    }
}
