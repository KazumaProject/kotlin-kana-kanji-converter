package com.kazumaproject.english

import java.nio.file.Files
import java.nio.file.Path

fun main(args: Array<String>) {
    val source = loadEnglishDictionarySource(args)
    require(source.upstream.isNotEmpty()) { "English upstream dictionary is empty" }
    val summary = EnglishDictionaryReport.summarize(source.upstream)
    require(summary.uniqueReadingSurfacePairs == summary.entries) {
        "English upstream dictionary contains duplicate reading/surface rows"
    }
    require(source.runtimeEntries.isNotEmpty()) { "English dictionary has no usable runtime entries" }
    require(source.runtimeEntries.all {
        EnglishDictionaryQuality.assess(it, source.allowedCompounds).status == EnglishCandidateStatus.PRIMARY
    }) { "Merged runtime dictionary contains a non-primary candidate" }
    println(
        "Validated English dictionary: upstream=${source.upstream.size}, supplement=${source.supplement.size}, " +
            "baselineRuntime=${source.baselineRuntime.size}, runtime=${source.runtimeEntries.size}, " +
            "addedPairs=${source.addedEntries.size}, newEnglishSurfaces=${source.newEnglishSurfaces}, " +
            "addedReadingsForExistingSurfaces=${source.addedReadingsForExistingSurfaces}",
    )
}

internal fun loadEnglishDictionarySource(args: Array<String>): EnglishDictionarySource = EnglishDictionarySource.load(
    Path.of(englishOption(args, "--input") ?: error("Missing required option: --input")),
    Path.of(englishOption(args, "--supplement") ?: "src/main/english/reading-supplement.tsv"),
    findGenericNounId(Path.of(englishOption(args, "--id-def") ?: "src/main/resources/id.def")),
)

internal fun findGenericNounId(idDef: Path): Int {
    require(Files.isRegularFile(idDef)) { "Mozc id.def was not found: $idDef" }
    return Files.newBufferedReader(idDef).useLines { lines ->
        lines.map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith('#') }.mapNotNull { line ->
            val separator = line.indexOfFirst(Char::isWhitespace)
            require(separator > 0) { "Malformed id.def line: $line" }
            val id = line.substring(0, separator).toIntOrNull() ?: error("Invalid id.def ID: $line")
            id.takeIf { line.substring(separator + 1).trim() == "名詞,一般,*,*,*,*,*" }
        }.firstOrNull() ?: error("No generic-noun context was found in id.def: $idDef")
    }
}

internal fun englishOption(args: Array<String>, name: String): String? {
    val index = args.indexOf(name)
    if (index < 0) return null
    return args.getOrNull(index + 1)?.takeUnless { it.startsWith("--") }
        ?: error("Missing value for option: $name")
}
