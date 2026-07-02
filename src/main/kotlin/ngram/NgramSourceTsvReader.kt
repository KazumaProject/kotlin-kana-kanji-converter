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
        val sourceSet = NgramSourceSetManifestReader.read(sourceDirectory)
        val files = sourceSet
            ?.enabledFiles
            ?.map { sourceDirectory.resolve(it).normalize() }
            ?: NgramSourceSetManifestReader.discoverSourceFiles(sourceDirectory)
        val allowedOrdersBySource = sourceSet
            ?.entries
            ?.filter { it.enabled }
            ?.associate { it.file to it.orders }
            .orEmpty()
        return readFiles(files, sourceDirectory, allowedOrdersBySource)
    }

    fun readFiles(files: List<Path>, sourceRoot: Path? = null): NgramSourceReadResult {
        return readFiles(files, sourceRoot, emptyMap())
    }

    private fun readFiles(
        files: List<Path>,
        sourceRoot: Path? = null,
        allowedOrdersBySource: Map<String, Set<Int>>,
    ): NgramSourceReadResult {
        val allRules = mutableListOf<NgramRule>()
        val sourceFiles = mutableListOf<String>()
        var sourceRowCount = 0

        files.forEach { file ->
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
                allowedOrdersBySource[sourceName]?.let { allowedOrders ->
                    require(order in allowedOrders) {
                        "N-gram source order is not allowed by $NGRAM_SOURCE_SET_MANIFEST: " +
                                "file=$sourceName line=$lineNumber order=$order allowed=${allowedOrders.sorted()}"
                    }
                }
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
