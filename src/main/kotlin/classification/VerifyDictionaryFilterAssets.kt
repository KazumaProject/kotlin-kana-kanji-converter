package com.kazumaproject.classification

import com.kazumaproject.specialist.readDictionary
import kotlinx.serialization.json.*
import java.io.File
import java.util.zip.ZipFile

/** Read back every direct dictionary entry, without printing private filter records. */
fun main(args: Array<String>) {
    require(args.size == 4 && args[0] == "--archive" && args[2] == "--kind" && args[3] in setOf("base", "replacement")) {
        "Usage: --archive <dictionary.zip> --kind <base|replacement>"
    }
    val filter = DictionaryFilter.fromEnvironment()
    fun categoryIds(path: String): List<String> = Json.parseToJsonElement(File(path).readText()).jsonObject
        .getValue("categories").jsonArray.map { it.jsonObject.getValue("id").jsonPrimitive.content }
    val categories = categoryIds("src/main/classification/categories.json") +
        categoryIds("src/main/specialist/categories.json")
    val sources = mutableListOf("system", "english_reading", "single_kanji", "emoji", "emoticon", "symbol", "reading_correction", "kotowaza")
    sources += categories.filter { args[3] == "base" || it != "person" }.map { "categories/$it" }
    if (args[3] == "replacement") {
        val taxonomy = Json.parseToJsonElement(File("src/main/classification/person-taxonomy.json").readText()).jsonObject
        sources += taxonomy.getValue("categories").jsonArray.map { it.jsonObject }
            .filter { it.getValue("standard_enabled").jsonPrimitive.boolean }
            .map { "categories/person/${it.getValue("id").jsonPrimitive.content}" }
    }
    var entries = 0L
    ZipFile(File(args[1])).use { zip ->
        if (args[3] == "replacement") {
            val manifest = zip.getEntry("dictionary-distribution-manifest.json") ?: error("Missing distribution manifest")
            val metadata = zip.getInputStream(manifest).bufferedReader().use { Json.parseToJsonElement(it.readText()).jsonObject }
            check(metadata.getValue("filterRevision").jsonPrimitive.content == filter.revision) {
                "Dictionary filter revision differs from the packaged manifest"
            }
        }
        sources.forEach { source ->
            val words = readDictionary(zip, source)
            check(words.none { filter.contains(it.yomi, it.tango) }) { "Filtered dictionary entry found in $source" }
            entries += words.size
        }
    }
    println("Verified dictionary filters: revision=${filter.revision}, dictionaries=${sources.size}, records=$entries")
}
