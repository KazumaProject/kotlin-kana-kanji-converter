package conversion

import grammar.Lexicon
import grammar.lookupKey
import grammar.readTsv
import supplementReadings
import supplementEntryFiles
import distributionRuleKey
import distributionMatches
import distributionKeys
import java.io.File
import categoryFileHash

/** End-to-end audit of both generated binaries using the same reader as the CLI. */
fun main(args: Array<String>) {
    require(args.size in 3..4) { "Expected base assets, extended assets, reviewed supplement TSV and optional runtime assets" }
    val base = ReviewedDictionary.load(File(args[0]))
    val extended = ReviewedDictionary.load(File(args[1]))
    fun entries(dictionary: ReviewedDictionary) = buildMap {
        for ((reading, surface, cost) in dictionary.allCandidates()) {
            check(put(reading to surface, cost) == null) { "Repeated binary candidate for $reading/$surface" }
        }
    }

    val before = entries(base)
    val after = entries(extended)
    val forms = supplementEntryFiles(File(args[2]).parentFile).flatMap {
        it.readTsv("lexeme_id", "lemma", "surface", "categories", "domain", "evidence", "source_ref")
    }
    val parentFormsFile=File(args[0],"grammar/forms.tsv")
    val parentLemmas=mutableMapOf<String,String>()
    val policyFile=File(args[2]).parentFile.resolve("distribution-exclusions.tsv")
    val declared=if(policyFile.isFile) policyFile.readTsv("surface","match","reason","evidence","license")
        .map { distributionRuleKey(it[0],it[1]) }.toSet() else emptySet()
    val blocked=parentFormsFile.useLines { lines ->
        val input=lines.iterator()
        check(input.hasNext() && input.next()=="lexeme_id\tlemma\tsurface\tevidence")
        val identities=mutableSetOf<grammar.FormKey>()
        distributionKeys(declared,input.asSequence().map { line ->
            val row=line.split('\t');check(row.size==4)
            check(identities.add(grammar.FormKey(row[0],row[2]))) { "Duplicate prior lexical identity" }
            check(parentLemmas.putIfAbsent(row[0],row[1]).let { it==null || it==row[1] })
            row[2] to row[1]
        }+forms.asSequence().flatMap { sequenceOf(it[2] to it[1],it[1] to it[1]) })
    }
    check(after.keys.none { distributionMatches(it.second,blocked) }) { "Restricted candidate leaked into distribution" }
    if(policyFile.isFile) check(readReviewedMetadata(File(args[1])).getProperty("distribution.policy.sha256")==categoryFileHash(policyFile))
    val runtime = args.getOrNull(3)?.let { ReviewedDictionary.load(File(it)) }
    runtime?.let { check(entries(it) == after) { "Runtime binary candidates differ from the full bundle" } }
    for ((pair, cost) in before) {
        if(!distributionMatches(pair.second,blocked)) check(after[pair] == cost) { "Changed or missing original reading/surface pair: $pair" }
    }
    val expected = forms.filter { !distributionMatches(it[2],blocked) }.flatMap { (_, _, surface) -> supplementReadings(surface).map { it to surface } }.toSet() - before.keys
    check(after.keys - before.keys == expected) { "Supplement binary pairs differ from the reviewed ledger" }
    val lexicon = Lexicon.load(File(args[1], "grammar"))
    val metadataFile = File(args[2]).parentFile.resolve("metadata.tsv")
    val metadata = if (metadataFile.isFile) metadataFile.readTsv(
        "lexeme_id", "lemma", "surface", "categories", "domain", "evidence", "source_ref") else emptyList()
    for ((id, lemma, surface, categories) in forms + metadata) {
        if(distributionMatches(surface,blocked) || distributionMatches(lemma,declared)) continue
        val form = lexicon.lookup(surface).single { it.key.lexemeId == id && it.key.surface == surface }
        val expectedRoles = lexicon.lookup(surface).flatMap { it.dictionaries }.toSet()
        check(extended.grammarRoles.lookup(surface, lookupKey(surface)) == expectedRoles) {
            "Supplement compact roles differ for $surface"
        }
        check(form.lemma == lemma && form.dictionaries.containsAll(categories.split(','))) {
            "Supplement lexical form or categories differ for $id/$surface"
        }
    }
    val afterForms = lexicon.forms.associateBy { it.key }
    check(lexicon.forms.none { distributionMatches(it.key.surface,blocked) || distributionMatches(it.lemma,declared) }) { "Restricted grammar form leaked" }
    streamTable(parentFormsFile,"lexeme_id\tlemma\tsurface\tevidence",4) { row ->
        if(!distributionMatches(row[2],blocked) && !distributionMatches(row[1],declared)) {
            val key=grammar.FormKey(row[0],row[2])
            check(checkNotNull(afterForms[key]) { "Missing prior lexical analysis $key" }.lemma==row[1])
        }
    }
    streamTable(File(args[0],"grammar/memberships.tsv"),"category\tlexeme_id\tsurface",3) { row ->
        val lemma=checkNotNull(parentLemmas[row[1]])
        if(!distributionMatches(row[2],blocked) && !distributionMatches(lemma,declared))
            check(row[0] in checkNotNull(afterForms[grammar.FormKey(row[1],row[2])]).dictionaries) {
                "Removed prior lexical membership ${row[1]}/${row[2]}/${row[0]}"
            }
    }
    runtime?.let {
        for (surface in lexicon.forms.map { form -> form.key.surface }.toSet()) {
            val normalized = lookupKey(surface)
            check(it.grammarRoles.lookup(surface, normalized) == extended.grammarRoles.lookup(surface, normalized)) {
                "Runtime grammar roles differ for $surface"
            }
        }
    }
    println("Verified original pairs=" + before.size + ", new pairs=" + expected.size + ", reviewed forms=" + forms.size)
    if(blocked.isNotEmpty()) println("Explicitly excluded parent pairs="+before.keys.count { distributionMatches(it.second,blocked) })
    if (runtime != null) println("Verified full/runtime candidate parity and all lexical surface roles")
}

private fun streamTable(file: File, header: String, columns: Int, consume: (List<String>) -> Unit) {
    file.bufferedReader().use { input ->
        check(input.readLine()==header)
        input.lineSequence().forEach { line ->
            val row=line.split('\t');check(row.size==columns);consume(row)
        }
    }
}
