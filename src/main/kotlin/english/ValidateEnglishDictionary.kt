package com.kazumaproject.english

import java.nio.file.Files
import java.nio.file.Path

fun main(args: Array<String>) {
    val input = requiredOption(args, "--input")
    val idDef = optionalOption(args, "--id-def")?.let(Path::of)
    val expectedContextId = idDef?.let(::findGenericNounId)
    val entries = EnglishDictionaryBuilder().parse(Path.of(input), expectedContextId)
    require(entries.isNotEmpty()) { "English dictionary source is empty: $input" }

    val summary = EnglishDictionaryReport.summarize(entries)
    require(summary.uniqueReadingSurfacePairs == summary.entries) {
        "English dictionary contains duplicate reading/surface rows: " +
                "entries=${summary.entries}, uniquePairs=${summary.uniqueReadingSurfacePairs}"
    }
    val quality = EnglishDictionaryQuality.summarize(entries)
    val runtimeEntries = EnglishDictionaryQuality.runtimeEntries(entries)
    require(runtimeEntries.isNotEmpty()) {
        "English dictionary has no usable runtime entries after quality filtering: input=$input"
    }
    require(runtimeEntries.all { EnglishDictionaryQuality.assess(it).status == EnglishCandidateStatus.PRIMARY }) {
        "Noise-removed runtime dictionary contains a non-primary candidate: input=$input"
    }
    require(runtimeEntries.size == quality.runtimeEntries) {
        "English dictionary quality summary disagrees with runtime selection: " +
                "summary=${quality.runtimeEntries}, runtime=${runtimeEntries.size}"
    }

    println(
        "Validated English dictionary: entries=${summary.entries}, " +
                "uniqueReadings=${summary.uniqueReadings}, uniqueSurfaces=${summary.uniqueSurfaces}, " +
                "primary=${quality.primaryEntries}, review=${quality.reviewEntries}, " +
                "excluded=${quality.excludedEntries}, cleanRuntime=${quality.runtimeEntries}, " +
                "contextId=${expectedContextId ?: "not checked"}",
    )
}

private fun findGenericNounId(idDef: Path): Int {
    require(Files.isRegularFile(idDef)) { "Mozc id.def was not found: $idDef" }
    var firstNounId: Int? = null
    var genericNounId: Int? = null
    Files.newBufferedReader(idDef).useLines { lines ->
        lines.forEach { rawLine ->
            val trimmed = rawLine.trim()
            if (trimmed.isEmpty() || trimmed.startsWith("#")) return@forEach
            val separator = trimmed.indexOfFirst(Char::isWhitespace)
            require(separator > 0) { "Malformed id.def line: $rawLine" }
            val id = trimmed.substring(0, separator).toIntOrNull()
                ?: error("Invalid id.def ID: $rawLine")
            val feature = trimmed.substring(separator + 1).split(',')
            if (feature.firstOrNull() == "名詞") {
                firstNounId ?: run { firstNounId = id }
                if (genericNounId == null && feature.getOrNull(1) == "一般") genericNounId = id
            }
        }
    }
    return genericNounId ?: firstNounId ?: error("No noun context was found in id.def: $idDef")
}

private fun requiredOption(args: Array<String>, name: String): String =
    optionalOption(args, name) ?: error("Missing required option: $name")

private fun optionalOption(args: Array<String>, name: String): String? {
    val index = args.indexOf(name)
    if (index < 0) return null
    return args.getOrNull(index + 1)?.takeUnless { it.startsWith("--") }
        ?: error("Missing value for option: $name")
}
