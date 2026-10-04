package com.kazumaproject.quality

import java.sql.Connection
import java.security.MessageDigest
import java.io.ByteArrayInputStream
import java.util.zip.GZIPInputStream
import kotlinx.serialization.json.*

object ResearchSnapshot {
    fun verifyProofDependencies(connection: Connection) {
        val known=mutableSetOf<String>()
        val graph=mutableMapOf<String,List<String>>()
        connection.createStatement().use { statement ->
            for(table in listOf("reading_facts","semantic_facts","quality_facts")) {
                statement.executeQuery("SELECT id,body FROM $table").use { rows ->
                    while(rows.next()) {
                        val id=rows.getString(1)
                        require(known.add(id)) { "Duplicate exported proof identity" }
                        val raw=rows.getBytes(2)
                        require(raw!=null) { "Missing exported proof body" }
                        val text=if(table=="reading_facts") raw.toString(Charsets.UTF_8) else GZIPInputStream(ByteArrayInputStream(raw)).bufferedReader(Charsets.UTF_8).use { it.readText() }
                        val body=Json.parseToJsonElement(text).jsonObject
                        val refs=(body["componentFacts"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList()) +
                            listOf("fullAddressEvidence","outputEvidence","prefixEvidence","addressFact","sourceEvidence").mapNotNull { body[it]?.jsonPrimitive?.content }
                        require(refs.all { it.isNotBlank() }) { "Invalid exported proof dependency" }
                        if(refs.isNotEmpty()) graph[id]=refs
                    }
                }
            }
        }
        require(graph.values.flatten().all { it in known }) { "Missing exported proof dependency" }
        val checked=mutableSetOf<String>()
        for(root in graph.keys) {
            val path=mutableSetOf<String>();val stack=ArrayDeque<Pair<String,Boolean>>();stack.add(root to false)
            while(stack.isNotEmpty()) {
                val (id,leaving)=stack.removeLast()
                if(leaving) { path.remove(id);checked.add(id);continue }
                require(id !in path) { "Cyclic exported proof dependency" }
                if(id in checked)continue
                path.add(id);stack.add(id to true);graph[id]?.forEach { stack.add(it to false) }
            }
        }
    }
    fun verify(connection: Connection, manifest: JsonObject, allowCandidate: Boolean) {
        val research = manifest.getValue("research").jsonObject
        require(allowCandidate || research.getValue("releaseReady").jsonPrimitive.boolean) { "Research candidate is not approved for release" }
        require(research.getValue("unprocessed").jsonPrimitive.int == 0 && research.getValue("errors").jsonPrimitive.int == 0) { "Incomplete research snapshot" }
        val validation = research.getValue("validation").jsonObject
        val eligible = validation.getValue("eligible").jsonPrimitive.int
        val adoptable = validation.getValue("adoptable").jsonPrimitive.int
        require(eligible > 0 && adoptable in 0..eligible && adoptable.toDouble() / eligible >= 0.95) { "Adoption coverage gate failed" }
        require(validation.getValue("goldSha256").jsonPrimitive.content.matches(Regex("[a-f0-9]{64}"))) { "Independent frozen gold checksum missing" }
        val methods = setOf("direct", "source_review", "ai")
        val precision = validation.getValue("precision").jsonObject
        require(precision.keys == methods) { "Invalid classification methods in validation" }
        val populations = methods.associateWith { method ->
            val stats = precision.getValue(method).jsonObject
            val n = stats.getValue("n").jsonPrimitive.int
            val correct = stats.getValue("correct").jsonPrimitive.int
            val population = stats.getValue("population").jsonPrimitive.int
            require(population >= 0 && n in 0..population && correct in 0..n) { "Invalid classification population/validation: $method" }
            if (method != "direct" && population > 0) {
                val lower = stats.getValue("lower95").jsonPrimitive.double
                require(n > 0 && correct.toDouble() / n >= 0.995 && lower in 0.99..1.0) { "$method precision gate failed" }
            }
            population
        }
        if (!allowCandidate) {
            val acceptance=research.getValue("acceptance").jsonObject
            require(listOf("categoryReviews","nonDistributedReview","conversionRegression","linuxBinaryParity","zipVerified").all { acceptance[it]?.jsonPrimitive?.boolean==true }) { "Required release acceptance records missing" }
            require(acceptance.getValue("resolutionSha256")==research.getValue("resolutionSha256")) { "Acceptance belongs to another resolution set" }
        }
        val active = manifest.getValue("activeCategories").jsonArray.map { it.jsonPrimitive.content }
        require(active.containsAll(CategoryRegistry.core) && active.all { it in CategoryRegistry.all } && active.distinct().size == active.size) { "Invalid active categories" }
        require(manifest.getValue("taxonomy") == CategoryRegistry.definition) { "Snapshot taxonomy differs from the bundled definitions" }
        connection.createStatement().use { s ->
            s.executeQuery("SELECT COUNT(*) FROM resolutions").use { r -> require(r.next() && r.getInt(1) == research.getValue("candidates").jsonPrimitive.int) { "Resolution coverage mismatch" } }
            s.executeQuery("SELECT COUNT(*) FROM resolutions WHERE status NOT IN ('adopted','excluded_confirmed','not_distributed')").use { r -> require(r.next() && r.getInt(1) == 0) { "Non-terminal research result" } }
            s.executeQuery("SELECT COUNT(*) FROM (SELECT source,line FROM source_map GROUP BY source,line)").use { r -> require(r.next() && r.getInt(1) == research.getValue("sourceRows").jsonPrimitive.int) { "Original row coverage mismatch" } }
            s.executeQuery("SELECT COUNT(*) FROM source_map m LEFT JOIN resolutions r ON r.id=m.candidate_id WHERE r.id IS NULL").use { r -> require(r.next() && r.getInt(1) == 0) { "Orphaned input mapping" } }
            s.executeQuery("SELECT COUNT(*) FROM resolutions r LEFT JOIN source_map m ON r.id=m.candidate_id WHERE m.candidate_id IS NULL").use { r -> require(r.next() && r.getInt(1)==0) { "Resolution has no original input" } }
            s.executeQuery("SELECT status,COUNT(*) FROM resolutions GROUP BY status").use { r ->
                val expected=mapOf("adopted" to "adopted","excluded_confirmed" to "excludedConfirmed","not_distributed" to "notDistributed")
                while(r.next()) require(r.getInt(2)==research.getValue(expected.getValue(r.getString(1))).jsonPrimitive.int) { "Decision totals differ from manifest" }
            }
            val hash=MessageDigest.getInstance("SHA-256")
            s.executeQuery("SELECT * FROM resolutions ORDER BY id").use { r ->
                while(r.next()) {
                    val values=(1..13).map { i -> if(i in 4..6) JsonPrimitive(r.getInt(i)) else JsonPrimitive(r.getString(i)) }
                    hash.update(JsonArray(values).toString().toByteArray(Charsets.UTF_8));hash.update(10.toByte())
                }
            }
            require(hash.digest().joinToString("") { "%02x".format(it) }==research.getValue("resolutionSha256").jsonPrimitive.content) { "Resolution checksum mismatch" }
            s.executeQuery("SELECT COUNT(*) FROM resolutions r WHERE status='adopted' AND (categories='' OR json_array_length(reading_ids)=0 OR json_array_length(roles)=0)").use { r -> require(r.next() && r.getInt(1) == 0) { "Adoption without reading/meaning proof" } }
            s.executeQuery("SELECT COUNT(*) FROM resolutions r,json_each(r.reading_ids) j LEFT JOIN reading_facts f ON f.id=j.value WHERE r.status='adopted' AND (f.id IS NULL OR (f.url NOT LIKE 'https://%' AND f.url NOT LIKE 'http://%') OR length(f.sha256)!=64)").use { r -> require(r.next() && r.getInt(1) == 0) { "Reading proof does not bind to adopted pair" } }
            s.executeQuery("SELECT r.reading,r.surface,f.reading,f.surface FROM resolutions r,json_each(r.reading_ids) j JOIN reading_facts f ON f.id=j.value WHERE r.status='adopted'").use { rows ->
                while (rows.next()) require(JmdictLexicon.pair(rows.getString(1),rows.getString(2)) == JmdictLexicon.pair(rows.getString(3),rows.getString(4))) { "Reading evidence binds another pair" }
            }
            s.executeQuery("SELECT COUNT(*) FROM resolutions r,json_each(r.roles) role,json_each(json_extract(role.value,'$.evidenceIds')) ref LEFT JOIN semantic_facts f ON f.id=ref.value WHERE r.status='adopted' AND (f.id IS NULL OR (f.url NOT LIKE 'https://%' AND f.url NOT LIKE 'http://%') OR length(f.sha256)!=64 OR f.target!=json_extract(role.value,'$.target') OR f.kind NOT IN ('context','meaning'))").use { r -> require(r.next() && r.getInt(1)==0) { "Missing or unrelated category provenance" } }
            for ((column,kind) in listOf("normalization_ids" to "normalization","exclusion_ids" to "invalid")) {
                s.executeQuery("SELECT r.reading,r.surface,f.reading,f.surface,f.kind,f.url,f.sha256,r.id,f.target FROM resolutions r,json_each(r.$column) j LEFT JOIN quality_facts f ON f.id=j.value").use { r ->
                    while(r.next()) require(r.getString(5)==kind && r.getString(8)==r.getString(9) && (r.getString(6)?.startsWith("https://")==true || r.getString(6)?.startsWith("http://")==true) && r.getString(7)?.matches(Regex("[a-f0-9]{64}"))==true && JmdictLexicon.pair(r.getString(1),r.getString(2))==JmdictLexicon.pair(r.getString(3),r.getString(4))) { "Invalid transformation/exclusion provenance" }
                }
            }
            s.executeQuery("SELECT COUNT(*) FROM resolutions WHERE status='excluded_confirmed' AND json_array_length(exclusion_ids)=0").use { r -> require(r.next() && r.getInt(1)==0) { "Confirmed exclusion has no evidence" } }
            val publishedMethods = mutableMapOf<String, Int>()
            s.executeQuery("SELECT categories,roles FROM resolutions WHERE status='adopted'").use { r ->
                while (r.next()) {
                    val cats = r.getString(1).split(',')
                    val roles = Json.parseToJsonElement(r.getString(2)).jsonArray.map { it.jsonObject }
                    for (role in roles) {
                        val method = role["method"]?.jsonPrimitive?.content
                        require(method in methods) { "Invalid exported classification method" }
                        publishedMethods[method!!] = publishedMethods.getOrDefault(method, 0) + 1
                    }
                    require(cats.all { it in active } && cats.distinct().size == cats.size && roles.isNotEmpty()) { "Invalid publication category" }
                    require(cats.all { c -> roles.any { role -> role.getValue("category").jsonPrimitive.content == c && role.getValue("target").jsonPrimitive.content.isNotBlank() && role.getValue("evidenceIds").jsonArray.isNotEmpty() } }) { "Role has no target/sense evidence" }
                }
            }
            require(publishedMethods.all { (method, count) -> count <= populations.getValue(method) }) { "Published classification route has no validated population" }
            val counts=mutableMapOf<String,Int>()
            s.executeQuery("SELECT categories FROM resolutions WHERE status='adopted'").use { r -> while(r.next()) r.getString(1).split(',').forEach { counts[it]=counts.getOrDefault(it,0)+1 } }
            CategoryRegistry.definition.getValue("categories").jsonArray.map { it.jsonObject }.filter { it.getValue("id").jsonPrimitive.content in active }.forEach { category ->
                val name=category.getValue("id").jsonPrimitive.content
                require((counts[name] ?: 0)>=maxOf(1,category.getValue("minimum").jsonPrimitive.int)) { "Publication floor not met: $name" }
            }
        }
        verifyProofDependencies(connection)
    }
}
