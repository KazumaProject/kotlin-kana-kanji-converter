package conversion

import grammar.readTsv
import supplementReadings
import java.io.File

/** End-to-end audit of both generated binaries using the same reader as the CLI. */
fun main(args: Array<String>) {
    require(args.size == 3) { "Expected base assets, extended assets and the reviewed supplement TSV" }
    val base = ReviewedDictionary.load(File(args[0]))
    val extended = ReviewedDictionary.load(File(args[1]))
    fun entries(dictionary: ReviewedDictionary) = buildMap {
        for ((reading, surface, cost) in dictionary.allCandidates()) {
            check(put(reading to surface, cost) == null) { "Repeated binary candidate for $reading/$surface" }
        }
    }

    val before = entries(base)
    val after = entries(extended)
    for ((pair, cost) in before) {
        check(after[pair] == cost) { "Changed or missing original reading/surface pair: $pair" }
    }
    val forms = File(args[2]).readTsv("lexeme_id", "lemma", "surface", "categories", "domain", "evidence", "source_ref")
    val expected = forms.flatMap { (_, _, surface) -> supplementReadings(surface).map { it to surface } }.toSet()
    check(after.keys - before.keys == expected) { "Supplement binary pairs differ from the reviewed ledger" }
    for ((id, lemma, surface, categories) in forms) {
        val form = extended.lexicon.lookup(surface).single { it.key.lexemeId == id && it.key.surface == surface }
        check(form.lemma == lemma && form.dictionaries.containsAll(categories.split(','))) {
            "Supplement lexical form or categories differ for $id/$surface"
        }
    }
    println("Verified original pairs=" + before.size + ", new pairs=" + expected.size + ", reviewed forms=" + forms.size)
}
