package com.kazumaproject.quality

import com.kazumaproject.dictionary.LoadedDictionary
import com.kazumaproject.engine.KanaKanjiEngine
import kotlinx.serialization.json.*
import java.io.File

/** Frozen, evidence-backed probes, separate from counts and post-build review sampling. */
object DictionaryEvaluation {
    fun evaluate(dictionaries: List<LoadedDictionary>, engine: KanaKanjiEngine, words: File, sentences: File, output: File, baseline: File? = null, enforce: Boolean = false, lock: File? = null): JsonObject {
        fun rows(file: File): List<Map<String,String>> {
            val lines=file.readLines(); val columns=lines.first().split('\t')
            return lines.drop(1).filter { it.isNotBlank() }.map { columns.zip(it.split('\t')).toMap() }
        }
        if (lock != null) {
            val spec=Json.parseToJsonElement(lock.readText()).jsonObject
            require(spec.getValue("wordsSha256").jsonPrimitive.content==sha256(words) && spec.getValue("sentencesSha256").jsonPrimitive.content==sha256(sentences)) { "Evaluation probe checksum mismatch" }
            if (baseline != null) require(baseline.isFile && spec.getValue("baselineSha256").jsonPrimitive.content==sha256(baseline)) { "Evaluation baseline checksum mismatch" }
        }
        val probes=rows(words); val contexts=rows(sentences)
        require(probes.size==600 && probes.groupingBy { it.getValue("category") }.eachCount()==publishedCategories.associateWith { 50 }) { "Expected 50 probes for each of 12 categories" }
        require(contexts.size==200) { "Expected 200 sentence probes" }
        val matches=probes.map { row -> buildJsonObject {
            row.forEach { (k,v)->put(k,v) }
            put("matched",dictionaries.single { it.id==row.getValue("category") }.lookup(row.getValue("reading")).any { it.surface==row.getValue("surface") })
        } }
        if(baseline!=null) require(baseline.isFile) { "Missing evaluation baseline: $baseline" }
        val baselineResult=baseline?.let { Json.parseToJsonElement(it.readText()).jsonObject }
        if(baselineResult!=null) require(baselineResult.getValue("summary").jsonObject.getValue("wordsSha256").jsonPrimitive.content==sha256(words) && baselineResult.getValue("summary").jsonObject.getValue("sentencesSha256").jsonPrimitive.content==sha256(sentences)) { "Frozen baseline/probe hashes differ" }
        val previous=baseline?.takeIf { it.isFile }?.let { Json.parseToJsonElement(it.readText()).jsonObject.getValue("sentences").jsonArray.associate { r->r.jsonObject.getValue("id").jsonPrimitive.content to r.jsonObject } }.orEmpty()
        var regressions=0; var bestRegressions=0; var top10Regressions=0
        val conversion=contexts.map { row ->
            val input=row.getValue("input");val expected=row.getValue("expected")
            val best=engine.convert(input).value;val nbest=engine.nBestPath(input,10)
            val old=previous[row.getValue("id")]; val top10Regression=(old?.get("top10Matched")?.jsonPrimitive?.boolean==true && expected !in nbest)
            val bestRegression=(old?.get("bestMatched")?.jsonPrimitive?.boolean==true && best!=expected)
            val regression=top10Regression || bestRegression
            if(top10Regression) top10Regressions++
            if(bestRegression) bestRegressions++
            if(regression) regressions++
            buildJsonObject { row.forEach { (k,v)->put(k,v) };put("best",best);put("bestMatched",best==expected);put("top10Matched",expected in nbest);put("regression",regression);put("bestRegression",bestRegression);put("top10Regression",top10Regression);put("top10",buildJsonArray { nbest.forEach { add(it) } }) }
        }
        val wordPass=matches.count { it.getValue("matched").jsonPrimitive.boolean }
        val sentencePass=conversion.count { it.getValue("top10Matched").jsonPrimitive.boolean }
        val counts=dictionaries.filter { it.id in publishedCategories }.associate { d->d.id to d.readings().sumOf { d.lookup(it).size } }
        val minimum=mapOf("general" to 10000,"technical" to 1500,"food" to 250,"product" to 200)
        val countPass=minimum.all { (id,min)->counts.getValue(id)>=min }
        val summary=buildJsonObject {
            put("wordCases",probes.size);put("wordMatches",wordPass);put("wordCoverage",wordPass.toDouble()/probes.size)
            put("sentenceCases",contexts.size);put("sentenceTop10Matches",sentencePass);put("sentenceBestMatches",conversion.count { it.getValue("bestMatched").jsonPrimitive.boolean });put("sentenceRegressions",regressions);put("sentenceBestRegressions",bestRegressions);put("sentenceTop10Regressions",top10Regressions)
            put("categoryCounts",buildJsonObject { counts.forEach { (k,v)->put(k,v) } });put("countGatePassed",countPass)
            put("passed",wordPass>=570 && regressions==0 && countPass)
            put("wordsSha256",sha256(words));put("sentencesSha256",sha256(sentences))
        }
        val result=buildJsonObject { put("summary",summary);put("words",JsonArray(matches));put("sentences",JsonArray(conversion)) }
        output.absoluteFile.parentFile.mkdirs();output.writeText(Json { prettyPrint=true }.encodeToString(JsonObject.serializer(),result)+"\n")
        if(enforce) require(summary.getValue("passed").jsonPrimitive.boolean) { "Dictionary practical evaluation failed; see $output" }
        return summary
    }
}
