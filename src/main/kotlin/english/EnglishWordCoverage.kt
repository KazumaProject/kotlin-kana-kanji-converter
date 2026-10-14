package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.io.InputStream
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.util.Locale

data class EnglishWordTarget(val word: String, val rank: Int?, val origin: String, val sourceWord: String = word)

enum class EnglishWordCoverageStatus(val code: String) {
    EXISTING("existing"), ADDED("added"), EXCLUDED("excluded"), DEFERRED("deferred"),
}

data class EnglishWordReviewDecision(val word: String, val status: String, val reason: String, val location: String)

data class EnglishWordCoverageRow(
    val target: EnglishWordTarget,
    val status: EnglishWordCoverageStatus,
    val reason: String,
    val baselineReadings: List<String>,
    val runtimeReadings: List<String>,
)

/** Exact canonical-headword audit. This does not infer lemmas from runtime spellings or approve readings. */
class EnglishWordCoverage(
    targets: List<EnglishWordTarget>,
    val baselineRuntime: List<Dictionary>,
    val runtimeEntries: List<Dictionary>,
    decisions: List<EnglishWordReviewDecision> = emptyList(),
) {
    val targets: List<EnglishWordTarget> = targets.sortedWith(compareBy({ it.rank ?: Int.MAX_VALUE }, { it.word }))
    val rows: List<EnglishWordCoverageRow>
    val addedPairs: List<Dictionary>
    val removedPairs: Int
    val changedExistingPairs: List<Pair<Dictionary, Dictionary>>
    val newSingleWordSurfaces: Set<String>
    val newNonTargetSingleWordSurfaces: Set<String>
    val addedReadingsForBaselineSurfaces: Int
    val addedReadingsForNewSurfaces: Int
    val addedCompoundPairs: Int

    init {
        require(targets.map { it.word }.toSet().size == targets.size) { "Duplicate canonical target words" }
        require(targets.mapNotNull { it.rank }.toSet().size == targets.count { it.rank != null }) { "Duplicate target ranks" }
        targets.forEach { require(it.word.matches(Regex("[a-z]+|I")) && (it.rank == null || it.rank > 0)) { "Invalid target: $it" } }
        val targetWords = targets.map { it.word }.toSet()
        val decisionMap = linkedMapOf<String, EnglishWordReviewDecision>()
        decisions.forEach { decision ->
            require(decision.word in targetWords) { "${decision.location}: review word is not a target: ${decision.word}" }
            require(decision.status in setOf("deferred", "rejected")) { "${decision.location}: invalid review status: ${decision.status}" }
            require(decision.reason.isNotBlank()) { "${decision.location}: missing review reason" }
            require(decisionMap.putIfAbsent(decision.word, decision) == null) { "${decision.location}: duplicate review word: ${decision.word}" }
        }
        val baselineBySurface = baselineRuntime.groupBy { it.tango }
        val runtimeBySurface = runtimeEntries.groupBy { it.tango }
        rows = this.targets.map { target ->
            val baselineReadings = baselineBySurface[target.word].orEmpty().map { it.yomi }.distinct().sorted()
            val runtimeReadings = runtimeBySurface[target.word].orEmpty().map { it.yomi }.distinct().sorted()
            val policyFlags = surfacePolicyFlags(target.word)
            val decision = decisionMap[target.word]
            require(decision == null || (runtimeReadings.isEmpty() && policyFlags.isEmpty())) {
                "${decision?.location}: review decision contradicts a runtime entry or policy exclusion: ${target.word}"
            }
            val (status, reason) = when {
                policyFlags.isNotEmpty() -> EnglishWordCoverageStatus.EXCLUDED to "Existing runtime quality policy: ${policyFlags.joinToString(",") { it.code }}"
                runtimeReadings.isNotEmpty() && baselineReadings.isNotEmpty() -> EnglishWordCoverageStatus.EXISTING to "Exact canonical surface present in baseline and runtime"
                runtimeReadings.isNotEmpty() -> EnglishWordCoverageStatus.ADDED to "Exact canonical surface newly present in runtime"
                decision != null -> EnglishWordCoverageStatus.DEFERRED to "Review ${decision.status}: ${decision.reason}"
                baselineReadings.isNotEmpty() -> EnglishWordCoverageStatus.DEFERRED to "Baseline surface is no longer emitted; requires review"
                else -> EnglishWordCoverageStatus.DEFERRED to "No confirmed reading registered; pronunciation or reading review remains unresolved"
            }
            EnglishWordCoverageRow(target, status, reason, baselineReadings, runtimeReadings)
        }
        val changes = EnglishDictionaryChanges.compare(baselineRuntime, runtimeEntries)
        addedPairs = changes.filter { it.kind == "added" }.map { it.after!! }
            .sortedWith(compareBy({ it.yomi }, { it.tango }, { it.cost }))
        removedPairs = changes.count { it.kind == "removed" }
        changedExistingPairs = changes.filter { it.before != null && it.after != null }
            .map { it.before!! to it.after!! }.sortedWith(compareBy({ it.second.yomi }, { it.second.tango }))
        val baselineSurfaces = baselineRuntime.map { it.tango }.toSet()
        newSingleWordSurfaces = runtimeEntries.map { it.tango }.filter { isSingleWord(it) && it !in baselineSurfaces }.toSortedSet()
        newNonTargetSingleWordSurfaces = newSingleWordSurfaces.filter { it !in targetWords }.toSortedSet()
        addedReadingsForBaselineSurfaces = addedPairs.count { it.tango in baselineSurfaces && isSingleWord(it.tango) }
        // One reading introduces a new surface; additional readings are counted independently of headwords.
        addedReadingsForNewSurfaces = addedPairs.filter { it.tango in newSingleWordSurfaces }
            .groupBy { it.tango }.values.sumOf { entries -> (entries.map { it.yomi }.distinct().size - 1).coerceAtLeast(0) }
        addedCompoundPairs = addedPairs.count { !isSingleWord(it.tango) }
    }

    fun write(output: Path, wordListSha256: String? = null, baselineSha256: String? = null) {
        Files.createDirectories(output)
        Files.newBufferedWriter(output.resolve("targets.tsv")).use { writer ->
            writer.appendLine("word\tsource_headword\tngsl_rank\torigin\tstatus\treason\tbaseline_readings\truntime_readings")
            rows.forEach { row -> writer.appendLine(listOf(row.target.word, row.target.sourceWord, row.target.rank?.toString().orEmpty(), row.target.origin,
                row.status.code, row.reason, row.baselineReadings.joinToString(","), row.runtimeReadings.joinToString(",")).joinToString("\t")) }
        }
        Files.newBufferedWriter(output.resolve("added-pairs.tsv")).use { writer ->
            writer.appendLine("reading\tleft_id\tright_id\tcost\tsurface\tcategory")
            val targetWords = targets.map { it.word }.toSet()
            addedPairs.forEach { entry ->
                val category = when {
                    !isSingleWord(entry.tango) -> "compound"
                    entry.tango in targetWords -> "target-headword"
                    else -> "non-target-single-word"
                }
                writer.appendLine("${entry.yomi}\t${entry.leftId}\t${entry.rightId}\t${entry.cost}\t${entry.tango}\t$category")
            }
        }
        Files.newBufferedWriter(output.resolve("summary.md")).use { writer ->
            writer.appendLine("# 一般英単語の収録監査")
            writer.appendLine()
            wordListSha256?.let { writer.appendLine("- NGSL input SHA-256: `$it`") }
            baselineSha256?.let { writer.appendLine("- baseline runtime SHA-256: `$it`") }
            writer.appendLine("- target headwords: ${targets.size}")
            EnglishWordCoverageStatus.entries.forEach { status -> writer.appendLine("- ${status.code} headwords: ${rows.count { it.status == status }}") }
            writer.appendLine("- baseline runtime pairs: ${baselineRuntime.size}")
            writer.appendLine("- current runtime pairs: ${runtimeEntries.size}")
            writer.appendLine("- added reading/surface pairs: ${addedPairs.size}")
            writer.appendLine("- removed reading/surface pairs: $removedPairs")
            writer.appendLine("- existing pairs with changed surface, cost, or POS: ${changedExistingPairs.size}")
            writer.appendLine("- new single-word surfaces: ${newSingleWordSurfaces.size}")
            writer.appendLine("- new non-target single-word surfaces: ${newNonTargetSingleWordSurfaces.size}")
            writer.appendLine("- added readings for baseline single-word surfaces: $addedReadingsForBaselineSurfaces")
            writer.appendLine("- extra readings for new single-word surfaces: $addedReadingsForNewSurfaces")
            writer.appendLine("- added compound pairs: $addedCompoundPairs")
            writer.appendLine()
            writer.appendLine("見出し語は NGSL の正規表記と完全一致で照合します。`IT` は `it` の収録として数えません。複合語を単独語の収録として数えず、追加の読みは単語数から分けます。")
            writer.appendLine("NGSL 原本の `TRUE`・`FALSE` だけは一般単語の `true`・`false` に対応させ、source_headword 列に原本表記を保持します。`I` は原本通りとし、一文字の除外方針を適用します。")
            writer.appendLine()
            writer.appendLine("NGSL のこの入力には活用形の対応表がありません。非対象の単独表記を活用形と推測せず、その内訳は未確認として扱います。追加された対象見出し語と既存の活用形・複合語の数は別です。")
            writer.appendLine()
            writer.appendLine("全対象の状態と理由は targets.tsv、追加された採用ペアは added-pairs.tsv、既存ペアの変更は changed-existing-pairs.tsv に記録します。deferred は読みの根拠や既存の統合キーとの衝突などにより未採用の語です。この監査は読みを承認せず、頻度加重の文章カバー率や実端末の候補順位も示しません。")
        }
        Files.newBufferedWriter(output.resolve("changed-existing-pairs.tsv")).use { writer ->
            writer.appendLine("reading\tbaseline_surface\tcurrent_surface\tbaseline_cost\tcurrent_cost\tbaseline_left_id\tcurrent_left_id\tbaseline_right_id\tcurrent_right_id")
            changedExistingPairs.forEach { (old, current) ->
                writer.appendLine("${current.yomi}\t${old.tango}\t${current.tango}\t${old.cost}\t${current.cost}\t${old.leftId}\t${current.leftId}\t${old.rightId}\t${current.rightId}")
            }
        }
    }

    companion object {
        const val NGSL_SHA256 = "2098bab8955a120a9766c6282a51d7d578c6cb0a7d946600d2ffb73ba25a0b44"
        const val NGSL_HEADWORD_COUNT = 2809
        val additionalWords = listOf("deploy", "dependency", "authentication", "authorization", "coroutine", "vendor", "stakeholder",
            "sync", "async", "commit", "branch", "merge", "rebase", "push", "pull", "fetch",
            "cache", "cookie", "session", "token", "endpoint", "webhook", "middleware")
        private val wordListHeader = listOf("Lemma", "SFI Rank", "SFI", "Adjusted Frequency per Million (U)")

        fun readWordList(path: Path, verifyOfficial: Boolean = true): List<EnglishWordTarget> {
            require(Files.isRegularFile(path)) { "NGSL word list was not found: $path" }
            if (verifyOfficial) require(sha256(path) == NGSL_SHA256) { "$path: NGSL 1.2 SHA-256 mismatch; expected $NGSL_SHA256" }
            val targets = Files.newInputStream(path).use { parseWordList(it, path.toString()) }
            if (verifyOfficial) require(targets.size == NGSL_HEADWORD_COUNT) { "$path: expected $NGSL_HEADWORD_COUNT NGSL headwords, got ${targets.size}" }
            return targets
        }

        fun parseWordList(input: InputStream, source: String): List<EnglishWordTarget> = input.bufferedReader().use { reader ->
            val lines = reader.readLines()
            require(lines.isNotEmpty()) { "$source: line=1: missing CSV header" }
            require(parseCsvLine(lines[0], "$source: line=1") == wordListHeader) { "$source: line=1: invalid NGSL CSV header" }
            val seenWords = mutableSetOf<String>()
            val seenRanks = mutableSetOf<Int>()
            val targets = lines.drop(1).mapIndexed { index, line ->
                val location = "$source: line=${index + 2}"
                val fields = parseCsvLine(line, location)
                require(fields.size == 4) { "$location: expected 4 CSV columns" }
                require(fields.all { it.isNotEmpty() && it == it.trim() }) { "$location: blank or padded CSV field" }
                val sourceWord = fields[0]
                val word = when (sourceWord) {
                    "TRUE" -> "true"
                    "FALSE" -> "false"
                    else -> sourceWord
                }
                val rank = fields[1].toIntOrNull()
                require(word.matches(Regex("[a-z]+|I"))) { "$location: expected a canonical single-word lemma: $sourceWord" }
                require(rank != null && rank > 0) { "$location: invalid positive rank: ${fields[1]}" }
                require(fields[2].toDoubleOrNull()?.let { it.isFinite() && it >= 0 } == true &&
                    fields[3].toDoubleOrNull()?.let { it.isFinite() && it >= 0 } == true) { "$location: invalid numeric frequency field" }
                require(seenWords.add(word)) { "$location: duplicate lemma: $word" }
                require(seenRanks.add(rank)) { "$location: duplicate rank: $rank" }
                require(rank == index + 1) { "$location: expected consecutive frequency rank ${index + 1}, got $rank" }
                EnglishWordTarget(word, rank, "ngsl-1.2", sourceWord)
            }
            require(targets.isNotEmpty()) { "$source: line=2: word list is empty" }
            targets
        }

        fun withAdditionalWords(targets: List<EnglishWordTarget>): List<EnglishWordTarget> = targets +
            additionalWords.filter { word -> targets.none { it.word == word } }.map { EnglishWordTarget(it, null, "development-work") }

        fun readBaseline(path: Path): List<Dictionary> = Files.newInputStream(path).use { parseBaseline(it, path.toString()) }

        fun parseBaseline(input: InputStream, source: String): List<Dictionary> = input.bufferedReader().use { reader ->
            val lines = reader.readLines()
            require(lines.firstOrNull() == "reading\tleft_id\tright_id\tcost\tsurface") { "$source: line=1: invalid runtime TSV header" }
            val seenPairs = mutableSetOf<Pair<String, String>>()
            lines.drop(1).mapIndexed { index, line ->
                val location = "$source: line=${index + 2}"
                val fields = line.split('\t')
                require(fields.size == 5 && fields.all { it.isNotBlank() && it == it.trim() && it.none(Char::isISOControl) }) {
                    "$location: expected 5 nonblank unpadded TSV fields"
                }
                require(fields[0].matches(Regex("[ぁ-ゖー]+")) && EnglishDictionaryQuality.normalizeReading(fields[0]) == fields[0]) {
                    "$location: expected normalized hiragana reading"
                }
                val left = fields[1].toIntOrNull()
                val right = fields[2].toIntOrNull()
                val cost = fields[3].toIntOrNull()
                require(left != null && left in 0..Short.MAX_VALUE && right != null && right in 0..Short.MAX_VALUE &&
                    cost != null && cost in 1..Short.MAX_VALUE) { "$location: invalid context ID or cost" }
                val entry = Dictionary(fields[0], left.toShort(), right.toShort(), cost.toShort(), fields[4])
                require(seenPairs.add(pairKey(entry))) { "$location: duplicate reading/surface pair" }
                entry
            }.also { require(it.isNotEmpty()) { "$source: line=2: runtime snapshot is empty" } }
        }

        fun readDecisions(path: Path): List<EnglishWordReviewDecision> = Files.newInputStream(path).use { parseDecisions(it, path.toString()) }

        fun parseDecisions(input: InputStream, source: String): List<EnglishWordReviewDecision> = input.bufferedReader().use { reader ->
            val lines = reader.readLines()
            require(lines.firstOrNull() == "word\tstatus\treason") { "$source: line=1: invalid review TSV header" }
            val words = mutableSetOf<String>()
            lines.drop(1).mapIndexed { index, line ->
                val location = "$source: line=${index + 2}"
                val fields = line.split('\t')
                require(fields.size == 3 && fields.all { it.isNotBlank() && it == it.trim() && it.none(Char::isISOControl) }) {
                    "$location: expected 3 nonblank unpadded review fields"
                }
                require(fields[0].matches(Regex("[a-z]+|I"))) { "$location: invalid canonical word" }
                require(fields[1] in setOf("deferred", "rejected")) { "$location: review status must be deferred or rejected" }
                require(words.add(fields[0])) { "$location: duplicate review word: ${fields[0]}" }
                EnglishWordReviewDecision(fields[0], fields[1], fields[2], location)
            }
        }

        fun sha256(path: Path): String {
            val digest = MessageDigest.getInstance("SHA-256")
            Files.newInputStream(path).use { input ->
                val buffer = ByteArray(8192)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    digest.update(buffer, 0, count)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        }

        private fun surfacePolicyFlags(word: String): List<EnglishQualityFlag> {
            val assessment = EnglishDictionaryQuality.assess(Dictionary("かたかな", 0, 0, 12500, word))
            return assessment.flags.takeIf { assessment.status != EnglishCandidateStatus.PRIMARY }.orEmpty()
        }

        private fun pairKey(entry: Dictionary) = entry.yomi to entry.tango
        private fun isSingleWord(surface: String) = surface.none(Char::isWhitespace)

        private fun parseCsvLine(line: String, location: String): List<String> {
            val fields = mutableListOf<String>()
            val field = StringBuilder()
            var quoted = false
            var closedQuote = false
            var index = 0
            while (index < line.length) {
                val char = line[index]
                when {
                    quoted && char == '"' && line.getOrNull(index + 1) == '"' -> { field.append('"'); index++ }
                    quoted && char == '"' -> { quoted = false; closedQuote = true }
                    quoted -> field.append(char)
                    char == ',' -> { fields += field.toString(); field.clear(); closedQuote = false }
                    char == '"' -> {
                        require(field.isEmpty() && !closedQuote) { "$location: malformed CSV quoting" }
                        quoted = true
                    }
                    else -> {
                        require(!closedQuote && !char.isISOControl()) { "$location: unexpected text after quote or control character" }
                        field.append(char)
                    }
                }
                index++
            }
            require(!quoted) { "$location: unterminated CSV quote" }
            fields += field.toString()
            return fields
        }
    }
}
