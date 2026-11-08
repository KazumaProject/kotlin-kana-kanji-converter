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
    val metadata: List<SupplementEntry>,
    val categoryDefinitions: List<List<String>>,
    val candidates: List<Dictionary>,
    val notices: List<File>,
) {
    fun appendGrammar(grammar: File, base: Lexicon) {
        val forms = base.forms.associateBy { it.key }
        val additions = mutableMapOf<FormKey, SupplementEntry>()
        for (entry in entries + metadata) {
            val previous = additions[entry.key]
            require(previous == null || previous.lemma == entry.lemma) { "Conflicting supplemental lemma" }
            additions[entry.key] = entry.copy(categories = entry.categories + previous?.categories.orEmpty())
        }
        if (categoryDefinitions.isNotEmpty()) grammar.resolve("categories.tsv").appendText(
            categoryDefinitions.joinToString("\n", postfix = "\n") { it.joinToString("\t") })
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
    ) + if (metadata.isEmpty() && categoryDefinitions.isEmpty()) emptyMap() else mapOf(
        "supplement.metadataRows" to metadata.size.toString(),
        "supplement.additionalCategories" to categoryDefinitions.size.toString(),
    )

    companion object {
        fun load(
            directory: File, baseManifest: File, base: Lexicon,
            original: List<Dictionary>, decisions: File,
        ): ReviewedSupplement {
            val manifestFile = directory.resolve("manifest.json")
            val manifest = Json.parseToJsonElement(manifestFile.readText()).jsonObject
            val version = manifest["schemaVersion"]?.jsonPrimitive?.intOrNull
            require(version in setOf(1, 2) &&
                manifest["kind"]?.jsonPrimitive?.content == "reviewed-english-supplement-v$version" &&
                baseManifest.isFile && manifest["baseManifestSha256"]?.jsonPrimitive?.content == categoryFileHash(baseManifest)) {
                "Supplement requires the pinned reviewed base manifest"
            }
            val files = manifest.getValue("files").jsonObject
            require("entries.tsv" in files && files.keys.all {
                it == "entries.tsv" || version == 2 && it in setOf("categories.tsv", "metadata.tsv") ||
                    it.matches(Regex("notices/[A-Za-z0-9_.-]+"))
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
            val definitions = if ("categories.tsv" in files) directory.resolve("categories.tsv")
                .readTsv("category", "definition", "examples") else emptyList()
            val newNames = definitions.map { it[0] }
            require(newNames.distinct().size == newNames.size && newNames.all {
                it.matches(Regex("topic_[a-z0-9_]+")) && it !in base.categories.map { category -> category.name }
            }) { "Invalid or repeated additional categories" }
            val entries = readSupplementEntries(entriesFile, base, original, rejected, newNames.toSet())
            val metadata = if ("metadata.tsv" in files) readSupplementMetadata(
                directory.resolve("metadata.tsv"), base, original, entries, newNames.toSet()) else emptyList()
            require(newNames.all { name -> (entries + metadata).any { name in it.categories } }) {
                "Additional category has no attested members"
            }
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
            return ReviewedSupplement(manifestFile, entriesFile, entries, metadata, definitions, candidates, notices)
        }
    }
}

private val supportedSurface = Regex("[A-Za-z0-9]+(?:[ '’./-][A-Za-z0-9]+)*")
private val domains = setOf("daily", "business", "technology", "travel")
private val lexicalRoles = setOf("noun", "verb", "adjective", "adverb", "pronoun", "determiner",
    "preposition", "conjunction", "interjection", "contraction", "abbreviation", "phrase")

internal fun supplementReadings(surface: String): Set<String> {
    require(surface.length in 1..64 && supportedSurface.matches(surface)) { "Invalid supplement surface: $surface" }
    val literal = lookupKey(surface)
    val spaced = literal.filterNot { it in "'-./" }
    return linkedSetOf(literal, spaced, spaced.replace(" ", ""))
}

internal fun readSupplementEntries(
    file: File, base: Lexicon, original: List<Dictionary>, excludedSurfaces: Set<String>,
    additionalCategories: Set<String> = emptySet(),
): List<SupplementEntry> {
    return readSupplementRows(file, base, original, excludedSurfaces, additionalCategories, emptyList(), false)
}

internal fun readSupplementMetadata(
    file: File, base: Lexicon, original: List<Dictionary>, entries: List<SupplementEntry>,
    additionalCategories: Set<String>,
): List<SupplementEntry> = readSupplementRows(file, base, original, emptySet(), additionalCategories, entries, true)

private fun readSupplementRows(
    file: File, base: Lexicon, original: List<Dictionary>, excludedSurfaces: Set<String>,
    additionalCategories: Set<String>, entries: List<SupplementEntry>, metadata: Boolean,
): List<SupplementEntry> {
    val categoryNames = base.categories.map { it.name }.toSet() + additionalCategories
    val lemmas = base.forms.associate { it.key.lexemeId to it.lemma }.toMutableMap()
    entries.forEach { lemmas[it.key.lexemeId] = it.lemma }
    val knownForms = base.forms.map { it.key }.toSet() + entries.map { it.key }
    val originalSurfaces = original.map { it.word }.toSet()
    val availableSurfaces = originalSurfaces + entries.map { it.key.surface }
    val identities = mutableSetOf<FormKey>()
    val rows = file.readTsv("lexeme_id", "lemma", "surface", "categories", "domain", "evidence", "source_ref")
    require(rows.isNotEmpty() || metadata) { "Supplement must contain reviewed entries" }
    return rows.map { row ->
        val (id, lemma, surface, membership, domain) = row
        val evidence = row[5]
        val source = row[6]
        val key = FormKey(id, surface)
        require((metadata || id.matches(Regex("[A-Za-z0-9_-]+"))) && identities.add(key)) { "Duplicate or invalid supplement identity $key" }
        if (!metadata) supplementReadings(surface)
        require((metadata || lemma.length <= 64 && supportedSurface.matches(lemma)) &&
            lemmas.putIfAbsent(id, lemma).let { it == null || it == lemma }) {
            "Invalid or conflicting supplement lemma for $key"
        }
        require(if (metadata) key in knownForms && surface in availableSurfaces else
            surface !in originalSurfaces && lookupKey(surface) !in excludedSurfaces) {
            "Supplement repeats an existing or excluded surface: $surface"
        }
        val categories = membership.split(',')
        require(!metadata || categories.all { it.startsWith("topic_") || it.startsWith("domain_") }) {
            "Metadata annotations may add only source-attested topic/domain memberships"
        }
        require(domain in domains && "domain_$domain" in categories && categories.toSet().size == categories.size &&
            categories.all { it in categoryNames } && (metadata || surface == lemma || categories.any { it in lexicalRoles })) {
            "Invalid supplement categories for $key"
        }
        val uri = URI(evidence)
        require(uri.scheme == "https" && !uri.host.isNullOrBlank() && source.length <= 256) {
            "Missing source evidence for supplement entry $key"
        }
        SupplementEntry(key, lemma, categories.toSet(), evidence)
    }
}
