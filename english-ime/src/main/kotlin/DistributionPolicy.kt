import grammar.Lexicon
import grammar.readTsv
import java.io.File
import kotlinx.serialization.json.*

/** Authoring records remain intact; distribution removes complete spellings/lexemes. */
internal class DistributionPolicy(val file: File, base: Lexicon, entries: List<SupplementEntry>) {
    private val declared = file.readTsv("surface", "match", "reason", "evidence", "license").map { row ->
        require(row[1] in setOf("exact","casefold","sha256-exact","sha256-casefold") && row[2] in setOf("adult-industry-person", "adult-industry-product-service", "sexual-slang", "victim-person", "victim-related-subject") &&
            row[3].startsWith("https://") && row[4] in setOf("CC0-1.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0", "BSD-2-Clause")) {
            "Invalid distribution exclusion evidence"
        }
        require(!row[1].startsWith("sha256-") || row[0].matches(Regex("[0-9a-f]{64}"))) { "Invalid hashed exclusion" }
        distributionRuleKey(row[0],row[1])
    }.toSet()
    val keys = distributionKeys(declared,base.forms.asSequence().map { it.key.surface to it.lemma } +
        entries.asSequence().flatMap { sequenceOf(it.key.surface to it.lemma,it.lemma to it.lemma) })

    fun allows(surface: String) = !distributionMatches(surface,keys)

    fun filterTable(file: File) {
        val columns=file.bufferedReader().use { it.readLine().split('\t') }
        val indexes=columns.indices.filter { columns[it] in setOf("surface","lemma","source","target") }
        rewrite(file) { row -> indexes.all {
            !distributionMatches(row[it],if(columns[it]=="lemma") declared else keys)
        } }
    }

    fun filterGrammar(grammar: File) {
        filterTable(grammar.resolve("forms.tsv"))
        val forms=grammar.resolve("forms.tsv").useLines { lines -> lines.drop(1).map {
            val row=it.split('\t'); row[0]+"\t"+row[2]
        }.toSet() }
        val used=mutableSetOf<String>()
        rewrite(grammar.resolve("memberships.tsv")) { row ->
            (row[1]+"\t"+row[2] in forms).also { if(it) used.add(row[0]) }
        }
        rewrite(grammar.resolve("categories.tsv")) { it[0] in used }
    }

    private fun rewrite(file: File, keep: (List<String>) -> Boolean) {
        val temporary=File.createTempFile(".filtered-",".tsv",file.parentFile)
        try {
            file.bufferedReader().use { input -> temporary.bufferedWriter().use { output ->
                output.appendLine(requireNotNull(input.readLine()))
                input.lineSequence().forEach { line -> if(keep(line.split('\t'))) output.appendLine(line) }
            } }
            java.nio.file.Files.move(temporary.toPath(),file.toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING)
        } finally { temporary.delete() }
    }

    fun publicManifest(authoring: File) = buildJsonObject {
        put("schemaVersion", 1)
        put("kind", "english-distribution-provenance")
        put("authoringManifestSha256", categoryFileHash(authoring))
        put("distributionPolicySha256", categoryFileHash(file))
    }.toString() + "\n"
}

internal fun distributionRuleKey(surface: String, match: String): String {
    if(match.startsWith("sha256-")) return "$match:$surface"
    val normalized=surface.replace('’','\'')
    return if(match=="casefold") "fold:"+normalized.lowercase(java.util.Locale.ROOT) else "exact:$normalized"
}

private val distributionModes=listOf("exact","casefold","sha256-exact","sha256-casefold")

internal fun distributionWordKey(surface: String, match: String): String {
    if(!match.startsWith("sha256-")) return distributionRuleKey(surface,match)
    val normalized=surface.replace('’','\'').let { if(match=="sha256-casefold") it.lowercase(java.util.Locale.ROOT) else it }
    val hash=java.security.MessageDigest.getInstance("SHA-256").digest(normalized.toByteArray(Charsets.UTF_8))
        .joinToString("") { (it.toInt() and 255).toString(16).padStart(2,'0') }
    return "$match:$hash"
}

internal fun distributionMatches(surface: String, keys: Set<String>) =
    distributionModes.any { distributionWordKey(surface,it) in keys }

internal fun distributionInheritedKeys(surface: String, lemma: String, declared: Set<String>) =
    distributionModes.filter { distributionWordKey(lemma,it) in declared }.map { distributionWordKey(surface,it) }

internal fun distributionKeys(declared: Set<String>, forms: Sequence<Pair<String,String>>): Set<String> {
    val records=forms.toList()
    val independent=records.asSequence().filter { (surface,lemma) ->
        !distributionMatches(surface,declared) && !distributionMatches(lemma,declared)
    }.map { it.first }.toSet()
    // Remove a restricted lexeme's aliases/inflections only when no independent
    // analysis supports that surface. Never cascade through a shared homonym.
    return declared+records.asSequence().filter { it.first !in independent }
        .flatMap { (surface,lemma) -> distributionInheritedKeys(surface,lemma,declared).asSequence() }.toSet()
}
