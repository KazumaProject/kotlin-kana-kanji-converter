package com.kazumaproject.quality

import java.io.File
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream
import kotlinx.serialization.json.*

/** Accounts for every unpublished baseline entry, including explicit normalization exclusions. */
object DictionaryComparison {
    private data class Key(val reading: String, val surface: String, val left: String, val right: String)
    private data class Decision(val state: String, val categories: String, val reason: String, val evidence: String)
    fun compare(before: File, after: File, output: File): JsonObject {
        fun rows(file: File, visit: (Map<String,String>) -> Unit) {
            val stream=if(file.name.endsWith(".gz")) GZIPInputStream(file.inputStream()) else file.inputStream()
            stream.bufferedReader().use { r -> val columns=r.readLine().split('\t'); r.lineSequence().forEach { visit(columns.zip(it.split('\t')).toMap()) } }
        }
        fun key(r: Map<String,String>)=Key(r.getValue("reading"),r.getValue("surface"),r.getValue("left_id"),r.getValue("right_id"))
        fun decision(r: Map<String,String>): Decision {
            val categories=r.getValue("categories")
            val state=when { r["quality_status"]=="excluded" -> "excluded"; r["quality_status"]!="accepted" -> "held"; categories=="unclassified" -> "unclassified"; else -> "adopted" }
            return Decision(state,categories,r.getValue("reason"),r["reading_evidence"].orEmpty())
        }
        val pending=linkedMapOf<Key,Decision>()
        rows(before) { r -> if(r["phase"]=="classification") { val d=decision(r); if(d.state!="adopted") require(pending.put(key(r),d)==null) { "Duplicate baseline key" } } }
        val current=HashMap<Key,Decision>()
        rows(after) { r -> if(r["phase"]=="classification" || r["quality_status"]=="excluded") { val k=key(r); if(k in pending) current[k]=decision(r) } }
        output.mkdirs();val counts=sortedMapOf<String,Int>();var missing=0
        GZIPOutputStream(File(output,"reassessment.tsv.gz").outputStream()).bufferedWriter().use { writer ->
            writer.appendLine("reading\tsurface\tleft_id\tright_id\tbefore_status\tafter_status\tcategories\treason\treading_evidence")
            pending.forEach { (k,old) ->
                val now=current[k] ?: Decision("unresolved","","missing-current-record","").also { missing++ }
                counts[now.state]=counts.getOrDefault(now.state,0)+1
                writer.appendLine(listOf(k.reading,k.surface,k.left,k.right,old.state,now.state,now.categories,now.reason,now.evidence).joinToString("\t"))
            }
        }
        val summary=buildJsonObject { put("baselineUnpublished",pending.size);put("accounted",pending.size-missing);put("missing",missing);put("beforeSha256",sha256(before));put("afterSha256",sha256(after));put("states",buildJsonObject { counts.forEach { (k,v)->put(k,v) } });put("reassessmentSha256",sha256(File(output,"reassessment.tsv.gz"))) }
        File(output,"comparison.json").writeText(Json { prettyPrint=true }.encodeToString(JsonObject.serializer(),summary)+"\n")
        require(missing==0) { "Unaccounted baseline entries: $missing; see $output" }
        return summary
    }
}
