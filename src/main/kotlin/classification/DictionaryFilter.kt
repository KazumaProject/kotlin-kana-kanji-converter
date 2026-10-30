package com.kazumaproject.classification

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.isHiraganaOrKatakana
import com.kazumaproject.specialist.effectiveSurface
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files

/** Exact reading/surface exclusions from one immutable private-repository snapshot. */
class DictionaryFilter private constructor(
    val revision: String,
    private val pairs: Set<Pair<String, String>>,
) {
    private val readings = pairs.mapTo(HashSet()) { it.first }

    fun contains(reading: String, surface: String): Boolean = (reading to surface) in pairs

    /** Also exclude the surface that the current dictionary encoding reconstructs. */
    fun filterRecords(entries: Collection<Dictionary>, skipKanaOnlyTango: Boolean = false): List<Dictionary> {
        var retained = entries.filterNot { contains(it.yomi, it.tango) }
        if (retained.none { it.yomi in readings }) return retained
        while (true) {
            val literalSurfaces = retained.asSequence()
                .map { it.tango }
                .filter { !skipKanaOnlyTango || !it.isHiraganaOrKatakana() }
                .toHashSet()
            val next = retained.filterNot { entry ->
                entry.yomi in readings && contains(entry.yomi, effectiveSurface(entry, literalSurfaces))
            }
            if (next.size == retained.size) return retained
            retained = next
        }
    }

    companion object {
        private val revisionPattern = Regex("[0-9a-f]{40}")
        private val categoryPattern = Regex("[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*\\.jsonl")
        private val statuses = setOf("hold", "source_reviewed", "model_provisional")

        fun empty(): DictionaryFilter = DictionaryFilter("0".repeat(40), emptySet())

        fun fromEnvironment(): DictionaryFilter {
            val path = System.getenv("DICTIONARY_FILTER_SNAPSHOT")
                ?: error("DICTIONARY_FILTER_SNAPSHOT is required for dictionary generation")
            return load(File(path))
        }

        fun load(directory: File): DictionaryFilter {
            require(directory.isDirectory) { "Dictionary filter snapshot is missing" }
            val manifest = Json.parseToJsonElement(File(directory, "manifest.json").readText()).jsonObject
            require(manifest.keys == setOf("schemaVersion") && manifest.getValue("schemaVersion").jsonPrimitive.int == 1) {
                "Unsupported dictionary filter schema"
            }
            val metadata = Json.parseToJsonElement(File(directory, "snapshot.json").readText()).jsonObject
            val revision = metadata.getValue("revision").jsonPrimitive.content
            require(metadata.getValue("schemaVersion").jsonPrimitive.int == 1 &&
                metadata.getValue("repository").jsonPrimitive.content == "KazumaProject/dictionary_filter_list" &&
                revision.matches(revisionPattern)) { "Invalid dictionary filter snapshot metadata" }
            val categories = File(directory, "categories")
            require(categories.isDirectory) { "Dictionary filter categories are missing" }
            val files = categories.walkTopDown().filter { it.isFile && it.extension == "jsonl" }.sortedBy {
                it.relativeTo(categories).invariantSeparatorsPath
            }.toList()
            require(files.isNotEmpty()) { "Dictionary filter categories are empty" }
            val pairs = mutableSetOf<Pair<String, String>>()
            files.forEach { file ->
                val path = file.relativeTo(categories).invariantSeparatorsPath
                require(path.matches(categoryPattern) && !Files.isSymbolicLink(file.toPath())) {
                    "Invalid dictionary filter category path"
                }
                val seen = mutableSetOf<Pair<String, String>>()
                file.bufferedReader().useLines { lines ->
                    lines.forEachIndexed { index, line ->
                        val row = Json.parseToJsonElement(line).jsonObject
                        require(row.keys == setOf("reading", "surface", "status", "evidence")) {
                            "Invalid dictionary filter record at $path:${index + 1}"
                        }
                        require(listOf("reading", "surface", "status").all { row.getValue(it).jsonPrimitive.isString }) {
                            "Invalid dictionary filter record at $path:${index + 1}"
                        }
                        val reading = row.getValue("reading").jsonPrimitive.content
                        val surface = row.getValue("surface").jsonPrimitive.content
                        val status = row.getValue("status").jsonPrimitive.content
                        val evidence = row.getValue("evidence").jsonArray
                        require(reading.isNotEmpty() && surface.isNotEmpty() &&
                            (reading + surface).none { it in "\u0000\r\n\t" } && status in statuses &&
                            evidence.isNotEmpty() && evidence.all { it is JsonObject }) {
                            "Invalid dictionary filter record at $path:${index + 1}"
                        }
                        val pair = reading to surface
                        require(seen.add(pair)) { "Duplicate dictionary filter record at $path:${index + 1}" }
                        pairs.add(pair)
                    }
                }
            }
            require(pairs.isNotEmpty()) { "Dictionary filter has no active records" }
            return DictionaryFilter(revision, pairs)
        }
    }
}
