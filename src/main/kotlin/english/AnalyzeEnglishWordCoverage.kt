package com.kazumaproject.english

import java.nio.file.Path

fun main(args: Array<String>) {
    val acceptedOptions = setOf("--word-list", "--baseline-runtime", "--input", "--supplement", "--id-def", "--output", "--review-decisions", "--candidate-review")
    require(args.size % 2 == 0) { "Expected option/value pairs" }
    val options = args.toList().chunked(2)
    require(options.all { it[0] in acceptedOptions && !it[1].startsWith("--") }) { "Unknown option or missing option value" }
    require(options.map { it[0] }.distinct().size == options.size) { "Duplicate CLI option" }
    fun requiredPath(name: String): Path = Path.of(englishOption(args, name) ?: error("Missing required option: $name"))
    val wordList = requiredPath("--word-list")
    val baseline = requiredPath("--baseline-runtime")
    val output = requiredPath("--output")
    val source = loadEnglishDictionarySource(args)
    val targets = EnglishWordCoverage.withAdditionalWords(EnglishWordCoverage.readWordList(wordList))
    val decisions = englishOption(args, "--review-decisions")?.let { EnglishWordCoverage.readDecisions(Path.of(it)) }.orEmpty()
    val coverage = EnglishWordCoverage(targets, EnglishWordCoverage.readBaseline(baseline), source.runtimeEntries, decisions)
    coverage.write(output, EnglishWordCoverage.sha256(wordList), EnglishWordCoverage.sha256(baseline))
    println("Audited English headwords: targets=${coverage.rows.size}, " + EnglishWordCoverageStatus.entries.joinToString(", ") { status ->
        "${status.code}=${coverage.rows.count { it.status == status }}"
    } + ", addedPairs=${coverage.addedPairs.size}, output=$output")
}
