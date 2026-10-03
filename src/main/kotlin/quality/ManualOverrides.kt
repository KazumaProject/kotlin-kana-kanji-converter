package com.kazumaproject.quality

import java.io.File

/** Exact, source-scoped decisions; no regex matching or inherited category labels. */
class ManualOverrides(file: File? = null) {
    data class Decision(val action: String, val reading: String, val surface: String, val categories: Set<String>, val evidence: String)
    private val decisions = hashMapOf<Triple<String, String, String>, MutableList<Decision>>()
    private val classifications = hashMapOf<Triple<String, String, String>, Classification>()
    init {
        if (file != null) {
            require(file.isFile) { "Missing overrides: $file" }
            file.readLines().forEachIndexed { index, line ->
                if (line.isBlank() || line.startsWith("#") || line.startsWith("source\t")) return@forEachIndexed
                val f = line.split('\t')
                require(f.size == 8 && f[0] in SupplementalSources.files && f[3] in setOf("include", "exclude", "hold")) { "$file:${index + 1}: invalid override" }
                val categories = f[6].split(',').filter { it.isNotBlank() && it != "-" }.toSet()
                require(categories.all { it in dictionaryCategories } && f[7].startsWith("https://")) { "$file:${index + 1}: category or evidence missing" }
                if (f[3] == "include") require(f[4].isNotBlank() && f[5].isNotBlank() && categories.isNotEmpty() && "unclassified" !in categories) { "$file:${index + 1}: incomplete inclusion" }
                val key = Triple(f[0], f[1], f[2])
                val decision = Decision(f[3], f[4], f[5], categories, f[7])
                decisions.getOrPut(key) { mutableListOf() }.add(decision)
                if (f[3] == "include") {
                    val output = Triple(f[0], f[4], f[5])
                    val old = classifications[output]
                    classifications[output] = Classification(old?.categories.orEmpty() + categories, listOfNotNull(old?.evidence, f[7]).joinToString(","))
                }
            }
            decisions.values.forEach { rows -> require(rows.map { it.action }.distinct().size == 1) { "Conflicting override actions" } }
        }
    }
    fun normalization(row: SourceRow): CandidateNormalizer.Result? = decisions[Triple(row.source, row.word.yomi, row.word.tango)]?.let { rows ->
        CandidateNormalizer.Result(rows.filter { it.action == "include" }.map { row.word.copy(yomi = it.reading, tango = it.surface) }, "manual-${rows.first().action}:${rows.joinToString(",") { it.evidence }}", if (rows.any { it.action == "include" }) "accepted" else if (rows.all { it.action == "exclude" }) "excluded" else "held")
    }
    fun classification(row: SourceRow) = classifications[Triple(row.source, row.word.yomi, row.word.tango)]
}
