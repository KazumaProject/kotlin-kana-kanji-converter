package com.kazumaproject.english

import java.nio.file.Path

fun main(args: Array<String>) {
    val input = requiredReportOption(args, "--input")
    val output = requiredReportOption(args, "--output")
    val summary = requiredReportOption(args, "--summary")
    val quality = optionalReportOption(args, "--quality-output")
        ?: Path.of(output).parent?.resolve("english-dictionary-quality.tsv")
        ?: Path.of("english-dictionary-quality.tsv")
    val entries = EnglishDictionaryBuilder().parse(Path.of(input))

    EnglishDictionaryReport.writeCandidates(entries, Path.of(output))
    EnglishDictionaryReport.writeQuality(entries, quality)
    EnglishDictionaryReport.writeSummary(entries, Path.of(summary), input)

    val report = EnglishDictionaryReport.summarize(entries)
    println(
        "Wrote English dictionary report: entries=${report.entries}, " +
                "uniqueReadings=${report.uniqueReadings}, output=$output, quality=$quality, summary=$summary",
    )
}

private fun requiredReportOption(args: Array<String>, name: String): String {
    val index = args.indexOf(name)
    return args.getOrNull(index + 1)?.takeUnless { it.startsWith("--") }
        ?: error("Missing required option: $name")
}

private fun optionalReportOption(args: Array<String>, name: String): Path? {
    val index = args.indexOf(name)
    if (index < 0) return null
    return args.getOrNull(index + 1)?.takeUnless { it.startsWith("--") }?.let(Path::of)
        ?: error("Missing value for option: $name")
}
