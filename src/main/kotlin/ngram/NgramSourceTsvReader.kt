package com.kazumaproject.ngram

import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.isRegularFile
import kotlin.io.path.name

class NgramSourceTsvReader {
    fun readDirectory(sourceDirectory: Path): NgramSourceReadResult {
        require(Files.isDirectory(sourceDirectory)) {
            "N-gram source directory does not exist: $sourceDirectory"
        }
        val files = Files.list(sourceDirectory).use { stream ->
            stream
                .filter { it.isRegularFile() && it.name.endsWith(".tsv") }
                .sorted { left, right -> left.name.compareTo(right.name) }
                .toList()
        }
        return readFiles(files, sourceDirectory)
    }

    fun readFiles(files: List<Path>, sourceRoot: Path? = null): NgramSourceReadResult {
        val allRules = mutableListOf<NgramRule>()
        val sourceFiles = mutableListOf<String>()
        var sourceRowCount = 0

        files.sortedBy { it.toString() }.forEach { file ->
            require(file.isRegularFile()) { "N-gram source TSV does not exist: $file" }
            val sourceName = sourceRoot?.relativize(file)?.toString()?.replace('\\', '/') ?: file.name
            sourceFiles += sourceName
            val rows = Files.readAllLines(file)
            if (rows.isEmpty()) {
                return@forEach
            }
            val header = splitPreservingEmpty(rows.first(), '\t').map { it.trim().lowercase() }
            val headerIndex = header.withIndex().associate { it.value to it.index }
            require("order" in headerIndex && "reading" in headerIndex) {
                "Invalid N-gram source header: file=$file, required columns are order and reading"
            }

            rows.drop(1).forEachIndexed { zeroBasedIndex, rawLine ->
                val lineNumber = zeroBasedIndex + 2
                if (rawLine.isBlank() || rawLine.trimStart().startsWith("#")) {
                    return@forEachIndexed
                }
                sourceRowCount += 1
                val columns = splitPreservingEmpty(rawLine, '\t')
                val orderText = column(columns, headerIndex, "order")
                val order = orderText.toIntOrNull()
                    ?: throw IllegalArgumentException("Invalid N-gram order: file=$file line=$lineNumber value=$orderText")
                val surfaces = (1..NGRAM_SECTION_COUNT).map { surfaceIndex ->
                    column(columns, headerIndex, "surface$surfaceIndex")
                }
                allRules += NgramRule(
                    order = order,
                    reading = column(columns, headerIndex, "reading"),
                    surfaces = surfaces,
                    source = firstPresent(columns, headerIndex, listOf("source", "source_id")),
                    comment = firstPresent(columns, headerIndex, listOf("comment", "improved", "update_date", "update_no")),
                    sourceFile = sourceName,
                    lineNumber = lineNumber,
                )
            }
        }

        return NgramSourceReadResult(
            rules = allRules,
            sourceFiles = sourceFiles,
            sourceRowCount = sourceRowCount,
        )
    }

    private fun column(columns: List<String>, headerIndex: Map<String, Int>, name: String): String {
        val index = headerIndex[name] ?: return ""
        return columns.getOrElse(index) { "" }
    }

    private fun firstPresent(columns: List<String>, headerIndex: Map<String, Int>, names: List<String>): String {
        names.forEach { name ->
            val value = column(columns, headerIndex, name)
            if (value.isNotBlank()) {
                return value
            }
        }
        return ""
    }
}
