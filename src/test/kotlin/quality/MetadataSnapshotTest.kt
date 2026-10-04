package quality

import com.kazumaproject.quality.*
import com.kazumaproject.dictionary.models.Dictionary
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files
import java.sql.DriverManager
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.test.*

class MetadataSnapshotTest {
    @Test fun exportsFactsAndProvenanceAndRebuildsOffline() = temporary { root ->
        val (base, source, reference, postal) = inputs(root)
        val archive = File(root, "snapshot.gz"); val lock = File(root, "lock.json"); val snapshot = File(root, "snapshot.sqlite")
        val before = sha256(reference)
        MetadataSnapshot.export(reference, postal, source, base, archive, lock)
        assertEquals(before, sha256(reference))
        MetadataSnapshot.fetch(lock, snapshot, archive)
        MetadataSnapshot.verify(snapshot, lock, source)
        val lexical = LexicalEvidence.load(snapshot, null)
        assertTrue(lexical.has("あいはた", "藍畑", "place"))
        assertTrue(lexical.has("だいじゅう", "第十", "place"))
        MetadataCatalog(cacheFile = snapshot, offline = true).use { catalog ->
            assertEquals(setOf("Q100"), catalog.links("Java")!!.direct)
            assertEquals(setOf("Q200"), catalog.links("Java")!!.searched)
            val classifier = SemanticClassifier(catalog)
            assertEquals(setOf("technical"), classifier.classify(SourceRow("neologd", 1, Dictionary("じゃば", 1, 1, 10, "Java"))).categories)
            val quality = QualityEvaluator(catalog, emptyMap(), lexical)
            assertEquals("held", quality.evaluate(SourceRow("neologd", 1, Dictionary("じゃば", 1, 1, 10, "Java"))).state)
            assertEquals("accepted", QualityEvaluator(catalog, mapOf("Java" to setOf("じゃば")), lexical).evaluate(SourceRow("neologd", 1, Dictionary("じゃば", 1, 1, 10, "Java"))).state)
        }
        val output = File(root, "categories"); val reports = File(root, "reports")
        val options = CategoryDictionaryBuilder.Options(source, base, output, reports, snapshot = snapshot, confirmed = null)
        CategoryDictionaryBuilder().build(options)
        val hashes = File(output,"manifest.json").readText()
        CategoryDictionaryBuilder().build(options)
        assertEquals(hashes, File(output,"manifest.json").readText())
        assertFalse(File(output,"unclassified").exists())
        listOf("LICENSE-JMDICT.html","LICENSE-CC-BY-SA-4.0.txt").forEach { File(root,it).writeText("fixture license\n") }
        val notices = File(root,"NOTICES.md").apply { writeText("fixture source notices\n") }
        val zip = File(root,"pack.zip")
        CategoryPackage.write(output,zip,notices); CategoryPackage.verify(zip)
        val zipHash = sha256(zip); CategoryPackage.write(output,zip,notices); assertEquals(zipHash,sha256(zip))
        File(source,"names.txt").appendText("new\t1\t1\t1\tnew\n")
        assertFailsWith<IllegalArgumentException> { MetadataSnapshot.verify(snapshot,lock,source) }
        assertTrue(root.listFiles()!!.none { it.name.startsWith(".snapshot-") })
    }
    @Test fun corruptArchiveLeavesExistingOutputAndCleansTemporaryFiles() = temporary { root ->
        val (base, source, reference, postal) = inputs(root)
        val archive = File(root,"snapshot.gz"); val lock = File(root,"lock.json")
        MetadataSnapshot.export(reference,postal,source,base,archive,lock)
        archive.appendBytes(byteArrayOf(1))
        val output=File(root,"out.sqlite").apply { writeText("previous") }
        assertFailsWith<IllegalArgumentException> { MetadataSnapshot.fetch(lock,output,archive) }
        assertEquals("previous",output.readText())
        assertTrue(root.listFiles()!!.none { it.name.startsWith(".snapshot-") })
    }
    @Test fun onlineUpdateWritesDirectProvenanceToStrictSnapshotSchema() = temporary { root ->
        val (base, source, reference, postal) = inputs(root)
        val archive = File(root, "snapshot.gz"); val lock = File(root, "lock.json"); val snapshot = File(root, "snapshot.sqlite")
        MetadataSnapshot.export(reference, postal, source, base, archive, lock)
        MetadataSnapshot.fetch(lock, snapshot, archive)
        val body = buildJsonObject {
            put("id", "Q100")
            put("labels", buildJsonObject { put("ja", buildJsonObject { put("value", "Java") }) })
            put("sitelinks", buildJsonObject { put("jawiki", buildJsonObject { put("title", "Java") }) })
        }
        MetadataCatalog(cacheFile = snapshot, apiBudget = 1, transport = { buildJsonObject { put("entities", buildJsonObject { put("Q100", body) }) } }).use { catalog ->
            assertEquals(setOf("Java"), catalog.prepare(listOf("Java"), refresh = true))
            assertEquals(setOf("Q100"), catalog.links("Java")!!.direct)
        }
        MetadataSnapshot.verify(snapshot)
    }
    @Test fun zeroBudgetRefreshPreservesFactsAndLeavesUnresolvedQueue() = temporary { root ->
        val (base, source, reference, postal) = inputs(root)
        val archive=File(root,"snapshot.gz");val lock=File(root,"lock.json");val snapshot=File(root,"snapshot.sqlite")
        MetadataSnapshot.export(reference,postal,source,base,archive,lock)
        MetadataSnapshot.fetch(lock,snapshot,archive)
        val initial=sha256(snapshot)
        val updated=File(root,"updated.gz");val nextLock=File(root,"next.json")
        MetadataSnapshot.refresh(snapshot,null,updated,nextLock,0)
        assertEquals(initial,sha256(snapshot))
        val next=File(root,"next.sqlite");MetadataSnapshot.fetch(nextLock,next,updated)
        DriverManager.getConnection("jdbc:sqlite:${next.path}").use { connection ->
            val count=connection.createStatement().executeQuery("SELECT count(*) FROM pending").use { it.next();it.getInt(1) }
            assertTrue(count>0)
        }
        MetadataCatalog(cacheFile=next,offline=true).use { assertEquals(setOf("Q100"),it.links("Java")!!.direct) }
        val candidate = File(root, "candidate/snapshot.sqlite.gz")
        val log = java.io.PrintWriter(java.io.StringWriter())
        assertEquals(0, com.kazumaproject.cli.DictionaryCli.run(arrayOf("metadata", "refresh", "--snapshot", snapshot.path, "--output", candidate.path, "--api-budget", "0"), log, log))
        assertTrue(File(candidate.parentFile, "snapshot.lock.json").isFile)
        assertEquals(initial, sha256(snapshot))
    }
    @Test fun csvHandlesQuotedCommasAndRejectsBrokenQuotes() {
        assertEquals(listOf("a,b","c\"d",""),PostalLexicon.csv("\"a,b\",\"c\"\"d\","))
        assertFailsWith<IllegalArgumentException> { PostalLexicon.csv("\"broken") }
        assertFalse(PostalLexicon.annotation("第十"));assertFalse(PostalLexicon.annotation("一円"));assertTrue(PostalLexicon.annotation("31階"))
        assertTrue(PostalLexicon.instruction("全域"));assertTrue(PostalLexicon.instruction("以下に掲載がない場合"))
        assertTrue(PostalLexicon.annotation("区"))
    }
    private fun inputs(root:File):List<File> {
        val base=File(root,"base").apply { mkdirs() };val source=File(root,"source").apply { mkdirs() }
        File(base,"id.def").writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n")
        (0..9).forEach { File(base,"dictionary%02d.txt".format(it)).writeText(if(it==0) "じゃば\t1\t1\t10\tJava\n" else "") }
        File(base,"suffix.txt").writeText("");File(source,"names.txt").writeText("なぞ\t1\t1\t10\t謎\n")
        fun zip(file:File,name:String,text:String) = ZipOutputStream(file.outputStream()).use { it.putNextEntry(ZipEntry(name));it.write(text.toByteArray());it.closeEntry() }
        SupplementalSources.files.filterKeys { it!="person" }.forEach { (id,name)-> zip(File(source,name),name.removeSuffix(".zip"),if(id=="neologd") "じゃば\t1\t1\t10\tJava\n" else "") }
        val postal=File(root,"postal.zip");zip(postal,"utf_ken_all.csv","00000,000,0000000,トクシマケン,イシイチョウ,アイハタ（ダイジュウ）,徳島県,石井町,藍畑（第十）,0,0,0,0,0,0\n")
        val reference=File(root,"ref.sqlite")
        DriverManager.getConnection("jdbc:sqlite:${reference.path}").use { c ->
            c.createStatement().use { s->s.execute("CREATE TABLE titles(title TEXT PRIMARY KEY,entity_ids TEXT)");s.execute("CREATE TABLE entity_searches(title TEXT PRIMARY KEY,entity_ids TEXT)");s.execute("CREATE TABLE entities(id TEXT PRIMARY KEY,body TEXT)");s.execute("INSERT INTO titles VALUES('Java','[\"Q100\"]')");s.execute("INSERT INTO entity_searches VALUES('Java','[\"Q200\"]')") }
            listOf("Q100" to "Q9143","Q200" to "Q11424").forEach { (id,type)->
                val body=buildJsonObject { put("id",id);put("labels",buildJsonObject { put("ja",buildJsonObject { put("value","Java") }) });put("claims",buildJsonObject { put("P31",buildJsonArray { add(buildJsonObject { put("mainsnak",buildJsonObject { put("datavalue",buildJsonObject { put("value",buildJsonObject { put("id",type) }) }) }) }) }) }) }
                c.prepareStatement("INSERT INTO entities VALUES(?,?)").use { it.setString(1,id);it.setString(2,body.toString());it.executeUpdate() }
            }
        }
        return listOf(base,source,reference,postal)
    }
    private fun temporary(block:(File)->Unit) { val root=Files.createTempDirectory("snapshot-test-").toFile();try { block(root) } finally { root.deleteRecursively() } }
}
