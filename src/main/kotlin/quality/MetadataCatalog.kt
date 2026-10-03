package com.kazumaproject.quality

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.io.Closeable
import java.io.File
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import java.sql.Connection
import java.sql.DriverManager
import java.time.Duration
import java.util.zip.GZIPInputStream

@Serializable
data class MetadataEntity(val id: String, val names: Set<String>, val types: Set<String>, val parents: Set<String>, val readings: Set<String>, val revision: String? = null, val title: String? = null)

/** Reads the older full catalog without changing it. New data is reduced before caching. */
class MetadataCatalog(
    reference: File? = null,
    private val cacheFile: File = File("build/dictionary-metadata/cache.sqlite"),
    private val limitMiB: Int = 512,
    private val apiBudget: Int = 200,
    private val offline: Boolean = false,
    private val transport: ((Map<String, String>) -> JsonObject)? = null,
    private val deadlineNanos: Long = Long.MAX_VALUE,
) : Closeable {
    private val json = Json { ignoreUnknownKeys = true }
    private val referenceConnection: Connection? = reference?.let {
        require(it.isFile) { "Missing metadata database: $it" }
        require(!cacheFile.exists() || !Files.isSameFile(it.toPath(), cacheFile.toPath())) {
            "The writable cache must be separate from the read-only reference catalog"
        }
        DriverManager.getConnection("jdbc:sqlite:${it.toURI()}?mode=ro")
    }
    private var cacheConnection: Connection? = null
    private val memo = object : LinkedHashMap<String, MetadataEntity?>(1024, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, MetadataEntity?>) = size > 8192
    }
    private val client by lazy { HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(15)).build() }
    var requests = 0; private set
    var unavailable = false; private set
    var capacityReached = false; private set
    var referenceHits = 0; private set
    var cacheHits = 0; private set

    init { require(limitMiB >= 2 && apiBudget >= 0) { "Cache limit must be >=2 MiB and API budget nonnegative" } }

    private fun cache(create: Boolean): Connection? {
        if (create && cacheFile.length() >= (limitMiB - 1L) * 1024 * 1024) { capacityReached = true; return null }
        cacheConnection?.let { return it }
        if (!cacheFile.isFile && !create) return null
        if (offline && !cacheFile.isFile) return null
        if (create) cacheFile.parentFile?.mkdirs()
        if (cacheFile.isFile) DriverManager.getConnection("jdbc:sqlite:${cacheFile.toURI()}?mode=ro").use { existing ->
            val tables = existing.createStatement().use { statement -> statement.executeQuery("SELECT name FROM sqlite_master WHERE type='table'").use { result -> buildSet { while (result.next()) add(result.getString(1)) } } }
            require(tables.isEmpty() || ("lookup" in tables && "entities" in tables && "titles" !in tables)) { "Not a dictionary-cli cache; refusing to modify: $cacheFile" }
        }
        val connection = DriverManager.getConnection(if (offline) "jdbc:sqlite:${cacheFile.toURI()}?mode=ro" else "jdbc:sqlite:${cacheFile.absolutePath}")
        if (!offline) connection.createStatement().use { statement ->
            statement.execute("PRAGMA journal_mode=DELETE")
            val pageSize = statement.executeQuery("PRAGMA page_size").use { it.next(); it.getLong(1) }
            statement.execute("PRAGMA max_page_count=${(limitMiB - 1L) * 1024 * 1024 / pageSize}")
            statement.execute("CREATE TABLE IF NOT EXISTS lookup(surface TEXT PRIMARY KEY, ids TEXT NOT NULL, direct_ids TEXT NOT NULL DEFAULT '[]')")
            if (!hasColumn(connection, "lookup", "direct_ids")) statement.execute("ALTER TABLE lookup ADD COLUMN direct_ids TEXT NOT NULL DEFAULT '[]'")
            statement.execute("CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        }
        cacheConnection = connection
        return connection
    }

    private fun query(connection: Connection?, table: String, keyColumn: String, valueColumn: String, key: String): String? {
        if (connection == null) return null
        return connection.prepareStatement("SELECT $valueColumn FROM $table WHERE $keyColumn=?").use { statement ->
            statement.setString(1, key)
            statement.executeQuery().use { result -> if (result.next()) result.getString(1) else null }
        }
    }

    data class Links(val direct: Set<String>, val searched: Set<String>) { val all get() = direct + searched }

    private fun hasColumn(connection: Connection, table: String, column: String): Boolean = connection.createStatement().use { statement ->
        statement.executeQuery("PRAGMA table_info($table)").use { result ->
            var found = false
            while (result.next()) if (result.getString("name") == column) found = true
            found
        }
    }

    fun links(surface: String): Links? {
        val cached = cache(false)
        query(cached, "lookup", "surface", "ids", surface)?.let { ids ->
            cacheHits++
            val direct = if (cached != null && hasColumn(cached, "lookup", "direct_ids")) query(cached, "lookup", "surface", "direct_ids", surface) else null
            val all = json.decodeFromString<List<String>>(ids).toSet()
            val titles = direct?.let { json.decodeFromString<List<String>>(it).toSet() }.orEmpty()
            return Links(titles, all - titles)
        }
        val title = query(referenceConnection, "titles", "title", "entity_ids", surface)
        val search = query(referenceConnection, "entity_searches", "title", "entity_ids", surface)
        if (title == null && search == null) return null
        referenceHits++
        return Links(title?.let { json.decodeFromString<List<String>>(it).toSet() }.orEmpty(), search?.let { json.decodeFromString<List<String>>(it).toSet() }.orEmpty())
    }

    private fun ids(surface: String): Set<String>? = links(surface)?.all

    fun prepare(surfaces: List<String>, refresh: Boolean = false): Set<String> {
        val processed = linkedSetOf<String>()
        if (offline || unavailable || capacityReached || requests >= apiBudget || System.nanoTime() >= deadlineNanos) return processed
        surfaces.distinct().filter { refresh || ids(it) == null }.chunked(50).forEach { batch ->
            val response = request(mapOf("action" to "wbgetentities", "sites" to "jawiki", "titles" to batch.joinToString("|"), "redirects" to "yes", "props" to "labels|aliases|claims|sitelinks", "languages" to "ja|en", "sitefilter" to "jawiki")) ?: return processed
            val entities = response["entities"]?.jsonObject?.values.orEmpty().mapNotNull(::parseEntity)
            entities.forEach(::saveEntity)
            batch.forEach surfaceLoop@ { surface ->
                val exact = entities.filter { surface in it.names }.map { it.id }.toMutableSet()
                if (exact.isEmpty()) {
                    if (requests >= apiBudget) return@surfaceLoop
                    val search = request(mapOf("action" to "wbsearchentities", "search" to surface, "language" to "ja", "type" to "item", "limit" to "10"))
                    val candidates = search?.get("search")?.jsonArray.orEmpty().mapNotNull { it.jsonObject["id"]?.jsonPrimitive?.content }
                    fetchIds(candidates)
                    exact.addAll(candidates.filter { entity(it)?.names?.contains(surface) == true })
                    // Failed or budget-limited searches are not permanent negative results.
                    if (search == null || candidates.any { memo[it] == null }) return@surfaceLoop
                }
                val direct = entities.filter { it.title == surface }.map { it.id }
                if (save("lookup", "surface", "ids", surface, json.encodeToString(exact.toList()), json.encodeToString(direct))) {
                    processed.add(surface)
                }
            }
        }
        return processed
    }

    fun forSurface(surface: String): List<MetadataEntity> = ids(surface).orEmpty().mapNotNull(::entity)

    fun matched(surface: String, reading: String): List<MetadataEntity> {
        val links = links(surface) ?: return emptyList()
        fun compatible(entity: MetadataEntity) = surface in entity.names && (entity.readings.isEmpty() || entity.readings.any { SemanticClassifier.normalizeReading(it) == SemanticClassifier.normalizeReading(reading) })
        val direct = links.direct.mapNotNull(::entity).filter { compatible(it) && it.types.none { type -> type in setOf("Q4167410", "Q4167836", "Q13406463") } }
        val searched = links.searched.mapNotNull(::entity).filter { compatible(it) && it.readings.any { r -> SemanticClassifier.normalizeReading(r) == SemanticClassifier.normalizeReading(reading) } }
        return (direct + searched).distinctBy { it.id }
    }

    fun entity(id: String): MetadataEntity? {
        if (memo.containsKey(id)) return memo[id]
        val cached = query(cache(false), "entities", "id", "body", id)
        if (cached != null) return json.decodeFromString<MetadataEntity>(cached).also { memo[id] = it }
        val existing = query(referenceConnection, "entities", "id", "body", id)
        if (existing != null) return parseEntity(json.parseToJsonElement(existing)).also { memo[id] = it }
        fetchIds(listOf(id))
        return memo[id]
    }

    private fun fetchIds(ids: List<String>) {
        if (ids.isEmpty() || offline || unavailable || capacityReached) return
        ids.chunked(50).forEach { batch ->
            val response = request(mapOf("action" to "wbgetentities", "ids" to batch.joinToString("|"), "props" to "labels|aliases|claims|sitelinks", "languages" to "ja|en", "sitefilter" to "jawiki")) ?: return
            response["entities"]?.jsonObject?.values.orEmpty().forEach { element -> parseEntity(element)?.let(::saveEntity) }
            batch.forEach { if (!memo.containsKey(it)) memo[it] = null }
        }
    }

    private fun saveEntity(entity: MetadataEntity) {
        if (save("entities", "id", "body", entity.id, json.encodeToString(entity))) memo[entity.id] = entity
    }

    private fun save(table: String, keyColumn: String, valueColumn: String, key: String, value: String, directIds: String? = null): Boolean {
        if (offline || capacityReached) return false
        val connection = cache(true) ?: return false
        try {
            val sql = if (table == "lookup") "INSERT OR REPLACE INTO lookup(surface,ids,direct_ids) VALUES(?,?,?)" else "INSERT OR REPLACE INTO $table($keyColumn,$valueColumn) VALUES(?,?)"
            connection.prepareStatement(sql).use {
                it.setString(1, key); it.setString(2, value)
                if (table == "lookup") it.setString(3, requireNotNull(directIds))
                it.executeUpdate()
            }
        } catch (e: java.sql.SQLException) {
            if (e.errorCode == 13) capacityReached = true else throw e
        }
        return !capacityReached
    }

    private fun request(parameters: Map<String, String>): JsonObject? {
        if (offline || unavailable || capacityReached || requests >= apiBudget || System.nanoTime() >= deadlineNanos) return null
        val params = parameters + mapOf("format" to "json", "maxlag" to "5")
        val query = params.entries.joinToString("&") { (key, value) -> "$key=${URLEncoder.encode(value, Charsets.UTF_8)}" }
        repeat(2) {
            if (requests >= apiBudget) { unavailable = true; return null }
            requests++
            try {
                transport?.let { return it(params) }
                val request = HttpRequest.newBuilder(URI("https://www.wikidata.org/w/api.php?$query"))
                    .timeout(Duration.ofSeconds(30)).header("User-Agent", "KotlinKanaKanjiDictionary/1.0 (https://github.com/KazumaProject/kotlin-kana-kanji-converter)")
                    .header("Accept-Encoding", "gzip").build()
                val response = client.send(request, HttpResponse.BodyHandlers.ofInputStream())
                response.body().use { body ->
                    if (response.statusCode() == 429 || response.statusCode() == 503) {
                        val delay = response.headers().firstValue("Retry-After").orElse("2").toLongOrNull() ?: 2
                        if (delay > 30) { unavailable = true; return null }
                        Thread.sleep(delay.coerceAtLeast(1) * 1000)
                        return@repeat
                    }
                    if (response.statusCode() != 200) { unavailable = true; return null }
                    val stream = if (response.headers().firstValue("Content-Encoding").orElse("") == "gzip") GZIPInputStream(body) else body
                    val bytes = stream.readNBytes(8 * 1024 * 1024 + 1)
                    require(bytes.size <= 8 * 1024 * 1024) { "Metadata response exceeds 8 MiB" }
                    val decoded = json.parseToJsonElement(bytes.toString(Charsets.UTF_8)).jsonObject
                    if (decoded.containsKey("error")) {
                        if (decoded["error"]?.jsonObject?.get("code")?.jsonPrimitive?.content == "maxlag") { Thread.sleep(2000); return@repeat }
                        unavailable = true; return null
                    }
                    Thread.sleep(250)
                    return decoded
                }
            } catch (e: InterruptedException) { Thread.currentThread().interrupt(); throw e }
            catch (e: Exception) { if (it == 1) { unavailable = true; System.err.println("Metadata fetch stopped: ${e.message}") } }
        }
        return null
    }

    override fun close() {
        try { cacheConnection?.close() } finally { referenceConnection?.close() }
    }

    companion object {
        fun parseEntity(element: JsonElement): MetadataEntity? {
            val obj = element as? JsonObject ?: return null
            if (obj.containsKey("missing")) return null
            val id = obj["id"]?.jsonPrimitive?.content ?: return null
            val names = linkedSetOf<String>()
            obj["labels"]?.jsonObject?.filterKeys { it in setOf("ja", "en") }?.values?.forEach { it.jsonObject["value"]?.jsonPrimitive?.content?.let(names::add) }
            obj["aliases"]?.jsonObject?.filterKeys { it in setOf("ja", "en") }?.values?.forEach { aliases -> aliases.jsonArray.forEach { it.jsonObject["value"]?.jsonPrimitive?.content?.let(names::add) } }
            obj["sitelinks"]?.jsonObject?.get("jawiki")?.jsonObject?.get("title")?.jsonPrimitive?.content?.let(names::add)
            val claims = obj["claims"]?.jsonObject ?: JsonObject(emptyMap())
            fun values(property: String): List<JsonElement> = claims[property]?.jsonArray.orEmpty().filter { it.jsonObject["rank"]?.jsonPrimitive?.content != "deprecated" }.mapNotNull {
                it.jsonObject["mainsnak"]?.jsonObject?.get("datavalue")?.jsonObject?.get("value")
            }
            values("P1476").forEach { (it as? JsonObject)?.get("text")?.jsonPrimitive?.content?.let(names::add) }
            fun qids(property: String) = values(property).mapNotNull { (it as? JsonObject)?.get("id")?.jsonPrimitive?.content }.toSet()
            val readings = values("P1814").mapNotNull { (it as? JsonPrimitive)?.content }.toSet()
            return MetadataEntity(id, names, qids("P31"), qids("P279"), readings, obj["lastrevid"]?.jsonPrimitive?.contentOrNull, obj["sitelinks"]?.jsonObject?.get("jawiki")?.jsonObject?.get("title")?.jsonPrimitive?.contentOrNull)
        }
    }
}
