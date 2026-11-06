import dictionary.Dictionary
import grammar.FormKey
import grammar.Lexicon
import grammar.lookupKey
import grammar.readTsv
import kotlinx.serialization.json.*
import java.io.File
import java.net.URI
import java.nio.file.Files

internal data class SupplementEntry(
    val key: FormKey,
    val lemma: String,
    val categories: Set<String>,
    val evidence: String,
)

internal class ReviewedSupplement private constructor(
    val manifest: File,
    val entriesFile: File,
    val entries: List<SupplementEntry>,
    val candidates: List<Dictionary>,
    val notices: List<File>,
) {
    fun appendGrammar(grammar: File, base: Lexicon) {
        val forms = base.forms.associateBy { it.key }
        val additions = entries.associateBy { it.key }.toMutableMap()
        // Supporting lemmas belong to the grammar tables. Only explicit entries
        // in the supplement ledger become conversion candidates.
        for (entry in entries) {
            val lemmaKey = FormKey(entry.key.lexemeId, entry.lemma)
            if (lemmaKey !in forms && lemmaKey !in additions) {
                val roles = entry.categories intersect lexicalRoles
                require(roles.isNotEmpty()) { "Missing grammatical role for supporting lemma $lemmaKey" }
                additions[lemmaKey] = entry.copy(key = lemmaKey, categories = roles)
            }
        }
        grammar.resolve("forms.tsv").appendText(buildString {
            for ((key, entry) in additions) {
                if (key !in forms) appendLine(listOf(key.lexemeId, entry.lemma, key.surface, entry.evidence).joinToString("\t"))
            }
        })
        grammar.resolve("memberships.tsv").appendText(buildString {
            for ((key, entry) in additions) {
                val original = forms[key]?.dictionaries.orEmpty()
                for (category in (entry.categories - original).sorted()) {
                    appendLine("$category\t${key.lexemeId}\t${key.surface}")
                }
            }
        })
    }

    fun properties(): Map<String, String> = mapOf(
        "supplement.entries.sha256" to categoryFileHash(entriesFile),
        "supplement.formRows" to entries.size.toString(),
        "supplement.surfaces" to entries.map { it.key.surface }.distinct().size.toString(),
        "supplement.candidatePairs" to candidates.size.toString(),
    )

    companion object {
        fun load(
            directory: File, baseManifest: File, base: Lexicon,
            original: List<Dictionary>, decisions: File,
        ): ReviewedSupplement {
            val manifestFile = directory.resolve("manifest.json")
            val manifest = Json.parseToJsonElement(manifestFile.readText()).jsonObject
            require(manifest["kind"]?.jsonPrimitive?.content == "reviewed-english-supplement-v1" &&
                manifest["schemaVersion"]?.jsonPrimitive?.intOrNull == 1 &&
                baseManifest.isFile && manifest["baseManifestSha256"]?.jsonPrimitive?.content == categoryFileHash(baseManifest)) {
                "Supplement requires the pinned reviewed base manifest"
            }
            val files = manifest.getValue("files").jsonObject
            require("entries.tsv" in files && files.keys.all {
                it == "entries.tsv" || it.matches(Regex("notices/[A-Za-z0-9_.-]+"))
            }) { "Invalid supplement file list" }
            for ((name, hash) in files) {
                val file = directory.resolve(name)
                require(file.isFile && !Files.isSymbolicLink(file.toPath()) && categoryFileHash(file) == hash.jsonPrimitive.content) {
                    "Supplement checksum differs for $name"
                }
            }
            val entriesFile = directory.resolve("entries.tsv")
            val rejected = decisions.readTsv("id", "reading", "surface", "cost", "decision", "lexeme_ids", "reason", "evidence")
                .filter { it[4] == "exclude" }.map { lookupKey(it[2]) }.toSet()
            val entries = readSupplementEntries(entriesFile, base, original, rejected)
            val maxCostByReading = mutableMapOf<String, Int>()
            for (candidate in original) {
                val cost = candidate.cost.toInt()
                maxCostByReading.merge(candidate.reading, cost, ::maxOf)
            }
            val candidates = entries.map { it.key.surface }.distinct().flatMap { surface ->
                supplementReadings(surface).map { key ->
                    // New homographs remain available without displacing the existing readings.
                    val cost = maxOf(6000, (maxCostByReading[key] ?: 0) + 1)
                    require(cost <= Short.MAX_VALUE) { "No cost available after the original candidates for $key" }
                    Dictionary(key, cost.toShort(), surface, key != surface)
                }
            }
            val notices = files.keys.filter { it.startsWith("notices/") }.sorted().map(directory::resolve)
            return ReviewedSupplement(manifestFile, entriesFile, entries, candidates, notices)
        }
    }
}

private val supportedSurface = Regex("[A-Za-z0-9]+(?:[ '’./-][A-Za-z0-9]+)*")
private val domains = setOf("daily", "business", "technology", "travel")
private val lexicalRoles = setOf("noun", "verb", "adjective", "adverb", "contraction", "abbreviation", "phrase")

internal fun supplementReadings(surface: String): Set<String> {
    require(surface.length in 1..64 && supportedSurface.matches(surface)) { "Invalid supplement surface: $surface" }
    val literal = lookupKey(surface)
    val spaced = literal.filterNot { it in "'-./" }
    return linkedSetOf(literal, spaced, spaced.replace(" ", ""))
}

internal fun readSupplementEntries(
    file: File, base: Lexicon, original: List<Dictionary>, excludedSurfaces: Set<String>,
): List<SupplementEntry> {
    val categoryNames = base.categories.map { it.name }.toSet()
    val lemmas = base.forms.associate { it.key.lexemeId to it.lemma }.toMutableMap()
    val originalSurfaces = original.map { lookupKey(it.word) }.toSet()
    val identities = mutableSetOf<FormKey>()
    val rows = file.readTsv("lexeme_id", "lemma", "surface", "categories", "domain", "evidence", "source_ref")
    require(rows.isNotEmpty()) { "Supplement must contain reviewed entries" }
    return rows.map { row ->
        val (id, lemma, surface, membership, domain) = row
        val evidence = row[5]
        val source = row[6]
        val key = FormKey(id, surface)
        require(id.matches(Regex("[A-Za-z0-9_-]+")) && identities.add(key)) { "Duplicate or invalid supplement identity $key" }
        supplementReadings(surface)
        require(lemma.length <= 64 && supportedSurface.matches(lemma) && lemmas.putIfAbsent(id, lemma).let { it == null || it == lemma }) {
            "Invalid or conflicting supplement lemma for $key"
        }
        require(lookupKey(surface) !in originalSurfaces && lookupKey(surface) !in excludedSurfaces) {
            "Supplement repeats an existing or excluded surface: $surface"
        }
        val categories = membership.split(',')
        require(domain in domains && "domain_$domain" in categories && categories.toSet().size == categories.size &&
            categories.all { it in categoryNames } && (surface == lemma || categories.any { it in lexicalRoles })) {
            "Invalid supplement categories for $key"
        }
        val uri = URI(evidence)
        require(uri.scheme == "https" && !uri.host.isNullOrBlank() && source.length <= 256) {
            "Missing source evidence for supplement entry $key"
        }
        SupplementEntry(key, lemma, categories.toSet(), evidence)
    }
}
