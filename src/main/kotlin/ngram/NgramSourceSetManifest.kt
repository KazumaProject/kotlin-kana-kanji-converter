package com.kazumaproject.ngram

import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.invariantSeparatorsPathString
import kotlin.io.path.isRegularFile
import kotlin.io.path.name

const val NGRAM_SOURCE_SET_MANIFEST = "sources_manifest.tsv"

data class NgramSourceSetEntry(
    val enabled: Boolean,
    val file: String,
    val kind: String,
    val orders: Set<Int>,
    val description: String,
    val lineNumber: Int,
)

data class NgramSourceSet(
    val entries: List<NgramSourceSetEntry>,
) {
    val enabledFiles: List<String>
        get() = entries.filter { it.enabled }.map { it.file }
}

object NgramSourceSetManifestReader {
    fun read(sourceDirectory: Path): NgramSourceSet? {
        val manifest = sourceDirectory.resolve(NGRAM_SOURCE_SET_MANIFEST)
        if (!manifest.isRegularFile()) {
            return null
        }
        val rows = Files.readAllLines(manifest)
        require(rows.isNotEmpty()) { "N-gram source manifest is empty: $manifest" }
        val header = splitPreservingEmpty(rows.first(), '\t')
            .map { it.trim().lowercase() }
            .withIndex()
            .associate { it.value to it.index }
        listOf("enabled", "file", "kind", "orders", "description").forEach { column ->
            require(column in header) {
                "N-gram source manifest is missing column '$column': $manifest"
            }
        }

        val entries = rows.drop(1).mapIndexedNotNull { index, rawLine ->
            val lineNumber = index + 2
            if (rawLine.isBlank() || rawLine.trimStart().startsWith("#")) {
                return@mapIndexedNotNull null
            }
            val columns = splitPreservingEmpty(rawLine, '\t')
            fun value(name: String): String = columns.getOrElse(header.getValue(name)) { "" }.trim()
            val file = normalizeManifestPath(value("file"), manifest, lineNumber)
            val orders = parseOrders(value("orders"), manifest, lineNumber)
            NgramSourceSetEntry(
                enabled = parseEnabled(value("enabled"), manifest, lineNumber),
                file = file,
                kind = value("kind").ifEmpty { "presence" },
                orders = orders,
                description = value("description"),
                lineNumber = lineNumber,
            )
        }

        val seenFiles = mutableMapOf<String, NgramSourceSetEntry>()
        entries.forEach { entry ->
            seenFiles.putIfAbsent(entry.file, entry)?.let { first ->
                error(
                    "Duplicate N-gram source manifest file entry: file=${entry.file}, " +
                            "firstLine=${first.lineNumber}, secondLine=${entry.lineNumber}"
                )
            }
            require(entry.kind == "presence") {
                "Unsupported N-gram source kind at $manifest:${entry.lineNumber}: ${entry.kind}"
            }
            require(entry.orders.all { it in 1..NGRAM_SECTION_COUNT }) {
                "Invalid N-gram source orders at $manifest:${entry.lineNumber}: ${entry.orders}"
            }
            val sourceFile = sourceDirectory.resolve(entry.file).normalize()
            require(sourceFile.startsWith(sourceDirectory.normalize())) {
                "N-gram source manifest path escapes source directory at $manifest:${entry.lineNumber}: ${entry.file}"
            }
            require(sourceFile.isRegularFile()) {
                "N-gram source manifest references missing file at $manifest:${entry.lineNumber}: ${entry.file}"
            }
        }
        return NgramSourceSet(entries)
    }

    fun discoverSourceFiles(sourceDirectory: Path): List<Path> {
        read(sourceDirectory)?.let { sourceSet ->
            return sourceSet.enabledFiles.map { sourceDirectory.resolve(it).normalize() }
        }
        return Files.walk(sourceDirectory).use { stream ->
            stream
                .filter { it.isRegularFile() }
                .filter { it.name.endsWith(".tsv") }
                .filter { it.name != NGRAM_SOURCE_SET_MANIFEST }
                .sorted { left, right ->
                    left.relativeToSource(sourceDirectory).compareTo(right.relativeToSource(sourceDirectory))
                }
                .toList()
        }
    }

    private fun parseEnabled(value: String, manifest: Path, lineNumber: Int): Boolean {
        return when (value.lowercase()) {
            "true", "1", "yes", "y", "enabled" -> true
            "false", "0", "no", "n", "disabled" -> false
            else -> error("Invalid enabled value at $manifest:$lineNumber: $value")
        }
    }

    private fun parseOrders(value: String, manifest: Path, lineNumber: Int): Set<Int> {
        if (value == "*" || value.equals("all", ignoreCase = true)) {
            return (1..NGRAM_SECTION_COUNT).toSet()
        }
        val orders = value.split(',')
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .map {
                it.toIntOrNull()
                    ?: error("Invalid order value at $manifest:$lineNumber: $it")
            }
            .toSet()
        require(orders.isNotEmpty()) { "orders must not be empty at $manifest:$lineNumber" }
        return orders
    }

    private fun normalizeManifestPath(value: String, manifest: Path, lineNumber: Int): String {
        require(value.isNotBlank()) { "file must not be blank at $manifest:$lineNumber" }
        require(value.endsWith(".tsv")) { "N-gram source file must end with .tsv at $manifest:$lineNumber: $value" }
        require(value != NGRAM_SOURCE_SET_MANIFEST) {
            "N-gram source manifest cannot include itself at $manifest:$lineNumber"
        }
        val path = Path.of(value)
        require(!path.isAbsolute) { "N-gram source file must be relative at $manifest:$lineNumber: $value" }
        require(path.none { it.toString() == ".." }) {
            "N-gram source file must not contain '..' at $manifest:$lineNumber: $value"
        }
        return path.invariantSeparatorsPathString
    }

    private fun Path.relativeToSource(sourceDirectory: Path): String =
        sourceDirectory.normalize().relativize(normalize()).invariantSeparatorsPathString
}
