package quality

import com.kazumaproject.quality.*
import kotlinx.serialization.json.*
import java.nio.file.Files
import java.security.MessageDigest
import java.sql.DriverManager
import java.io.ByteArrayOutputStream
import java.util.zip.GZIPOutputStream
import kotlin.test.*

class ResearchSnapshotTest {
    private fun compressed(text: String): ByteArray = ByteArrayOutputStream().also { output -> GZIPOutputStream(output).use { it.write(text.toByteArray()) } }.toByteArray()

    @Test fun rejectsMissingAndCyclicIdentityProofs() {
        DriverManager.getConnection("jdbc:sqlite::memory:").use { c ->
            c.createStatement().use { s ->
                s.execute("CREATE TABLE reading_facts(id TEXT,body TEXT)");s.execute("CREATE TABLE semantic_facts(id TEXT,body BLOB)");s.execute("CREATE TABLE quality_facts(id TEXT,body BLOB)")
                s.execute("INSERT INTO reading_facts VALUES('reading','{\"componentFacts\":[\"identity\"]}')")
            }
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verifyProofDependencies(c) }
            c.prepareStatement("INSERT INTO semantic_facts VALUES('identity',?)").use { it.setBytes(1,compressed("{}"));it.executeUpdate() }
            ResearchSnapshot.verifyProofDependencies(c)
            c.prepareStatement("UPDATE semantic_facts SET body=?").use { it.setBytes(1,compressed("{\"componentFacts\":[\"reading\"]}"));it.executeUpdate() }
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verifyProofDependencies(c) }
        }
    }
    @Test fun verifiesOfflineProofBindingsAndRejectsTamperingAndDraftPublication() {
        val file=Files.createTempFile("research-snapshot-", ".sqlite").toFile()
        try { DriverManager.getConnection("jdbc:sqlite:${file.path}").use { c ->
            c.createStatement().use { s ->
                s.execute("CREATE TABLE resolutions(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,left_id INTEGER,right_id INTEGER,cost INTEGER,status TEXT,categories TEXT,reading_ids TEXT,roles TEXT,reason TEXT,normalization_ids TEXT,exclusion_ids TEXT)")
                s.execute("CREATE TABLE source_map(source TEXT,line INTEGER,candidate_id TEXT)")
                s.execute("CREATE TABLE reading_facts(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,url TEXT,revision TEXT,sha256 TEXT,target TEXT,body TEXT)")
                s.execute("CREATE TABLE semantic_facts(id TEXT PRIMARY KEY,target TEXT,kind TEXT,url TEXT,revision TEXT,sha256 TEXT,body BLOB)")
                s.execute("CREATE TABLE quality_facts(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,target TEXT,kind TEXT,url TEXT,revision TEXT,sha256 TEXT,body BLOB)")
            }
            val hash=MessageDigest.getInstance("SHA-256");var n=0
            c.autoCommit=false
            c.prepareStatement("INSERT INTO resolutions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)").use { rows ->
                c.prepareStatement("INSERT INTO source_map VALUES('person',?,?)").use { mapping ->
                    c.prepareStatement("INSERT INTO reading_facts VALUES(?,?,?,'https://example.org/source','v1',?,'source','{}')").use { reading ->
                        c.prepareStatement("INSERT INTO semantic_facts VALUES(?,?,'meaning','https://example.org/source','v1',?,?)").use { meaning ->
                            for(definition in CategoryRegistry.definition.getValue("categories").jsonArray.map { it.jsonObject }.filter { it.getValue("core").jsonPrimitive.boolean }) {
                                val category=definition.getValue("id").jsonPrimitive.content
                                repeat(maxOf(1,definition.getValue("minimum").jsonPrimitive.int)) {
                                    n++;val id="%08d".format(n);val y="よみ$n";val surface="表記$n"
                                    val roles=buildJsonArray { add(buildJsonObject { put("category",category);put("target",id);put("sense","fixture");put("method","direct");put("evidenceIds",buildJsonArray { add("m$id") }) }) }.toString()
                                    val values=listOf(id,y,surface,1,1,10,"adopted",category,"[\"r$id\"]",roles,"verified","[]","[]")
                                    val encoded=JsonArray(values.map { if(it is Int) JsonPrimitive(it) else JsonPrimitive(it.toString()) }).toString()
                                    hash.update(encoded.toByteArray());hash.update(10.toByte())
                                    values.forEachIndexed { i,v -> rows.setObject(i+1,v) };rows.executeUpdate()
                                    mapping.setInt(1,n);mapping.setString(2,id);mapping.executeUpdate()
                                    reading.setString(1,"r$id");reading.setString(2,y);reading.setString(3,surface);reading.setString(4,"0".repeat(64));reading.executeUpdate()
                                    meaning.setString(1,"m$id");meaning.setString(2,id);meaning.setString(3,"0".repeat(64));meaning.setBytes(4,compressed("{}"));meaning.executeUpdate()
                                }
                            }
                        }
                    }
                }
            };c.commit();c.autoCommit=true
            val manifest=buildJsonObject {
                put("taxonomy",CategoryRegistry.definition);put("activeCategories",buildJsonArray { CategoryRegistry.core.forEach { add(it) } })
                put("research",buildJsonObject {
                    put("releaseReady",false);put("unprocessed",0);put("errors",0);put("candidates",n);put("sourceRows",n);put("adopted",n);put("excludedConfirmed",0);put("notDistributed",0)
                    put("resolutionSha256",hash.digest().joinToString("") { "%02x".format(it) })
                    put("validation",buildJsonObject {
                        put("eligible",300);put("adoptable",300);put("goldSha256","a".repeat(64))
                        put("precision",buildJsonObject {
                            for (method in listOf("direct","source_review","ai")) put(method,buildJsonObject {
                                put("n",if (method=="direct") 300 else 0);put("correct",if (method=="direct") 300 else 0)
                                put("population",if (method=="direct") n else 0);if (method!="direct") put("lower95",0.0)
                            })
                        })
                    })
                })
            }
            ResearchSnapshot.verify(c,manifest,true)
            fun methodManifest(method: String, validated: Boolean): JsonObject {
                c.createStatement().use { it.execute("UPDATE resolutions SET roles=json_set(roles,'$[0].method','$method')") }
                val updatedHash=MessageDigest.getInstance("SHA-256")
                c.createStatement().use { statement -> statement.executeQuery("SELECT * FROM resolutions ORDER BY id").use { rows ->
                    while(rows.next()) {
                        updatedHash.update(JsonArray((1..13).map { i -> if(i in 4..6) JsonPrimitive(rows.getInt(i)) else JsonPrimitive(rows.getString(i)) }).toString().toByteArray())
                        updatedHash.update(10.toByte())
                    }
                } }
                val originalResearch=manifest.getValue("research").jsonObject
                val originalValidation=originalResearch.getValue("validation").jsonObject
                return JsonObject(manifest + ("research" to JsonObject(originalResearch + mapOf(
                    "resolutionSha256" to JsonPrimitive(updatedHash.digest().joinToString("") { "%02x".format(it) }),
                    "validation" to JsonObject(originalValidation + ("precision" to buildJsonObject {
                        for(route in listOf("direct","source_review","ai")) put(route,buildJsonObject {
                            val used=route==method && validated
                            put("population",if(used) n else 0);put("n",if(used) 300 else 0);put("correct",if(used) 300 else 0)
                            if(route!="direct") put("lower95",if(used) .99006 else 0.0)
                        })
                    }))
                ))))
            }
            // Zero model use remains valid with sufficiently validated source reviews;
            // an exported inferred method absent from validation must fail closed.
            val sourceReviewManifest=methodManifest("source_review",true)
            c.createStatement().use { it.execute("UPDATE semantic_facts SET kind='context'") }
            ResearchSnapshot.verify(c,sourceReviewManifest,true)
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verify(c,methodManifest("source_review",false),true) }
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verify(c,methodManifest("unchecked",false),true) }
            val aiManifest=methodManifest("ai",true)
            ResearchSnapshot.verify(c,aiManifest,true)
            methodManifest("direct",true)
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verify(c,manifest,false) }
            c.createStatement().use { it.execute("UPDATE reading_facts SET reading='べつ' WHERE id='r00000001'") }
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verify(c,manifest,true) }
            c.createStatement().use { it.execute("UPDATE reading_facts SET reading='よみ1' WHERE id='r00000001'");it.execute("UPDATE semantic_facts SET target='unrelated' WHERE id='m00000001'") }
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verify(c,manifest,true) }
            c.createStatement().use { it.execute("UPDATE semantic_facts SET target='00000001' WHERE id='m00000001'");it.execute("UPDATE resolutions SET reason='tampered' WHERE id='00000001'") }
            assertFailsWith<IllegalArgumentException> { ResearchSnapshot.verify(c,manifest,true) }
        } } finally { file.delete() }
    }
}
