package com.kazumaproject.english

import java.io.InputStream
import java.net.URI
import java.nio.file.Files
import java.nio.file.Path

data class EnglishCandidateDecision(
    val reading: String,
    val surface: String,
    val keep: Boolean,
    val outputSurface: String?,
    val source: String,
    val reason: String,
)

/** Editorial selection is explicit; new upstream words never become approved by spelling alone. */
class EnglishCandidateReview private constructor(val decisions: Map<Pair<String, String>, EnglishCandidateDecision>) {
    fun assess(entry: EnglishCandidateAssessment, allowedCompounds: Set<Pair<String, String>>): EnglishCandidateAssessment {
        // A keep decision cannot override a lexical/format exclusion or approve a partial compound.
        if (entry.status != EnglishCandidateStatus.PRIMARY) return entry
        val decision = decisions[entry.normalizedReading to entry.normalizedSurface]
            ?: return entry.copy(status = EnglishCandidateStatus.REVIEW, score = 40,
                flags = entry.flags + EnglishQualityFlag.UNREVIEWED_CANDIDATE)
        if (!decision.keep) return entry.copy(status = EnglishCandidateStatus.EXCLUDED, score = 0,
            flags = entry.flags + EnglishQualityFlag.REVIEW_EXCLUDED)
        val output = decision.outputSurface!!
        val canonical = EnglishDictionaryQuality.assess(entry.source.copy(tango = output), allowedCompounds)
        return canonical.copy(source = entry.source,
            flags = (entry.flags + canonical.flags +
                if (output != entry.normalizedSurface) listOf(EnglishQualityFlag.NORMALIZED_SURFACE) else emptyList()).distinct())
    }

    companion object {
        const val RESOURCE = "/candidate-review.tsv"
        private const val HEADER = "reading\tsurface\tdecision\toutput_surface\tsource\treason"

        fun parse(path: Path): EnglishCandidateReview = Files.newInputStream(path).use { parse(it, path.toString()) }

        fun parseResource(): EnglishCandidateReview =
            (EnglishCandidateReview::class.java.getResourceAsStream(RESOURCE)
                ?: error("English candidate review was not found: $RESOURCE")).use { parse(it, RESOURCE) }

        fun parse(input: InputStream, sourceName: String): EnglishCandidateReview {
            val decisions = linkedMapOf<Pair<String, String>, EnglishCandidateDecision>()
            var headerSeen = false
            input.bufferedReader(Charsets.UTF_8).useLines { lines ->
                lines.forEachIndexed { index, line ->
                    if (line.isBlank() || line.startsWith('#')) return@forEachIndexed
                    fun check(condition: Boolean, reason: String) = require(condition) {
                        "Invalid English candidate review: source=$sourceName, line=${index + 1}, reason=$reason"
                    }
                    if (!headerSeen) {
                        check(line == HEADER, "expected header '$HEADER'")
                        headerSeen = true
                        return@forEachIndexed
                    }
                    val fields = line.split('\t')
                    check(fields.size == 6, "expected exactly six tab-separated columns")
                    val (reading, surface, decision, output, source) = fields
                    val reason = fields[5]
                    check(fields.all { it.isNotBlank() && it == it.trim() && it.none(Char::isISOControl) },
                        "fields must be nonblank, trimmed, and free of control characters")
                    check(Regex("[ぁ-ゔー]+").matches(reading) && reading == EnglishDictionaryQuality.normalizeReading(reading),
                        "reading must be normalized hiragana")
                    check(decision in setOf("keep", "exclude"), "decision must be keep or exclude")
                    // This table selects vocabulary and case; it cannot introduce another spelling or translation.
                    check(if (decision == "keep") output.lowercase(java.util.Locale.ROOT) == surface.lowercase(java.util.Locale.ROOT)
                        else output == "-", "keep may only change case; exclude must use '-' as output")
                    check(source.matches(Regex("jmdict:[0-9]+(?:;jmdict:[0-9]+)*")) || runCatching {
                        val uri = URI(source)
                        uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null
                    }.getOrDefault(false), "source must identify a JMdict entry or HTTPS evidence")
                    val key = reading to surface
                    check(key !in decisions, "duplicate reading/surface pair")
                    decisions[key] = EnglishCandidateDecision(reading, surface, decision == "keep",
                        output.takeIf { decision == "keep" }, source, reason)
                }
            }
            require(headerSeen) { "English candidate review is missing its header: $sourceName" }
            return EnglishCandidateReview(decisions)
        }
    }
}
