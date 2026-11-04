import dictionary.Dictionary
import grammar.FormKey
import grammar.Lexicon
import louds.LOUDS
import louds.louds_with_term_id.LOUDSWithTermId
import succinctBitVector.SuccinctBitVector
import tokenArray.TokenArray
import java.io.File
import java.io.ObjectInputStream
import java.nio.file.Files
import java.util.BitSet
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class ReviewedDictionaryBuilderTest {
    @Test
    fun readsAllSourceRowsAndRequiresOneDecisionPerRow() {
        val inventory = englishInventory(File("data/1-grams_score_cost_pos_combined_with_ner.zip"))
        assertEquals(102051, inventory.size)
        assertEquals(SourceRow("tsv:2", "a", "a", 700), inventory.first())
        val temporary = Files.createTempDirectory("review-ledger").toFile()
        try {
            val decisions = temporary.resolve("decisions.tsv")
            decisions.writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                "tsv:2\ta\ta\t700\tinclude\tword-a\tverified\thttps://en.wiktionary.org/wiki/a#English\n")
            val forms = setOf(FormKey("word-a", "a"))
            assertEquals(listOf(Dictionary("a", 700, "a", false)), selectReviewedRows(inventory.take(1), decisions, forms))
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(inventory.take(2), decisions, forms) }
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(inventory.take(1), decisions, emptySet()) }
            decisions.appendText(decisions.readLines().last() + "\n")
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(inventory.take(1), decisions, forms) }
        } finally {
            temporary.deleteRecursively()
        }
        val lexicon = Lexicon.load(File("data/grammar"))
        validateRelations(File("data/grammar/relations.tsv"), lexicon.forms.map { it.key.surface }.toSet())
    }

    @Test
    fun groupsSurfacesAndRetainsTheFinalDelimiterInTheCompactRepresentation() {
        val temporary = Files.createTempDirectory("review-assets").toFile()
        try {
            val base = listOf(
                Dictionary("a", 700, "a", false),
                Dictionary("i", 700, "I", true),
                Dictionary("i", 1700, "i", false),
                Dictionary("dont", 900, "don't", true),
                Dictionary("dont", 9900, "don't", true),
            )
            val filler = ('a'..'z').map { Dictionary("fixture$it", 1000, "fixture$it", false) } +
                listOf(Dictionary("zzz", 1, "zzz", false), Dictionary("longlast", 2, "longlast", false),
                    Dictionary("longlast", 3, "LongLast", true))
            writeReviewedPayloads(base + filler, temporary)
            fun read(name: String) = ObjectInputStream(temporary.resolve(name).inputStream())
            val reading = read("reading.dat").use { LOUDSWithTermId().readExternalNotCompress(it) }
            val words = read("word.dat").use { LOUDS().readExternalNotCompress(it) }
            val tokens = TokenArray().also { array -> read("token.dat").use { array.readExternal(it) } }
            val compactBits = BitSet.valueOf(tokens.bitvector.toLongArray())
            val compactTokenIndex = SuccinctBitVector(compactBits)
            val readingIndex = SuccinctBitVector(reading.LBS)
            val leafIndex = SuccinctBitVector(reading.isLeaf)
            val wordIndex = SuccinctBitVector(words.LBS)
            fun candidates(input: String): List<Pair<String, Int>> {
                val term = reading.getTermId(reading.getNodeIndex(input, readingIndex), leafIndex)
                return tokens.getListDictionaryByYomiTermId(term, compactTokenIndex).map {
                    (if (it.nodeId == -1) input else words.getLetter(it.nodeId, wordIndex)) to it.wordCost.toInt()
                }
            }
            assertEquals(listOf("a" to 700), candidates("a"))
            assertEquals(listOf("I" to 700, "i" to 1700), candidates("i"))
            assertEquals(listOf("don't" to 900), candidates("dont"))
            assertEquals(listOf("longlast" to 2, "LongLast" to 3), candidates("longlast"))
            assertEquals(66, compactBits.length())
            assertTrue(!temporary.resolve("qwerty_glide_index.dat").readBytes().toString(Charsets.ISO_8859_1).contains("keyboard"))
        } finally {
            temporary.deleteRecursively()
        }
    }
}
