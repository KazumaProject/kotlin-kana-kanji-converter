package com.kazumaproject.english

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption.APPEND

fun main(args: Array<String>) {
    val source = loadEnglishDictionarySource(args)
    val output = Path.of(englishOption(args, "--output") ?: error("Missing required option: --output"))
    val summary = Path.of(englishOption(args, "--summary") ?: error("Missing required option: --summary"))
    val quality = Path.of(englishOption(args, "--quality-output")
        ?: output.resolveSibling("english-dictionary-quality.tsv").toString())
    EnglishDictionaryReport.writeCandidates(source.entries, output, source.allowedCompounds, source.assessments)
    EnglishDictionaryReport.writeQuality(source.entries, quality, source.allowedCompounds, source.assessments)
    EnglishDictionaryReport.writeSummary(source.entries, summary, "upstream + reading-supplement.tsv", source.allowedCompounds, source.assessments)
    Files.writeString(summary, """

        ## 補完辞書の差分

        - upstream source entries: ${source.upstream.size}
        - supplemental source entries: ${source.supplement.size}
        - baseline runtime entries: ${source.baselineRuntime.size}
        - merged runtime entries: ${source.runtimeEntries.size}
        - added reading/surface pairs: ${source.addedEntries.size}
        - existing pairs with changed cost or surface: ${source.changedExistingEntries.size}
        - new English surfaces (case insensitive): ${source.newEnglishSurfaces}
        - added readings for existing English surfaces: ${source.addedReadingsForExistingSurfaces}
        - explicitly registered variant rows (cost 12800): ${source.supplement.count { it.dictionary.cost.toInt() == 12800 }}

        追加ペアと新しい英語表記の数は異なります。同じ表記の読み揺れは個別のペアとして数えます。
        採用された全行は merged-runtime.tsv、補完の根拠は supplement-sources.tsv に記録します。
        これらは辞書内容の確認結果であり、実端末のIME表示・最終順位の検証結果ではありません。
        """.trimIndent() + "\n", APPEND)
    Files.newBufferedWriter(output.resolveSibling("merged-runtime.tsv")).use { writer ->
        writer.appendLine("reading\tleft_id\tright_id\tcost\tsurface")
        source.runtimeEntries.forEach { writer.appendLine("${it.yomi}\t${it.leftId}\t${it.rightId}\t${it.cost}\t${it.tango}") }
    }
    Files.newBufferedWriter(output.resolveSibling("supplement-sources.tsv")).use { writer ->
        writer.appendLine("reading\tsurface\tcost\tsource\tnote")
        source.supplement.forEach {
            writer.appendLine("${it.dictionary.yomi}\t${it.dictionary.tango}\t${it.dictionary.cost}\t${it.source}\t${it.note}")
        }
    }
    val baselinePath = englishOption(args, "--baseline-runtime")?.let(Path::of)
    val baseline = baselinePath?.let(EnglishWordCoverage::readBaseline) ?: source.legacyRuntime
    val changes = EnglishDictionaryChanges.compare(baseline, source.runtimeEntries)
    EnglishDictionaryChanges.write(changes, output.resolveSibling("runtime-changes.tsv"))
    Files.newBufferedWriter(output.resolveSibling("candidate-review.tsv")).use { writer ->
        writer.appendLine("reading\tsurface\tdecision\toutput_surface\tsource\treason")
        source.entries.distinctBy { it.yomi to it.tango }.forEach { entry ->
            val decision = source.review.decisions[entry.yomi to entry.tango]
            writer.appendLine(listOf(entry.yomi, entry.tango, if (decision == null) "unreviewed" else if (decision.keep) "keep" else "exclude",
                decision?.outputSurface ?: "-", decision?.source ?: "-", decision?.reason ?: "未レビューのため配布しない").joinToString("\t"))
        }
    }
    Files.writeString(summary, "\n## 採用レビューと差分\n\n" +
        "- review SHA-256: `${EnglishWordCoverage.sha256(Path.of(englishOption(args, "--candidate-review") ?: "src/main/english/candidate-review.tsv"))}`\n" +
        "- baseline: ${baselinePath?.toString() ?: "同じ入力に従来の大小文字をまとめる処理を適用（過去の配布との比較ではない）"}\n" +
        "- baseline pairs: ${baseline.size}\n" +
        "- baseline SHA-256: ${baselinePath?.let(EnglishWordCoverage::sha256) ?: "not applicable"}\n" +
        "- changes: ${changes.groupingBy { it.kind }.eachCount().toSortedMap()}\n" +
        "- unreviewed input rows: ${source.assessments.count { EnglishQualityFlag.UNREVIEWED_CANDIDATE in it.flags }}\n" +
        "- editorially excluded input rows: ${source.assessments.count { EnglishQualityFlag.REVIEW_EXCLUDED in it.flags }}\n", APPEND)
    println("Wrote merged English dictionary report: runtime=${source.runtimeEntries.size}, addedPairs=${source.addedEntries.size}, output=$output")
}
