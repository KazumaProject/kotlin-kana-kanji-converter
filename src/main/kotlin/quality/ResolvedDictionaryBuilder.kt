package com.kazumaproject.quality

import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.mozc.MozcIdDefParser
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.sql.DriverManager
import java.util.zip.GZIPOutputStream

/** Schema 4 consumes reviewed resolutions. No semantic/reading fallback or network access. */
object ResolvedDictionaryBuilder {
    fun build(options: CategoryDictionaryBuilder.Options, metadata: JsonObject) {
        val active = metadata.getValue("activeCategories").jsonArray.map { it.jsonPrimitive.content }
        val ids = MozcIdDefParser.parse(File(options.base, "id.def").toPath()).map { it.id }.toSet()
        require(sha256(File(options.base, "id.def")) == metadata.getValue("baseIdDefSha256").jsonPrimitive.content) { "Snapshot context IDs differ from Mozc" }
        val words = active.associateWith { linkedMapOf<WordKey, Dictionary>() }
        options.output.absoluteFile.parentFile.mkdirs()
        val work = Files.createTempDirectory(options.output.absoluteFile.parentFile.toPath(), ".resolved-build-").toFile()
        val packs = File(work, "packs").apply { mkdirs() }; val reports = File(work, "reports").apply { mkdirs() }
        try {
            DriverManager.getConnection("jdbc:sqlite:${options.snapshot!!.toURI()}?mode=ro").use { db ->
                var sourceRows = 0
                db.prepareStatement("SELECT r.* FROM source_map m JOIN resolutions r ON r.id=m.candidate_id WHERE m.source=? AND m.line=? ORDER BY r.id").use { q ->
                    SupplementalSources.files.keys.forEach { source ->
                        SupplementalSources.read(source, options.source) { original ->
                            sourceRows++; q.setString(1, source); q.setInt(2, original.line)
                            q.executeQuery().use { rows ->
                                var found = false
                                while (rows.next()) {
                                    found = true
                                    require(rows.getInt("left_id") == original.word.leftId.toInt() && rows.getInt("right_id") == original.word.rightId.toInt()) { "Reviewed context IDs changed at $source:${original.line}" }
                                    if (rows.getString("status") == "adopted") {
                                        val changed=rows.getString("reading")!=original.word.yomi || rows.getString("surface")!=original.word.tango
                                        require(!changed || Json.parseToJsonElement(rows.getString("normalization_ids")).jsonArray.isNotEmpty()) { "Changed candidate has no independent transformation proof at $source:${original.line}" }
                                        val word = Dictionary(rows.getString("reading"), rows.getShort("left_id"), rows.getShort("right_id"), rows.getShort("cost"), rows.getString("surface"))
                                        require(word.leftId.toInt() in ids && word.rightId.toInt() in ids) { "Unknown context ID" }
                                        rows.getString("categories").split(',').forEach { category -> words.getValue(category)[word.key()] = word }
                                    }
                                }
                                require(found) { "Original row not reviewed: $source:${original.line}" }
                            }
                        }
                    }
                }
                require(sourceRows == metadata.getValue("research").jsonObject.getValue("sourceRows").jsonPrimitive.int) { "Original row count differs" }
                GZIPOutputStream(File(reports, "audit.tsv.gz").outputStream()).bufferedWriter().use { audit ->
                    audit.appendLine("phase\tsources\tline\treading\tsurface\toutput_reading\toutput_surface\tcategories\treason\tleft_id\tright_id\tcost\tquality_status\treading_evidence\tverification_issue\tsemantic_issue")
                    db.createStatement().use { s ->
                        s.executeQuery("WITH sources AS (SELECT candidate_id,group_concat(DISTINCT source) AS sources FROM source_map GROUP BY candidate_id) SELECT r.*,s.sources FROM resolutions r JOIN sources s ON s.candidate_id=r.id ORDER BY r.id").use { rows ->
                            while (rows.next()) {
                                val status = rows.getString("status")
                                val cols = listOf("classification", rows.getString("sources"), "0", rows.getString("reading"), rows.getString("surface"), rows.getString("reading"), rows.getString("surface"), rows.getString("categories"), rows.getString("reason"), rows.getString("left_id"), rows.getString("right_id"), rows.getString("cost"), status, rows.getString("reading_ids"), if (status == "not_distributed") rows.getString("reason") else "", "")
                                audit.appendLine(cols.joinToString("\t") { it.replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n") })
                            }
                        }
                    }
                }
                val all = words.values.flatMap { it.values }.distinctBy { it.key() }.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
                val buildPos = File(work, "pos-build.dat")
                TokenArray().buildPOSTable(all, 1, File(packs, "pos_table.dat").path)
                TokenArray().buildPOSTableWithIndex(all, 1, buildPos.path)
                words.forEach { (category, entries) ->
                    val directory = File(packs, category).apply { mkdirs() }
                    val grouped = entries.values.sortedWith(compareBy({ it.yomi.length }, { it.yomi }, { it.cost }, { it.tango }, { it.leftId }, { it.rightId })).groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
                    buildAndWriteDictionaryArtifacts(grouped, File(directory, "yomi.dat").path, File(directory, "tango.dat").path, File(directory, "token.dat").path, posTableForBuildPath = buildPos.path)
                }
            }
            val counts = buildJsonObject { words.forEach { (c, w) -> put(c, w.size) } }
            val manifest = buildJsonObject {
                put("format", "legacy-louds-triplets-v1"); put("taxonomyVersion", 4); put("qualityVersion", 4); put("normalizationVersion", 4)
                put("categories", counts); put("taxonomy", CategoryRegistry.definition)
                put("sources", metadata.getValue("sources")); put("snapshotSha256", sha256(options.snapshot!!))
                put("resolutionSha256", metadata.getValue("research").jsonObject.getValue("resolutionSha256"))
                put("research", metadata.getValue("research")); put("models", metadata.getValue("models"))
                put("inputManifest", options.inputManifest?.let { Json.parseToJsonElement(it.readText()) } ?: JsonNull)
                put("artifacts", buildJsonObject { packs.walkTopDown().filter { it.isFile }.sortedBy { it.path }.forEach { put(it.relativeTo(packs).invariantSeparatorsPath, sha256(it)) } })
            }
            val json = Json { prettyPrint = true }
            File(packs, "manifest.json").writeText(json.encodeToString(JsonObject.serializer(), manifest) + "\n")
            File(reports, "manifest.json").writeText(json.encodeToString(JsonObject.serializer(), manifest) + "\n")
            File(reports, "summary.json").writeText(json.encodeToString(JsonObject.serializer(), buildJsonObject { put("research", metadata.getValue("research")); put("categories", counts) }) + "\n")
            for ((from, into) in listOf(packs to options.output, reports to options.reports)) {
                into.mkdirs()
                from.walkTopDown().filter { it.isFile }.forEach { file ->
                    val target = File(into, file.relativeTo(from).path); target.parentFile.mkdirs()
                    Files.move(file.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
                }
            }
            println("Built reviewed schema-4 dictionaries: $counts")
        } finally { check(work.deleteRecursively()) { "Cannot remove resolved build temporary files" } }
    }
}
