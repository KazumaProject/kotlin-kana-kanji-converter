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
    private val cmuPathPattern = Regex("/cmusphinx/cmudict/blob/[0-9a-f]{40}/cmudict\\.dict")
    private val cmuRawPathPattern = Regex("/cmusphinx/cmudict/[0-9a-f]{40}/cmudict\\.dict")
    private val cmuPronunciationPattern = Regex("(?:^|; )ARPAbet=([^;]+)(?:;|$)")
    private val cmuVowels = setOf("AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW")
    private val cmuConsonants = setOf("B", "CH", "D", "DH", "F", "G", "HH", "JH", "K", "L", "M", "N", "NG", "P", "R", "S", "SH", "T", "TH", "V", "W", "Y", "Z", "ZH")

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
                if (isCmuSource(source)) {
                    val uri = URI(source)
                    val pinnedPath = when (uri.host.lowercase(Locale.ROOT)) {
                        "github.com" -> cmuPathPattern.matches(uri.path)
                        "raw.githubusercontent.com" -> cmuRawPathPattern.matches(uri.path)
                        else -> false
                    }
                    check(pinnedPath && uri.query == null &&
                            (uri.fragment == null || uri.fragment.matches(Regex("L[1-9][0-9]*"))),
                        "CMUdict source must identify a fixed commit and an optional source line")
                    check(note.startsWith("英語発音から作成・確認した読み; "),
                        "CMUdict-derived reading must record its explicit pronunciation review")
                    val phones = cmuPronunciationPattern.find(note)?.groupValues?.get(1)?.split(' ')
                    check(!phones.isNullOrEmpty() && phones.all(::isCmuPhone),
                        "CMUdict-derived reading must record valid stressed ARPAbet phonemes")
                }
                check(pairs.add(reading to surface), "duplicate reading/surface pair")
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

    private fun isCmuPhone(phone: String): Boolean = phone in cmuConsonants ||
        (phone.length == 3 && phone.take(2) in cmuVowels && phone.last() in '0'..'2')

    private fun isCmuSource(source: String): Boolean {
        val uri = URI(source)
        val path = uri.path?.lowercase(Locale.ROOT) ?: return false
        return uri.host?.lowercase(Locale.ROOT) in setOf("github.com", "raw.githubusercontent.com") &&
            (path == "/cmusphinx/cmudict" || path.startsWith("/cmusphinx/cmudict/"))
    }
}
