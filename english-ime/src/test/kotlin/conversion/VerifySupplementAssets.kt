package conversion

import grammar.Lexicon
import grammar.lookupKey
import grammar.readTsv
import supplementReadings
import java.io.File

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
    val runtime = args.getOrNull(3)?.let { ReviewedDictionary.load(File(it)) }
    runtime?.let { check(entries(it) == after) { "Runtime binary candidates differ from the full bundle" } }
    for ((pair, cost) in before) {
        check(after[pair] == cost) { "Changed or missing original reading/surface pair: $pair" }
    }
    val forms = File(args[2]).readTsv("lexeme_id", "lemma", "surface", "categories", "domain", "evidence", "source_ref")
    val expected = forms.flatMap { (_, _, surface) -> supplementReadings(surface).map { it to surface } }.toSet() - before.keys
    check(after.keys - before.keys == expected) { "Supplement binary pairs differ from the reviewed ledger" }
    val lexicon = Lexicon.load(File(args[1], "grammar"))
    for ((id, lemma, surface, categories) in forms) {
        val form = lexicon.lookup(surface).single { it.key.lexemeId == id && it.key.surface == surface }
        val expectedRoles = lexicon.lookup(surface).flatMap { it.dictionaries }.toSet()
        check(extended.grammarRoles.lookup(surface, lookupKey(surface)) == expectedRoles) {
            "Supplement compact roles differ for $surface"
        }
        check(form.lemma == lemma && form.dictionaries.containsAll(categories.split(','))) {
            "Supplement lexical form or categories differ for $id/$surface"
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
    if (runtime != null) println("Verified full/runtime candidate parity and all lexical surface roles")
}
