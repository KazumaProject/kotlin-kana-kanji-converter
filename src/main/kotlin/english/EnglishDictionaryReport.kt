package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.util.Locale

data class EnglishDictionarySummary(
    val entries: Int,
    val uniqueReadings: Int,
    val uniqueSurfaces: Int,
    val uniqueReadingSurfacePairs: Int,
    val singleCandidateReadings: Int,
    val multiCandidateReadings: Int,
    val maximumCandidatesForOneReading: Int,
    val minimumReadingLength: Int,
    val maximumReadingLength: Int,
    val minimumCost: Int,
    val maximumCost: Int,
)

data class EnglishReadingCandidates(
    val reading: String,
    val candidates: List<Dictionary>,
)

object EnglishDictionaryReport {

    fun groupByReading(entries: List<Dictionary>): List<EnglishReadingCandidates> =
        entries
            .groupBy(Dictionary::yomi)
            .toSortedMap(compareBy<String>({ it.length }, { it }))
            .map { (reading, candidates) ->
                EnglishReadingCandidates(
                    reading = reading,
                    candidates = candidates.sortedWith(compareBy<Dictionary>({ it.cost }, { it.tango })),
                )
            }

    fun summarize(entries: List<Dictionary>): EnglishDictionarySummary {
        val grouped = groupByReading(entries)
        val pairs = entries.map { it.yomi to it.tango }.toSet()
        return EnglishDictionarySummary(
            entries = entries.size,
            uniqueReadings = grouped.size,
            uniqueSurfaces = entries.map(Dictionary::tango).toSet().size,
            uniqueReadingSurfacePairs = pairs.size,
            singleCandidateReadings = grouped.count { it.candidates.size == 1 },
            multiCandidateReadings = grouped.count { it.candidates.size > 1 },
            maximumCandidatesForOneReading = grouped.maxOfOrNull { it.candidates.size } ?: 0,
            minimumReadingLength = grouped.minOfOrNull { it.reading.length } ?: 0,
            maximumReadingLength = grouped.maxOfOrNull { it.reading.length } ?: 0,
            minimumCost = entries.minOfOrNull { it.cost.toInt() } ?: 0,
            maximumCost = entries.maxOfOrNull { it.cost.toInt() } ?: 0,
        )
    }

    /**
     * Writes one row per source reading. Every source row is retained in one
     * of the three candidate columns, so the report is both a usable overview
     * and a complete quality audit.
     */
    fun writeCandidates(entries: List<Dictionary>, output: Path) {
        val assessments = EnglishDictionaryQuality.assessAll(entries)
        val grouped = assessments
            .groupBy { it.source.yomi }
            .toSortedMap(compareBy<String>({ it.length }, { it }))
        output.parent?.let(Files::createDirectories)
        Files.newBufferedWriter(output, StandardCharsets.UTF_8).use { writer ->
            writer.appendLine(
                "reading\tnormalized_reading\tcandidate_count\tprimary_count\t" +
                        "review_count\texcluded_count\tprimary_candidates\t" +
                        "review_candidates\texcluded_candidates",
            )
            grouped.forEach { (reading, readingAssessments) ->
                val sorted = readingAssessments.sortedWith(candidateComparator)
                val primary = sorted.filter { it.status == EnglishCandidateStatus.PRIMARY }
                val review = sorted.filter { it.status == EnglishCandidateStatus.REVIEW }
                val excluded = sorted.filter { it.status == EnglishCandidateStatus.EXCLUDED }
                writer.append(reading)
                writer.append('\t')
                writer.appendLine(
                    listOf(
                        EnglishDictionaryQuality.normalizeReading(reading),
                        sorted.size.toString(),
                        primary.size.toString(),
                        review.size.toString(),
                        excluded.size.toString(),
                        primary.joinToString(" | ") { formatCandidate(it) },
                        review.joinToString(" | ") { formatCandidate(it) },
                        excluded.joinToString(" | ") { formatCandidate(it) },
                    ).joinToString("\t"),
                )
            }
        }
    }

    /** Writes one row for every source entry with the exact quality decision and flags. */
    fun writeQuality(entries: List<Dictionary>, output: Path) {
        output.parent?.let(Files::createDirectories)
        Files.newBufferedWriter(output, StandardCharsets.UTF_8).use { writer ->
            writer.appendLine(
                "entry_index\treading\tnormalized_reading\tenglish_candidate\t" +
                        "normalized_surface\tsource_cost\truntime_cost\tstatus\tscore\tflags",
            )
            EnglishDictionaryQuality.assessAll(entries).forEachIndexed { index, assessment ->
                writer.appendLine(
                    listOf(
                        (index + 1).toString(),
                        assessment.source.yomi,
                        assessment.normalizedReading,
                        assessment.source.tango,
                        assessment.normalizedSurface,
                        assessment.source.cost.toString(),
                        assessment.runtimeCost?.toString().orEmpty(),
                        assessment.status.code(),
                        assessment.score.toString(),
                        assessment.flags.joinToString(",") { it.code }.ifEmpty { "-" },
                    ).joinToString("\t"),
                )
            }
        }
    }

    fun writeSummary(
        entries: List<Dictionary>,
        output: Path,
        sourceDescription: String,
    ) {
        output.parent?.let(Files::createDirectories)
        val summary = summarize(entries)
        val quality = EnglishDictionaryQuality.summarize(entries)
        val duplicateRows = entries.size - summary.uniqueReadingSurfacePairs
        val averageCandidates = if (summary.uniqueReadings == 0) {
            0.0
        } else {
            summary.entries.toDouble() / summary.uniqueReadings
        }

        Files.newBufferedWriter(output, StandardCharsets.UTF_8).use { writer ->
            writer.appendLine("# JapaneseCorpus 読み→英語辞書 集計")
            writer.appendLine()
            writer.appendLine("- source: $sourceDescription")
            writer.appendLine("- entries: ${summary.entries}")
            writer.appendLine("- unique readings: ${summary.uniqueReadings}")
            writer.appendLine("- unique English surfaces: ${summary.uniqueSurfaces}")
            writer.appendLine("- unique reading/surface pairs: ${summary.uniqueReadingSurfacePairs}")
            writer.appendLine("- duplicate rows: $duplicateRows")
            writer.appendLine("- readings with one candidate: ${summary.singleCandidateReadings}")
            writer.appendLine("- readings with multiple candidates: ${summary.multiCandidateReadings}")
            writer.appendLine("- maximum candidates for one reading: ${summary.maximumCandidatesForOneReading}")
            writer.appendLine("- reading length (Kotlin characters): ${summary.minimumReadingLength}..${summary.maximumReadingLength}")
            writer.appendLine("- cost range: ${summary.minimumCost}..${summary.maximumCost}")
            writer.appendLine("- average candidates per reading: ${String.format(Locale.ROOT, "%.3f", averageCandidates)}")
            writer.appendLine()
            writer.appendLine("## 品質判定")
            writer.appendLine()
            writer.appendLine("- primary entries: ${quality.primaryEntries}")
            writer.appendLine("- review entries: ${quality.reviewEntries}")
            writer.appendLine("- excluded entries: ${quality.excludedEntries}")
            writer.appendLine("- clean runtime entries after normalization/deduplication: ${quality.runtimeEntries}")
            writer.appendLine("- clean runtime readings: ${quality.runtimeReadings}")
            writer.appendLine()
            writer.appendLine("`primary` は直接辞書生成時に完全な読みと発音が一致した候補、`review` は説明文・定義断片・未許可の複合語、`excluded` は括弧注釈・母音反復読み・数値表記・感嘆表現・機能語・間投詞・読み記号・接辞・未完の省略表現です。括弧注釈は表記を切り詰めず、原文のまま監査用に保持します。実行時辞書には全 primary 候補を残し、同じ読みと英語表記の重複だけを除去します。")
            writer.appendLine()
            writer.appendLine("### フラグ件数")
            writer.appendLine()
            quality.flagCounts.forEach { (flag, count) ->
                writer.appendLine("- `${flag.code}`: $count")
            }
            writer.appendLine()
            writer.appendLine("## 変換できる読みの条件")
            writer.appendLine()
            writer.appendLine("JapaneseCorpus の生成条件により、JMdict の読みが Unicode カタカナブロックだけで構成されたものを対象にし、NFKC 正規化後にひらがなへ変換しています。")
            writer.appendLine("そのため、日本語文全体の英訳辞書ではなく、カタカナ系の読みを入力したときの英語 gloss / 完全な英語 lsource 候補です。")
            writer.appendLine()
            writer.appendLine("全読みごとの候補は同じディレクトリの `english-dictionary-candidates.tsv` に出力し、全${summary.entries}件の個別判定は `english-dictionary-quality.tsv` に出力します。")
        }
    }

    private val candidateComparator = compareBy<EnglishCandidateAssessment>(
        { statusRank(it.status) },
        { it.runtimeCost ?: Int.MAX_VALUE },
        { it.source.tango },
    )

    private fun formatCandidate(assessment: EnglishCandidateAssessment): String {
        val flags = assessment.flags.joinToString(",") { it.code }.ifEmpty { "-" }
        val runtimeCost = assessment.runtimeCost?.let { "; runtime_cost=$it" }.orEmpty()
        val runtimeSurface = assessment.normalizedSurface
            .takeUnless { it == assessment.source.tango }
            ?.let { "; runtime_surface=$it" }
            .orEmpty()
        return "${assessment.source.tango} [cost=${assessment.source.cost}; status=${assessment.status.code()}; score=${assessment.score}; flags=$flags$runtimeSurface$runtimeCost]"
    }

    private fun statusRank(status: EnglishCandidateStatus): Int = when (status) {
        EnglishCandidateStatus.PRIMARY -> 0
        EnglishCandidateStatus.REVIEW -> 1
        EnglishCandidateStatus.EXCLUDED -> 2
    }
}

private fun EnglishCandidateStatus.code(): String = name.lowercase(Locale.ROOT)
