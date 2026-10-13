package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.net.URI
import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.Files
import java.nio.file.Path
import java.io.InputStream
import java.util.Locale

data class EnglishSupplementEntry(
    val dictionary: Dictionary,
    val source: String,
    val note: String,
)

/** Explicitly checked full-reading pairs, rather than automatically accepted glosses. */
object EnglishReadingSupplement {
    const val RESOURCE = "/reading-supplement.tsv"
    private const val HEADER = "reading\tsurface\tcost\tsource\tnote"
    private val readingPattern = Regex("[ぁ-ゔー]+")
    private val surfacePattern = Regex("[A-Za-z.][A-Za-z0-9 .+#'/-]*")
    private val jmdictSourcePattern = Regex("jmdict:[0-9]+(?:;jmdict:[0-9]+)*")

    fun parse(path: Path, contextId: Int): List<EnglishSupplementEntry> =
        Files.newInputStream(path).use { parse(it, path.toString(), contextId) }

    fun parseResource(contextId: Int): List<EnglishSupplementEntry> {
        val stream = javaClass.getResourceAsStream(RESOURCE)
            ?: error("English reading supplement was not found: $RESOURCE")
        return stream.use { parse(it, RESOURCE, contextId) }
    }

    fun parse(input: InputStream, sourceName: String, contextId: Int): List<EnglishSupplementEntry> {
        require(contextId in 0..Short.MAX_VALUE) { "Invalid generic-noun context ID: $contextId" }
        val result = mutableListOf<EnglishSupplementEntry>()
        val pairs = mutableSetOf<Pair<String, String>>()
        var headerSeen = false
        input.bufferedReader(UTF_8).useLines { lines ->
            lines.forEachIndexed { index, line ->
                if (line.isBlank() || line.startsWith("#")) return@forEachIndexed
                fun check(condition: Boolean, reason: String) = require(condition) {
                    "Invalid English reading supplement: source=$sourceName, line=${index + 1}, reason=$reason"
                }
                if (!headerSeen) {
                    check(line == HEADER, "expected header '$HEADER'")
                    headerSeen = true
                    return@forEachIndexed
                }
                val fields = line.split('\t')
                check(fields.size == 5, "expected exactly five tab-separated columns")
                val (reading, surface, costText, source, note) = fields
                check(fields.all { it.isNotBlank() && it == it.trim() && it.none(Char::isISOControl) },
                    "fields must be nonblank, trimmed, and free of control characters")
                check(readingPattern.matches(reading) && reading == EnglishDictionaryQuality.normalizeReading(reading),
                    "reading must contain normalized hiragana and long-vowel marks only")
                check(surfacePattern.matches(surface) && surface.any { it in 'A'..'Z' || it in 'a'..'z' } &&
                        !surface.contains("  "), "invalid English word, abbreviation, or compound surface")
                check(reading.toByteArray(UTF_8).size <= 256 && surface.toByteArray(UTF_8).size <= 256,
                    "reading/surface exceeds the Mozc field size limit")
                val cost = costText.toIntOrNull()
                check(cost != null && cost in 1..Short.MAX_VALUE, "cost must be in the positive Short range")
                check(isValidSource(source), "source must be jmdict:<entry ID> or an HTTPS source URL")
                check(pairs.add(reading to surface.lowercase(Locale.ROOT)), "duplicate reading/surface pair")
                val dictionary = Dictionary(reading, contextId.toShort(), contextId.toShort(), cost!!.toShort(), surface)
                // Approval only relaxes the compound rule. All lexical/explanation exclusions remain in force.
                val assessment = EnglishDictionaryQuality.assess(dictionary, setOf(reading to surface))
                check(assessment.status == EnglishCandidateStatus.PRIMARY,
                    "candidate fails the quality gate: ${assessment.status}, flags=${assessment.flags}")
                result += EnglishSupplementEntry(dictionary, source, note)
            }
        }
        require(headerSeen) { "English reading supplement is missing its header: $sourceName" }
        return result
    }

    private fun isValidSource(source: String): Boolean {
        if (jmdictSourcePattern.matches(source)) return true
        return runCatching { URI(source) }.getOrNull()?.let {
            it.scheme == "https" && !it.host.isNullOrBlank() && it.userInfo == null
        } == true
    }
}
