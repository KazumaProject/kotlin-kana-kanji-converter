package com.kazumaproject.feedback

import com.kazumaproject.dictionary.models.Dictionary
import kotlinx.serialization.json.*
import java.io.File
import java.security.MessageDigest

/** Exact reading+literal-surface overlays, shared by Main and the input inventory. */
internal object SystemDictionaryFeedback {
    fun apply(
        baseline: List<Dictionary>,
        source: File = File("src/main/dictionary-feedback/system.json"),
        idDef: File = File("src/main/resources/id.def"),
    ): List<Dictionary> {
        val document = Json.parseToJsonElement(source.readText()).jsonObject
        require(document.getValue("schemaVersion").jsonPrimitive.int == 1)
        val checksum = MessageDigest.getInstance("SHA-256").digest(idDef.readBytes())
            .joinToString("") { "%02x".format(it) }
        require(document.getValue("idDefSha256").jsonPrimitive.content == checksum) { "Feedback id.def changed" }
        val idCount = idDef.readLines().size
        val exclusions = document.getValue("exclusions").jsonArray.map {
            val pair = it.jsonArray
            require(pair.size == 2)
            pair[0].jsonPrimitive.content to pair[1].jsonPrimitive.content
        }.toSet()
        val existing = baseline.mapTo(HashSet()) { it.yomi to it.tango }
        val additions = document.getValue("additions").jsonArray.map {
            val row = it.jsonArray
            require(row.size == 5)
            val reading = row[0].jsonPrimitive.content
            val surface = row[4].jsonPrimitive.content
            val left = row[1].jsonPrimitive.int
            val right = row[2].jsonPrimitive.int
            val cost = row[3].jsonPrimitive.int
            require(reading.isNotEmpty() && surface.isNotEmpty())
            require(left in 0 until idCount && right in 0 until idCount && cost in Short.MIN_VALUE..Short.MAX_VALUE)
            Dictionary(reading, left.toShort(), right.toShort(), cost.toShort(), surface)
        }.distinct().filter { (it.yomi to it.tango) !in existing }
        return (baseline + additions).filter { (it.yomi to it.tango) !in exclusions }
    }
}
