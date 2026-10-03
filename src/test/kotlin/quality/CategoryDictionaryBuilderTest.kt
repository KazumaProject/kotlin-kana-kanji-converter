package quality

import com.kazumaproject.dictionary.LoadedDictionary
import com.kazumaproject.quality.*
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files
import java.sql.DriverManager
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.test.*

class CategoryDictionaryBuilderTest {
    @Test fun buildsAllCategoriesWithoutCopiesOrTemporaryFiles() = temporary { root ->
        val base = File(root, "base"); val sources = File(root, "sources"); val reference = File(root, "reference.sqlite")
        inputFixture(base, sources)
        catalogFixture(reference)
        val before = sha256(reference)
        val output = File(root, "out/categories"); val reports = File(root, "reports")
        val cache = File(root, "cache.sqlite")
        CategoryDictionaryBuilder().build(CategoryDictionaryBuilder.Options(sources, base, output, reports, reference, cache, offline = true))
        assertEquals(before, sha256(reference))
        assertFalse(cache.exists())
        val pos = File(output, "pos_table.dat")
        fun pack(category: String) = LoadedDictionary.load(category, File(output, category), pos)
        assertEquals("藍畑", pack("place").lookup("あいはた").single().surface)
        assertEquals("高畑", pack("place").lookup("たかばたけ").single().surface)
        assertEquals("赤坂トラストタワー", pack("facility").lookup("あかさかとらすとたわー").single().surface)
        assertEquals("山田太郎", pack("person").lookup("やまだたろう").single().surface)
        assertEquals("コンパイラ", pack("technical").lookup("こんぱいら").single().surface)
        assertEquals("カレー", pack("food").lookup("かれー").single().surface)
        assertFalse(File(output, "unclassified").exists())
        assertTrue(java.util.zip.GZIPInputStream(File(reports, "review.tsv.gz").inputStream()).bufferedReader().use { it.readText() }.contains("未知語"))
        publishedCategories.forEach { category ->
            assertTrue(pack(category).readings().flatMap { pack(category).lookup(it) }.none { it.surface.contains("(31階)") || it.surface == "藍畑(高畑)" })
        }
        assertTrue(File(output, "event/token.dat").isFile)
        assertTrue(File(reports, "audit.tsv.gz").isFile)
        assertTrue(File(root, "out").listFiles()!!.none { it.name.startsWith(".category-build-") })
        val hashes = Json.parseToJsonElement(File(output, "manifest.json").readText()).jsonObject.getValue("artifacts")
        CategoryDictionaryBuilder().build(CategoryDictionaryBuilder.Options(sources, base, output, reports, reference, cache, offline = true))
        assertEquals(hashes, Json.parseToJsonElement(File(output, "manifest.json").readText()).jsonObject.getValue("artifacts"))
    }
    @Test fun semanticIncludeCannotBypassReadingVerification() = temporary { root ->
        val base = File(root, "base"); val sources = File(root, "sources"); inputFixture(base, sources)
        File(sources, "names.txt").writeText("まちがったよみ\t1\t1\t10\t確かな人物\n")
        val overrides = File(root, "overrides.tsv").apply {
            writeText("person\tまちがったよみ\t確かな人物\tinclude\tまちがったよみ\t確かな人物\tperson\thttps://example.org/name-only\n")
        }
        val output = File(root, "out/categories")
        CategoryDictionaryBuilder().build(CategoryDictionaryBuilder.Options(source = sources, base = base, output = output, reports = File(root, "reports"), overrides = overrides, confirmed = null))
        val person = LoadedDictionary.load("person", File(output, "person"), File(output, "pos_table.dat"))
        assertTrue(person.lookup("まちがったよみ").isEmpty())
    }
    @Test fun failedBuildCleansTemporaryFilesAndLeavesPublishedOutput() = temporary { root ->
        val base = File(root, "base"); val sources = File(root, "sources"); inputFixture(base, sources)
        File(sources, "names.txt").writeText("broken\n")
        val output = File(root, "out/categories").apply { mkdirs() }
        File(output, "preserved.txt").writeText("previous")
        assertFailsWith<IllegalArgumentException> { CategoryDictionaryBuilder().build(CategoryDictionaryBuilder.Options(sources, base, output, File(root, "reports"), offline = true)) }
        assertEquals("previous", File(output, "preserved.txt").readText())
        assertTrue(File(root, "out").listFiles()!!.none { it.name.startsWith(".category-build-") })
    }
    @Test fun readingMismatchAndHomonymsRemainUnclassified() = temporary { root ->
        val reference = File(root, "ref.sqlite"); catalogFixture(reference)
        MetadataCatalog(reference, File(root, "cache.sqlite"), offline = true).use { catalog ->
            val classifier = SemanticClassifier(catalog)
            val word = com.kazumaproject.dictionary.models.Dictionary("やまだじろう", 1, 1, 0, "山田太郎")
            assertEquals(setOf("unclassified"), classifier.classify(SourceRow("person", 1, word)).categories)
        }
    }
    @Test fun metadataCacheHonorsBudgetAndStoresOnlySlimFields() = temporary { root ->
        val cache = File(root, "cache.sqlite")
        val body = entity("Q100", "山田太郎", "Q5", "やまだたろう")
        MetadataCatalog(cacheFile = cache, limitMiB = 2, apiBudget = 1, transport = { buildJsonObject { put("entities", buildJsonObject { put("Q100", body) }) } }).use { catalog ->
            catalog.prepare(listOf("山田太郎")); catalog.prepare(listOf("未取得"))
            assertEquals(1, catalog.requests)
            assertEquals("Q100", catalog.forSurface("山田太郎").single().id)
        }
        assertTrue(cache.length() < 2 * 1024 * 1024)
        DriverManager.getConnection("jdbc:sqlite:${cache.path}").use { connection ->
            val saved = connection.createStatement().executeQuery("SELECT body FROM entities").use { it.next(); it.getString(1) }
            assertFalse(saved.contains("claims")); assertFalse(saved.contains("descriptions"))
        }
    }
    @Test fun apiBudgetDoesNotCacheAnUnsearchedTitleAsAbsent() = temporary { root ->
        val cache = File(root, "cache.sqlite")
        MetadataCatalog(cacheFile = cache, apiBudget = 1, transport = { buildJsonObject { put("entities", buildJsonObject {}) } }).use { catalog ->
            catalog.prepare(listOf("未確認の別名"))
            assertEquals(1, catalog.requests)
            assertTrue(catalog.forSurface("未確認の別名").isEmpty())
        }
        assertFalse(cache.exists())
    }
    @Test fun refreshFetchesExistingFactsAndHonorsDeadline() = temporary { root ->
        val cache = File(root, "cache.sqlite")
        MetadataCatalog(cacheFile = cache, apiBudget = 2, transport = {
            buildJsonObject { put("entities", buildJsonObject { put("Q100", entity("Q100", "山田太郎", "Q5", "やまだたろう")) }) }
        }).use { catalog ->
            catalog.prepare(listOf("山田太郎"))
            catalog.prepare(listOf("山田太郎"))
            assertEquals(1, catalog.requests)
            catalog.prepare(listOf("山田太郎"), refresh = true)
            assertEquals(2, catalog.requests)
        }
        MetadataCatalog(cacheFile = cache, apiBudget = 2, deadlineNanos = 0, transport = { error("Expired deadline must not request") }).use { catalog ->
            catalog.prepare(listOf("山田太郎"), refresh = true)
            assertEquals(0, catalog.requests)
        }
        MetadataCatalog(cacheFile = cache, apiBudget = 2, transport = { throw java.io.IOException("offline fixture") }).use { catalog ->
            assertTrue(catalog.prepare(listOf("山田太郎"), refresh = true).isEmpty())
            assertTrue(catalog.unavailable)
            assertEquals("Q100", catalog.forSurface("山田太郎").single().id)
        }
    }
    @Test fun cacheLimitStopsWritesAndDeletesRollbackJournal() = temporary { root ->
        val cache = File(root, "cache.sqlite")
        val body = buildJsonObject {
            val original = entity("Q100", "巨大別名", "Q5", "きょだいべつめい")
            original.forEach { (key, value) -> put(key, value) }
            put("aliases", buildJsonObject { put("ja", buildJsonArray {
                repeat(20000) { index -> add(buildJsonObject { put("value", "alias-$index-" + "x".repeat(80)) }) }
            }) })
        }
        MetadataCatalog(cacheFile = cache, limitMiB = 2, apiBudget = 1, transport = { buildJsonObject { put("entities", buildJsonObject { put("Q100", body) }) } }).use { catalog ->
            catalog.prepare(listOf("巨大別名"))
            assertTrue(catalog.capacityReached)
            assertTrue(catalog.forSurface("巨大別名").isEmpty())
        }
        assertTrue(root.walkTopDown().filter { it.isFile }.sumOf { it.length() } <= 2L * 1024 * 1024)
        assertFalse(File(cache.path + "-journal").exists())
    }
    @Test fun cannotUseReferenceCatalogAsWritableCache() = temporary { root ->
        val reference = File(root, "ref.sqlite"); catalogFixture(reference)
        val before = sha256(reference)
        assertFailsWith<IllegalArgumentException> { MetadataCatalog(reference, reference).close() }
        assertEquals(before, sha256(reference))
        MetadataCatalog(cacheFile = reference, apiBudget = 1).use { catalog ->
            assertFailsWith<IllegalArgumentException> { catalog.forSurface("山田太郎") }
        }
        assertEquals(before, sha256(reference))
    }
    private fun inputFixture(base: File, sources: File) {
        base.mkdirs(); sources.mkdirs()
        File(base, "id.def").writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n2 名詞,固有名詞,人名,一般,*,*,*\n3 名詞,固有名詞,地域,一般,*,*,*\n")
        (0..9).forEach { File(base, "dictionary%02d.txt".format(it)).writeText("") }
        File(base, "dictionary00.txt").writeText("あかさか\t3\t3\t10\t赤坂\nあいはた\t3\t3\t10\t藍畑\nたかばたけ\t3\t3\t10\t高畑\n")
        File(base, "suffix.txt").writeText("")
        File(sources, "names.txt").writeText("やまだたろう\t1\t1\t10\t山田太郎\n")
        fun zip(name: String, text: String) = ZipOutputStream(File(sources, "$name.zip").outputStream()).use { out -> out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry() }
        zip("place.txt", "あいはたたかばたけ\t1\t1\t20\t藍畑(高畑)\nあかさかあかさかとらすとたわーさんじゅういちかい\t1\t1\t20\t赤坂赤坂トラストタワー(31階)\n")
        zip("only_wiki.txt", "こんぱいら\t1\t1\t20\tコンパイラ\n")
        zip("only_neologd.txt", "かれー\t1\t1\t20\tカレー\n")
        zip("wiki_neologd_common.txt", "みちご\t1\t1\t20\t未知語\n")
    }
    private fun catalogFixture(file: File) {
        DriverManager.getConnection("jdbc:sqlite:${file.path}").use { connection ->
            connection.createStatement().use {
                it.execute("CREATE TABLE titles(title TEXT PRIMARY KEY, entity_ids TEXT)")
                it.execute("CREATE TABLE entity_searches(title TEXT PRIMARY KEY, entity_ids TEXT)")
                it.execute("CREATE TABLE entities(id TEXT PRIMARY KEY, body TEXT)")
            }
            listOf(entity("Q100", "山田太郎", "Q5", "やまだたろう"), entity("Q101", "コンパイラ", "Q17155032", "こんぱいら"), entity("Q102", "カレー", "Q2095", "かれー")).forEach { body ->
                val id = body.getValue("id").jsonPrimitive.content
                val name = body.getValue("labels").jsonObject.getValue("ja").jsonObject.getValue("value").jsonPrimitive.content
                connection.prepareStatement("INSERT INTO titles VALUES(?,?)").use { it.setString(1, name); it.setString(2, "[\"$id\"]"); it.executeUpdate() }
                connection.prepareStatement("INSERT INTO entities VALUES(?,?)").use { it.setString(1, id); it.setString(2, body.toString()); it.executeUpdate() }
            }
        }
    }
    private fun entity(id: String, name: String, type: String, reading: String) = buildJsonObject {
        put("id", id); put("labels", buildJsonObject { put("ja", buildJsonObject { put("value", name) }) })
        put("descriptions", "not retained")
        put("claims", buildJsonObject {
            put("P31", buildJsonArray { add(buildJsonObject { put("mainsnak", buildJsonObject { put("datavalue", buildJsonObject { put("value", buildJsonObject { put("id", type) }) }) }) }) })
            put("P1814", buildJsonArray { add(buildJsonObject { put("mainsnak", buildJsonObject { put("datavalue", buildJsonObject { put("value", reading) }) }) }) })
        })
    }
    private fun temporary(block: (File) -> Unit) { val root = Files.createTempDirectory("category-builder-").toFile(); try { block(root) } finally { root.deleteRecursively() } }
}
