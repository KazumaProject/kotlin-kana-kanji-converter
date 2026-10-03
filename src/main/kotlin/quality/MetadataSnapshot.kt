package com.kazumaproject.quality

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.io.File
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.sql.Connection
import java.sql.DriverManager
import java.time.Duration
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream

/** Immutable, reduced facts. Semantic decisions are deliberately not persisted here. */
object MetadataSnapshot {
    private val json = Json { prettyPrint = true }
    const val MAX_BYTES = 512L * 1024 * 1024
    fun sourceHashes(source: File): JsonObject = buildJsonObject { SupplementalSources.files.forEach { (id, name) -> put(id, sha256(File(source, name))) } }
    fun verify(file: File, lock: File? = null, source: File? = null): JsonObject {
        require(file.isFile && file.length() in 1..MAX_BYTES) { "Missing or oversized metadata snapshot: $file" }
        if (lock != null) require(sha256(file) == Json.parseToJsonElement(lock.readText()).jsonObject.getValue("databaseSha256").jsonPrimitive.content) { "Snapshot database checksum mismatch" }
        return DriverManager.getConnection("jdbc:sqlite:${file.toURI()}?mode=ro").use { connection ->
            connection.createStatement().use { statement ->
                statement.executeQuery("PRAGMA quick_check").use { check(it.next() && it.getString(1) == "ok") { "Corrupt snapshot database" } }
                statement.executeQuery("SELECT value FROM info WHERE key='manifest'").use { result ->
                    require(result.next()) { "Missing snapshot manifest" }
                    val manifest = Json.parseToJsonElement(result.getString(1)).jsonObject
                    require(manifest["schemaVersion"]?.jsonPrimitive?.int == 2) { "Unsupported metadata snapshot" }
                    if (source != null) {
                        require(manifest.getValue("sources") == sourceHashes(source)) { "Snapshot source hashes differ; export/refresh a new snapshot" }
                        require(manifest["postalParserVersion"]?.jsonPrimitive?.int == 2) { "Snapshot postal parser is outdated; refresh postal data" }
                    }
                    listOf("lookup", "entities", "lexical", "pending").forEach { table -> statement.connection.prepareStatement("SELECT 1 FROM $table LIMIT 1").use { it.executeQuery().close() } }
                    manifest
                }
            }
        }
    }
    fun fetch(lock: File, output: File, archive: File? = null) {
        val spec = Json.parseToJsonElement(lock.readText()).jsonObject
        require(spec.getValue("schemaVersion").jsonPrimitive.int == 2) { "Unsupported snapshot lock" }
        if (output.isFile && sha256(output) == spec.getValue("databaseSha256").jsonPrimitive.content) { verify(output, lock); return }
        output.absoluteFile.parentFile.mkdirs()
        val work = Files.createTempDirectory(output.absoluteFile.parentFile.toPath(), ".snapshot-fetch-").toFile()
        try {
            val compressed = File(work, "snapshot.sqlite.gz")
            if (archive != null) { require(archive.length() <= MAX_BYTES) { "Oversized snapshot archive" }; archive.copyTo(compressed) } else {
                val url = URI(spec.getValue("url").jsonPrimitive.content)
                require(url.scheme == "https" && url.host == "github.com") { "Snapshot URL must be a GitHub HTTPS release asset" }
                val request = HttpRequest.newBuilder(url).timeout(Duration.ofMinutes(3)).build()
                val response = HttpClient.newBuilder().followRedirects(HttpClient.Redirect.NORMAL).connectTimeout(Duration.ofSeconds(20)).build().send(request, HttpResponse.BodyHandlers.ofInputStream())
                response.body().use { input -> require(response.statusCode() == 200) { "Snapshot download failed: HTTP ${response.statusCode()}" }; compressed.outputStream().use { boundedCopy(input, it) } }
            }
            require(compressed.length() <= MAX_BYTES && sha256(compressed) == spec.getValue("archiveSha256").jsonPrimitive.content) { "Snapshot archive checksum mismatch" }
            val database = File(work, "snapshot.sqlite")
            GZIPInputStream(compressed.inputStream()).use { input -> database.outputStream().use { boundedCopy(input, it) } }
            verify(database, lock)
            Files.move(database.toPath(), output.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        } finally { check(work.deleteRecursively()) }
    }
    private fun boundedCopy(input: java.io.InputStream, output: java.io.OutputStream) {
        val buffer = ByteArray(65536); var total = 0L
        while (true) { val n = input.read(buffer); if (n < 0) break; total += n; require(total <= MAX_BYTES) { "Snapshot exceeds 512 MiB" }; output.write(buffer, 0, n) }
    }
    fun export(reference: File, postal: File, source: File, base: File, output: File, lock: File, confirmed: File? = null) {
        output.absoluteFile.parentFile.mkdirs()
        val work = Files.createTempDirectory(output.absoluteFile.parentFile.toPath(), ".snapshot-export-").toFile()
        try {
            val database = File(work, "snapshot.sqlite")
            val wanted = sortedSetOf<String>()
            SupplementalSources.files.keys.forEach { id -> SupplementalSources.read(id, source) { row ->
                wanted.add(row.word.tango)
                if (id == "place") {
                    wanted.addAll(CandidateNormalizer.proposedSurfaces(row.word.tango))
                    row.word.tango.split('(', ')', '（', '）').filter { it.isNotBlank() && !PostalLexicon.annotation(it) }.forEach(wanted::add)
                }
            } }
            LexicalEvidence.load(confirmed = confirmed).all().forEach { wanted.add(it.surface) }
            val parentIds = sortedSetOf<String>(); val stored = hashSetOf<String>()
            DriverManager.getConnection("jdbc:sqlite:${database.path}").use { connection ->
                connection.createStatement().use { s ->
                    s.execute("PRAGMA max_page_count=${(MAX_BYTES - 1024 * 1024) / 4096}")
                    s.execute("CREATE TABLE lookup(surface TEXT PRIMARY KEY, ids TEXT NOT NULL, direct_ids TEXT NOT NULL)")
                    s.execute("CREATE TABLE entities(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
                    s.execute("CREATE TABLE lexical(reading TEXT, surface TEXT, categories TEXT, evidence TEXT, PRIMARY KEY(reading,surface,categories))")
                    s.execute("CREATE TABLE pending(surface TEXT PRIMARY KEY)")
                    s.execute("CREATE TABLE info(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                }
                connection.autoCommit = false
                connection.prepareStatement("INSERT OR IGNORE INTO lexical VALUES(?,?,?,?)").use { insert ->
                    fun save(fact: LexicalFact) { insert.setString(1, fact.reading); insert.setString(2, fact.surface); insert.setString(3, fact.categories.sorted().joinToString(",")); insert.setString(4, fact.evidence); insert.executeUpdate() }
                    PostalLexicon.read(postal, ::save)
                    LexicalEvidence.load(confirmed = confirmed).all().forEach(::save)
                }
                MetadataCatalog(reference, File(work, "unused.sqlite"), offline = true).use { catalog ->
                    connection.prepareStatement("INSERT INTO lookup VALUES(?,?,?)").use { lookup ->
                        connection.prepareStatement("INSERT OR IGNORE INTO entities VALUES(?,?)").use { entity ->
                            connection.prepareStatement("INSERT OR IGNORE INTO pending VALUES(?)").use { pending ->
                                fun store(id: String, includeParents: Boolean = true) {
                                    if (!stored.add(id)) return
                                    catalog.entity(id)?.let { body ->
                                        entity.setString(1, id); entity.setString(2, Json.encodeToString(body)); entity.executeUpdate()
                                        if (includeParents) { parentIds.addAll(body.types); parentIds.addAll(body.parents) }
                                    }
                                }
                                wanted.forEachIndexed { index, surface ->
                                    val links = catalog.links(surface)
                                    if (links != null && links.all.isNotEmpty()) {
                                        lookup.setString(1, surface); lookup.setString(2, Json.encodeToString(links.all.sorted())); lookup.setString(3, Json.encodeToString(links.direct.sorted())); lookup.executeUpdate()
                                        links.all.sorted().forEach { store(it) }
                                        if (links.all.any { id -> catalog.entity(id)?.let { it.readings.isEmpty() || it.types.isEmpty() } != false }) {
                                            pending.setString(1, surface); pending.executeUpdate()
                                        }
                                    } else { pending.setString(1, surface); pending.executeUpdate() }
                                    if (index % 50000 == 0) println("Snapshot surfaces: $index/${wanted.size}; entities=${stored.size}")
                                }
                                repeat(4) { depth ->
                                    val batch = parentIds.toList(); parentIds.clear()
                                    batch.forEach { store(it, depth < 3) }
                                }
                            }
                        }
                    }
                }
                val manifest = buildJsonObject {
                    put("schemaVersion", 2); put("postalParserVersion", 2); put("sources", sourceHashes(source)); put("referenceSha256", sha256(reference)); put("postalSha256", sha256(postal))
                    put("confirmedSha256", confirmed?.let(::sha256)?.let(::JsonPrimitive) ?: JsonNull)
                    put("baseIdDefSha256", sha256(File(base, "id.def")))
                    put("provenance", "Wikidata reduced structured facts (CC0); Japan Post UTF-8 postal data")
                }
                saveManifest(connection, manifest); connection.commit(); connection.autoCommit = true
                connection.createStatement().use { it.execute("VACUUM") }
            }
            verify(database, source = source)
            archive(database, output, lock)
        } finally { check(work.deleteRecursively()) }
    }
    private fun saveManifest(connection: Connection, manifest: JsonObject) = connection.prepareStatement("INSERT OR REPLACE INTO info VALUES('manifest',?)").use { it.setString(1, manifest.toString()); it.executeUpdate() }
    private fun archive(database: File, output: File, lock: File) {
        GZIPOutputStream(output.outputStream().buffered()).use { compressed -> database.inputStream().use { it.copyTo(compressed) } }
        val archiveHash = sha256(output); val tag = "dictionary-metadata-${archiveHash.take(16)}"
        val spec = buildJsonObject {
            put("schemaVersion", 2); put("tag", tag); put("asset", "snapshot.sqlite.gz"); put("archiveSha256", archiveHash); put("databaseSha256", sha256(database)); put("databaseBytes", database.length())
            put("url", "https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/download/$tag/snapshot.sqlite.gz")
        }
        lock.absoluteFile.parentFile.mkdirs(); lock.writeText(json.encodeToString(JsonObject.serializer(), spec) + "\n")
        println("Snapshot archive=${output.length()} bytes, database=${database.length()} bytes, lock=$lock")
    }
    fun refresh(snapshot: File, postal: File?, output: File, lock: File, budget: Int = 200, minutes: Int = 30) {
        verify(snapshot); output.absoluteFile.parentFile.mkdirs()
        val work = Files.createTempDirectory(output.absoluteFile.parentFile.toPath(), ".snapshot-refresh-").toFile()
        try {
            val database = File(work, "snapshot.sqlite"); snapshot.copyTo(database)
            val deadline = System.nanoTime() + Duration.ofMinutes(minutes.toLong()).toNanos()
            val pending = DriverManager.getConnection("jdbc:sqlite:${snapshot.toURI()}?mode=ro").use { c -> c.createStatement().use { s -> s.executeQuery("SELECT surface FROM pending ORDER BY surface").use { r -> buildList { while (r.next()) add(r.getString(1)) } } } }
            val resolved = linkedSetOf<String>()
            MetadataCatalog(cacheFile = database, apiBudget = budget, deadlineNanos = deadline).use { catalog ->
                for (batch in pending.chunked(50)) {
                    if (catalog.requests >= budget || catalog.unavailable || catalog.capacityReached || System.nanoTime() >= deadline) break
                    val processed = catalog.prepare(batch, refresh = true)
                    processed.forEach { surface ->
                        var complete = true
                        val queue = ArrayDeque(catalog.forSurface(surface).flatMap { it.types + it.parents }.map { it to 0 })
                        val visited = hashSetOf<String>()
                        while (queue.isNotEmpty()) {
                            val (id, depth) = queue.removeFirst()
                            if (!visited.add(id)) continue
                            val body = catalog.entity(id)
                            if (body == null) complete = false
                            else if (depth < 3) queue.addAll(body.parents.map { it to depth + 1 })
                        }
                        val links = catalog.links(surface)
                        if (links != null && complete && links.all.all { catalog.entity(it) != null }) resolved.add(surface)
                    }
                }
                DriverManager.getConnection("jdbc:sqlite:${database.path}").use { connection ->
                    connection.autoCommit = false
                    connection.prepareStatement("DELETE FROM pending WHERE surface=?").use { remove -> resolved.forEach { surface -> remove.setString(1, surface); remove.executeUpdate() } }
                    if (postal != null) connection.prepareStatement("DELETE FROM lexical WHERE evidence=?").use { it.setString(1, PostalLexicon.evidence); it.executeUpdate() }
                    if (postal != null) connection.prepareStatement("INSERT OR REPLACE INTO lexical VALUES(?,?,?,?)").use { insert -> PostalLexicon.read(postal) { f -> insert.setString(1, f.reading); insert.setString(2, f.surface); insert.setString(3, f.categories.sorted().joinToString(",")); insert.setString(4, f.evidence); insert.executeUpdate() } }
                    val before = verify(snapshot)
                    val manifest = buildJsonObject { before.forEach { (k,v) -> put(k,v) }; put("updateRequests", catalog.requests); put("updateUnavailable", catalog.unavailable); put("updateCapacityReached", catalog.capacityReached); put("previousDatabaseSha256", sha256(snapshot)); postal?.let { put("postalSha256", sha256(it)); put("postalParserVersion", 2) } }
                    saveManifest(connection, manifest); connection.commit()
                }
            }
            verify(database); archive(database, output, lock)
        } finally { check(work.deleteRecursively()) }
    }
}
