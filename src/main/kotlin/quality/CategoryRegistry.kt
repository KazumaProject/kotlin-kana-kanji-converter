package com.kazumaproject.quality

import kotlinx.serialization.json.*

/** Definitions are shared with the local worker and versioned independently of output counts. */
object CategoryRegistry {
    val definition: JsonObject by lazy {
        val stream = CategoryRegistry::class.java.getResourceAsStream("/dictionary-quality/categories.json")
            ?: error("Missing category definitions")
        stream.use { Json.parseToJsonElement(it.bufferedReader().readText()).jsonObject }
    }
    val all: List<String> get() = definition.getValue("categories").jsonArray.map { it.jsonObject.getValue("id").jsonPrimitive.content }
    val core: List<String> get() = definition.getValue("categories").jsonArray.filter { it.jsonObject.getValue("core").jsonPrimitive.boolean }.map { it.jsonObject.getValue("id").jsonPrimitive.content }
    fun active(manifest: JsonObject, requireCore: Boolean = false): List<String> {
        val selected = manifest["categories"]?.jsonObject?.keys?.toList() ?: manifest.getValue("artifacts").jsonObject.keys.filter { it.contains('/') }.map { it.substringBefore('/') }.distinct()
        require((!requireCore || selected.containsAll(core)) && selected.all { it in all }) { "Unknown or missing core category in manifest" }
        return all.filter { it in selected }
    }
}
