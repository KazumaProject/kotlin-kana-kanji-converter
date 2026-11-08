import grammar.readTsv
import grammar.Lexicon
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest

/** Carry source notices and a reviewed, hashed category contract to the consumer. */
internal fun writeReviewedCategoryBundle(
    lexicon: File,
    relations: File,
    decisions: File,
    notices: File,
    output: File,
    base: Lexicon? = null,
    supplement: ReviewedSupplement? = null,
) {
    require(notices.isDirectory) { "Reviewed builds require a source notice directory" }
    val noticeFiles = (notices.listFiles().orEmpty().toList() + supplement?.notices.orEmpty()).sortedBy { it.name }
    require(noticeFiles.distinctBy { it.name }.size == noticeFiles.size) { "Supplement notice conflicts with a base notice" }
    require(noticeFiles.isNotEmpty() && noticeFiles.all {
        it.isFile && !Files.isSymbolicLink(it.toPath()) && it.name.matches(Regex("[A-Za-z0-9_.-]+"))
    }) { "Missing or invalid source notices" }
    val sourceManifest = lexicon.absoluteFile.parentFile.resolve("manifest.json")
    if (sourceManifest.isFile) {
        val recorded = Json.parseToJsonElement(sourceManifest.readText()).jsonObject.getValue("files").jsonObject
            .filterKeys { it.startsWith("notices/") }
        require(recorded.isNotEmpty() && recorded.all { (name, hash) ->
            val filename = name.removePrefix("notices/")
            filename in noticeFiles.map { it.name } &&
                categoryFileHash(notices.resolve(filename)) == hash.jsonPrimitive.content
        }) { "Source notices do not match materialization provenance" }
    }
    val ledger = decisions.readTsv("id", "reading", "surface", "cost", "decision", "lexeme_ids", "reason", "evidence")
    require(ledger.isNotEmpty() && ledger.none { it[4] !in setOf("include", "exclude") }) { "Incomplete review" }
    val grammar = output.resolve("grammar").apply { mkdir() }
    val names = listOf("categories.tsv", "forms.tsv", "memberships.tsv")
    names.forEach { lexicon.resolve(it).copyTo(grammar.resolve(it)) }
    supplement?.appendGrammar(grammar, requireNotNull(base))
    supplement?.distributionPolicy?.filterGrammar(grammar)
    writeCompactCategories(Lexicon.load(grammar), grammar.resolve("categories.ecat"))
    relations.copyTo(grammar.resolve("relations.tsv"))
    supplement?.distributionPolicy?.filterTable(grammar.resolve("relations.tsv"))
    val destinationNotices = grammar.resolve("notices").apply { mkdir() }
    noticeFiles.forEach { it.copyTo(destinationNotices.resolve(it.name)) }
    val properties = sortedMapOf(
        "schemaVersion" to "1", "reviewComplete" to "true", "inputRows" to ledger.size.toString(),
        "includedRows" to ledger.count { it[4] == "include" }.toString(),
        "excludedRows" to ledger.count { it[4] == "exclude" }.toString(), "pendingRows" to "0",
        "noticeCount" to noticeFiles.size.toString(), "reviewedLedger.sha256" to categoryFileHash(decisions),
    )
    names.forEach { properties["$it.sha256"] = categoryFileHash(grammar.resolve(it)) }
    properties["categories.ecat.sha256"] = categoryFileHash(grammar.resolve("categories.ecat"))
    noticeFiles.forEach { properties["notice.${it.name}.sha256"] = categoryFileHash(destinationNotices.resolve(it.name)) }
    supplement?.let {
        properties.putAll(it.properties())
        if (it.distributionPolicy != null) {
            properties["distribution.policy.sha256"] = categoryFileHash(it.distributionPolicy.file)
            output.resolve("supplement-manifest.json").writeText(it.distributionPolicy.publicManifest(it.manifest))
        } else it.manifest.copyTo(output.resolve("supplement-manifest.json"))
    }
    grammar.resolve("bundle.properties").writeText(properties.entries.joinToString("\n", postfix="\n") { "${it.key}=${it.value}" })
    sourceManifest.takeIf { it.isFile }?.copyTo(output.resolve("source-evidence-manifest.json"))
}

internal fun categoryFileHash(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().buffered().use { input ->
        val buffer = ByteArray(8192)
        while (true) {
            val length = input.read(buffer)
            if (length < 0) break
            digest.update(buffer, 0, length)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
