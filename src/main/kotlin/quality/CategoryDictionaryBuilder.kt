package com.kazumaproject.quality

import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.mozc.MozcIdDefParser
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.zip.GZIPOutputStream

class CategoryDictionaryBuilder {
    data class Options(
        val source: File = File("src/main/bin"), val base: File = File("src/main/resources"),
        val output: File = File("build/dictionaries/categories"), val reports: File = File("build/reports/dictionary-quality"),
        val reference: File? = null, val cache: File = File("build/dictionary-metadata/cache.sqlite"),
        val cacheLimitMiB: Int = 512, val apiBudget: Int = 0, val offline: Boolean = true,
        val overrides: File? = File("src/main/dictionary-quality/overrides.tsv").takeIf { it.isFile },
        val snapshot: File? = null,
        val confirmed: File? = File("src/main/dictionary-quality/confirmed.tsv").takeIf { it.isFile },
        val inputManifest: File? = null,
        val candidate: Boolean = false,
    )
    private data class Entry(var word: Dictionary, val sources: MutableSet<String>)

    fun build(options: Options) {
        require(options.output.canonicalFile != options.base.canonicalFile) { "Category output must be separate from system resources" }
        val ids = MozcIdDefParser.parse(File(options.base, "id.def").toPath()).map { it.id }.toSet()
        val overrides = ManualOverrides(options.overrides)
        val metadata = options.snapshot?.let { MetadataSnapshot.verify(it, source = options.source, allowCandidate = options.candidate) }
        if (metadata?.get("schemaVersion")?.jsonPrimitive?.int == 4) { ResolvedDictionaryBuilder.build(options, metadata); return }
        val lexical = LexicalEvidence.load(options.snapshot, options.confirmed)
        val independentReadings = ReadingEvidence.load(options.base)
        val readings = independentReadings.toMutableMap().apply {
            lexical.readings.forEach { (surface, values) -> put(surface, get(surface).orEmpty() + values) }
        }
        val catalog = MetadataCatalog(options.reference, options.snapshot ?: options.cache, options.cacheLimitMiB, options.apiBudget, options.offline)
        val identityClassifier = SemanticClassifier(catalog)
        val normalizer = CandidateNormalizer(readings, overrides, lexical) { surface, reading ->
            lexical.has(reading, surface, "facility") || identityClassifier.classify(SourceRow("place", 0, Dictionary(reading, 0, 0, 0, surface))).categories == setOf("facility")
        }
        options.output.parentFile?.mkdirs(); options.reports.parentFile?.mkdirs()
        val work = Files.createTempDirectory(options.output.parentFile?.toPath(), ".category-build-").toFile()
        var sourceCount = 0; var heldCount = 0; var changedCount = 0; var excludedCount = 0; var qualityHeld = 0; var unclassifiedCount = 0; var acceptedCount = 0
        try {
            val packs = File(work, "packs").apply { mkdirs() }
            val reports = File(work, "reports").apply { mkdirs() }
            val counts = linkedMapOf<String, Int>()
            val entries = linkedMapOf<WordKey, Entry>()
            var requests = 0; var unavailable = false; var capacity = false
            GZIPOutputStream(File(reports, "review.tsv.gz").outputStream()).bufferedWriter(Charsets.UTF_8).use { review ->
                GZIPOutputStream(File(reports, "audit.tsv.gz").outputStream()).bufferedWriter(Charsets.UTF_8).use { audit ->
                    val header = "phase\tsources\tline\treading\tsurface\toutput_reading\toutput_surface\tcategories\treason\tleft_id\tright_id\tcost\tquality_status\treading_evidence\tverification_issue\tsemantic_issue"
                    audit.appendLine(header); review.appendLine(header)
                    fun record(phase: String, sources: String, line: Int, original: Dictionary, output: Dictionary?, categories: String, reason: String, quality: String = "", readingEvidence: String = "", verificationIssue: String = "") {
                        val record = listOf(phase, sources, line.toString(), original.yomi, original.tango, output?.yomi.orEmpty(), output?.tango.orEmpty(), categories, reason, original.leftId.toString(), original.rightId.toString(), original.cost.toString(), quality, readingEvidence, verificationIssue, if (categories == "unclassified") "semantic-evidence-missing" else "").joinToString("\t") { it.replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r") }
                        audit.appendLine(record)
                        if (quality in setOf("held", "excluded") || categories == "unclassified") review.appendLine(record)
                    }
                    SupplementalSources.files.keys.forEach { source ->
                        SupplementalSources.read(source, options.source) { row ->
                            sourceCount++
                            require(row.word.leftId.toInt() in ids && row.word.rightId.toInt() in ids) { "$source:${row.line}: context ID outside id.def" }
                            val result = normalizer.normalize(row)
                            if (result.entries.isEmpty()) {
                                if (result.state == "excluded") excludedCount++ else heldCount++
                                record("normalization", source, row.line, row.word, null, "", result.reason, result.state)
                            }
                            else {
                                if (result.reason != "unchanged") {
                                    changedCount++
                                    result.entries.forEach { record("normalization", source, row.line, row.word, it, "", result.reason) }
                                }
                                result.entries.forEach { word ->
                                    val existing = entries[word.key()]
                                    if (existing == null) entries[word.key()] = Entry(word, linkedSetOf(source))
                                    else { existing.sources.add(source); if (word.cost < existing.word.cost) existing.word = word }
                                }
                            }
                        }
                        println("Read $source: total=$sourceCount, accepted=${entries.size}, held=$heldCount")
                    }
                    val baseEvidence = SemanticClassifier.baseEvidence(options.base, entries.values.map { it.word.yomi to it.word.tango }.toSet())
                    val grouped = publishedCategories.associateWith { mutableListOf<Dictionary>() }
                    run {
                        val classifier = SemanticClassifier(catalog, baseEvidence)
                        val qualityEvaluator = QualityEvaluator(catalog, independentReadings, lexical)
                        entries.values.toList().chunked(500).forEachIndexed { index, chunk ->
                            catalog.prepare(chunk.map { it.word.tango })
                            chunk.forEach { entry ->
                                val first = SourceRow(entry.sources.first(), 0, entry.word)
                                val qualityCheck = qualityEvaluator.evaluate(first)
                                val decisions = entry.sources.map { source ->
                                    val row = SourceRow(source, 0, entry.word)
                                    overrides.classification(row) ?: classifier.classify(row, qualityCheck.state == "accepted").let { decision ->
                                        val facts = lexical.facts(row.word.yomi, row.word.tango)
                                        if (facts.flatMap { it.categories }.isEmpty()) decision else {
                                            val confirmed = classifier.confirmedCategories(row, qualityCheck.state == "accepted")
                                            Classification((confirmed.categories - "unclassified") + facts.flatMap { it.categories }, (listOf(confirmed.evidence, "lexical-and-confirmed-referents") + facts.map { it.evidence }).filter { it.isNotBlank() }.distinct().joinToString(";"))
                                        }
                                    }
                                }
                                val categories = decisions.flatMap { it.categories }.toMutableSet()
                                if (categories.size > 1) categories.remove("unclassified")
                                // Semantic overrides never establish a reading.
                                val quality = qualityCheck
                                if (quality.state != "accepted") qualityHeld++
                                if (categories == setOf("unclassified")) unclassifiedCount++
                                if (quality.state == "accepted" && categories != setOf("unclassified")) {
                                    acceptedCount++; categories.forEach { grouped.getValue(it).add(entry.word) }
                                }
                                record("classification", entry.sources.joinToString(","), 0, entry.word, entry.word, categories.sorted().joinToString(","), decisions.map { it.evidence }.distinct().joinToString(";"), quality.state, quality.evidence, quality.issue)
                            }
                            if (index % 40 == 0) println("Classified ${minOf((index + 1) * 500, entries.size)}/${entries.size}; API=${catalog.requests}")
                        }
                        requests = catalog.requests; unavailable = catalog.unavailable; capacity = catalog.capacityReached
                    }
                    val all = grouped.values.flatten().distinctBy { it.key() }.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
                    val posBuild = File(work, "pos_table_for_build.dat")
                    TokenArray().buildPOSTable(all, 1, File(packs, "pos_table.dat").path)
                    TokenArray().buildPOSTableWithIndex(all, 1, posBuild.path)
                    grouped.forEach { (category, words) ->
                        val directory = File(packs, category).apply { mkdirs() }
                        val sorted = words.sortedWith(compareBy({ it.yomi.length }, { it.yomi }, { it.cost }, { it.tango }, { it.leftId }, { it.rightId })).groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
                        buildAndWriteDictionaryArtifacts(sorted, File(directory, "yomi.dat").path, File(directory, "tango.dat").path, File(directory, "token.dat").path, posTableForBuildPath = posBuild.path)
                        counts[category] = words.size
                        println("Built $category: ${words.size}")
                    }
                }
            }
            val sources = buildJsonObject {
                SupplementalSources.files.forEach { (source, name) -> put(source, sha256(File(options.source, name))) }
                (0..9).forEach { put("dictionary%02d.txt".format(it), sha256(File(options.base, "dictionary%02d.txt".format(it)))) }
                listOf("suffix.txt", "id.def").forEach { put(it, sha256(File(options.base, it))) }
            }
            val summary = buildJsonObject {
                put("sourceRows", sourceCount); put("normalizedEntries", entries.size); put("acceptedEntries", acceptedCount); put("qualityHeldEntries", qualityHeld); put("unclassifiedEntries", unclassifiedCount); put("excludedRows", excludedCount); put("heldRows", heldCount); put("changedRows", changedCount)
                put("categories", buildJsonObject { counts.forEach { (name, count) -> put(name, count) } })
                put("apiRequests", requests); put("metadataUnavailable", unavailable); put("cacheCapacityReached", capacity)
                put("cacheBytes", if (options.snapshot == null) options.cache.length() else 0); put("dictionaryBytes", packs.walkTopDown().filter { it.isFile }.sumOf { it.length() })
            }
            val manifest = buildJsonObject {
                put("format", "legacy-louds-triplets-v1"); put("taxonomyVersion", 3); put("normalizationVersion", 2); put("qualityVersion", 2)
                put("implementationSha256", implementationHash())
                put("implementation", buildJsonObject {
                    listOf(CandidateNormalizer::class.java, SemanticClassifier::class.java, ManualOverrides::class.java, SupplementalSources::class.java, ReadingEvidence::class.java, MetadataEntity::class.java, MetadataCatalog::class.java, LexicalEvidence::class.java, QualityEvaluator::class.java, PostalLexicon::class.java, MetadataSnapshot::class.java, TokenArray::class.java, Class.forName("com.kazumaproject.DictionaryBuilderKt"), CategoryDictionaryBuilder::class.java).forEach { type ->
                        val resource = type.name.replace('.', '/') + ".class"
                        val digest = MessageDigest.getInstance("SHA-256")
                        type.classLoader.getResourceAsStream(resource)!!.use { input ->
                            val buffer = ByteArray(65536)
                            while (true) { val size = input.read(buffer); if (size < 0) break; digest.update(buffer, 0, size) }
                        }
                        put(type.simpleName, digest.digest().joinToString("") { "%02x".format(it) })
                    }
                })
                put("sources", sources); put("overridesSha256", options.overrides?.let(::sha256)?.let(::JsonPrimitive) ?: JsonNull)
                put("snapshotSha256", options.snapshot?.let(::sha256)?.let(::JsonPrimitive) ?: JsonNull)
                put("confirmedSha256", options.confirmed?.let(::sha256)?.let(::JsonPrimitive) ?: JsonNull)
                put("inputManifest", options.inputManifest?.let { Json.parseToJsonElement(it.readText()) } ?: JsonNull)
                put("referenceSha256", options.reference?.let(::sha256)?.let(::JsonPrimitive) ?: JsonNull)
                put("cacheSha256", options.cache.takeIf { options.snapshot == null && it.isFile }?.let(::sha256)?.let(::JsonPrimitive) ?: JsonNull)
                put("categories", summary.getValue("categories"))
                put("artifacts", buildJsonObject { packs.walkTopDown().filter { it.isFile }.sortedBy { it.path }.forEach { put(it.relativeTo(packs).invariantSeparatorsPath, sha256(it)) } })
            }
            val json = Json { prettyPrint = true }
            File(packs, "manifest.json").writeText(json.encodeToString(JsonObject.serializer(), manifest) + "\n")
            File(reports, "manifest.json").writeText(json.encodeToString(JsonObject.serializer(), manifest) + "\n")
            File(reports, "summary.json").writeText(json.encodeToString(JsonObject.serializer(), summary) + "\n")
            publish(packs, options.output)
            publish(reports, options.reports)
            // Remove only obsolete artifacts owned by the former 13th pack.
            listOf("yomi.dat", "tango.dat", "token.dat").forEach { File(options.output, "unclassified/$it").delete() }
            File(options.output, "unclassified").delete()
            println(json.encodeToString(JsonObject.serializer(), summary))
        } finally { catalog.close(); check(work.deleteRecursively()) { "Could not remove temporary build directory: $work" } }
    }

    private fun publish(source: File, target: File) {
        require(!target.isFile) { "Output is a file: $target" }
        target.mkdirs()
        // Only replace owned artifacts, not unrelated user files.
        source.walkTopDown().filter { it.isFile }.forEach { file ->
            val output = File(target, file.relativeTo(source).path)
            output.parentFile.mkdirs()
            Files.move(file.toPath(), output.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
    }

    // Include generated lambda/nested classes as well as the enclosing classes.
    private fun implementationHash(): String {
        val location = File(CategoryDictionaryBuilder::class.java.protectionDomain.codeSource.location.toURI())
        val digest = MessageDigest.getInstance("SHA-256")
        fun include(name: String, input: java.io.InputStream) {
            digest.update(name.toByteArray(Charsets.UTF_8)); digest.update(0.toByte())
            input.use { stream ->
                val bytes = ByteArray(65536)
                while (true) { val size = stream.read(bytes); if (size < 0) break; digest.update(bytes, 0, size) }
            }
        }
        if (location.isFile) java.util.jar.JarFile(location).use { jar ->
            jar.entries().asSequence().filter { it.name.startsWith("com/kazumaproject/") && it.name.endsWith(".class") }.sortedBy { it.name }.forEach { include(it.name, jar.getInputStream(it)) }
        } else location.walkTopDown().filter { it.isFile && it.extension == "class" }.sortedBy { it.relativeTo(location).invariantSeparatorsPath }.forEach { include(it.relativeTo(location).invariantSeparatorsPath, it.inputStream()) }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

fun sha256(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().buffered().use { input ->
        val buffer = ByteArray(65536)
        while (true) { val size = input.read(buffer); if (size < 0) break; digest.update(buffer, 0, size) }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
