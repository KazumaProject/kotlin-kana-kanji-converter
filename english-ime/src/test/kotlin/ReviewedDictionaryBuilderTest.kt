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
    fun spacedInputAliasRequiresTheUnchangedOriginalManualMapping() {
        val temporary = Files.createTempDirectory("literal-phrase-alias").toFile()
        try {
            val relations = temporary.resolve("relations.tsv").apply {
                writeText("relation\tsource\ttarget\tevidence\ninput_alias\texample three sixty five\tExample 365\thttps://example.org/manual\n")
            }
            val row = SourceRow("manual:1", "example three sixty five", "Example 365", 9000)
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("Example 365")) }
            validateRelations(relations, setOf("Example 365"), listOf(row))
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("Example 365"), listOf(row.copy(id = "tsv:1"))) }
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("Example 365"), listOf(row.copy(reading = "different input"))) }
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("Example 365"), listOf(row.copy(surface = "Different product"))) }
        } finally { temporary.deleteRecursively() }
    }

    @Test
    fun retainsVerifiedLiteralAndNamedReadingsAtTheOriginalCost() {
        val temporary = Files.createTempDirectory("literal-and-name").toFile()
        try {
            val rows = listOf(SourceRow("raw:1", "may", "may", 700))
            val forms = setOf(FormKey("modal", "may"), FormKey("name", "May"))
            val decisions = temporary.resolve("decisions.tsv").apply {
                writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                    "raw:1\tmay\tmay\t700\tinclude\tmodal,name\tverified\thttps://example.org/fixture\n")
            }
            val header = "id\tsource\ttarget\trelation\tevidence\n"
            val literal = "raw:1\tmay\tmay\tcase_candidates\thttps://example.org/word\n"
            val corrections = temporary.resolve("corrections.tsv")
            corrections.writeText(header + literal + "raw:1\tmay\tMay\tcase_candidates\thttps://example.org/name\n")
            assertEquals(listOf(Dictionary("may", 700, "May", true), Dictionary("may", 700, "may", false)),
                selectReviewedRows(rows, decisions, forms, corrections))
            corrections.writeText(header + literal)
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms, corrections) }
            corrections.writeText(header + literal.replace("case_candidates", "case_correction"))
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms, corrections) }
        } finally { temporary.deleteRecursively() }
    }

    @Test
    fun spellingCorrectionsRetainVerifiedAlternativesWithoutChangingRawRowsOrCosts() {
        val temporary = Files.createTempDirectory("punctuation-correction").toFile()
        try {
            val rows = listOf(SourceRow("raw:1", "callin", "callin", 700))
            val decisions = temporary.resolve("decisions.tsv").apply {
                writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                    "raw:1\tcallin\tcallin\t700\tinclude\tn-call,v-call\tverified\thttps://example.org/fixture\n")
            }
            val corrections = temporary.resolve("corrections.tsv")
            val header = "id\tsource\ttarget\trelation\tevidence\n"
            corrections.writeText(header + "raw:1\tcallin\tcall-in\tinput_spelling_candidates\thttps://example.org/fixture\n" +
                "raw:1\tcallin\tcallin'\tinput_spelling_candidates\thttps://example.org/fixture\n")
            val forms = setOf(FormKey("n-call", "call-in"), FormKey("v-call", "callin'"))
            val selected = selectReviewedRows(rows, decisions, forms, corrections)
            assertEquals(setOf("call-in", "callin'"), selected.map { it.word }.toSet())
            assertTrue(selected.all { it.reading == "callin" && it.cost.toInt() == 700 })
            assertEquals("callin", rows.single().surface)
            corrections.writeText(header + "raw:1\tcallin\tcalling\tinput_spelling_correction\thttps://example.org/fixture\n")
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms + FormKey("wrong", "calling"), corrections) }
        } finally { temporary.deleteRecursively() }
    }

    @Test
    fun retainsMappedSpacesAcrossAllSurfaceRendererOverloads() {
        val temporary = Files.createTempDirectory("mapped-spaces").toFile()
        try {
            val decisions = temporary.resolve("decisions.tsv")
            decisions.writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                "manual:1\tgoogledocs\tGoogle Docs\t700\tinclude\tgoogle-docs\tverified\thttps://en.wiktionary.org/wiki/Google_Docs\n")
            val accepted = selectReviewedRows(listOf(SourceRow("manual:1", "googledocs", "Google Docs", 700)),
                decisions, setOf(FormKey("google-docs", "Google Docs")))
            writeReviewedPayloads(accepted, temporary)
            val words = ObjectInputStream(temporary.resolve("word.dat").inputStream()).use { LOUDS().readExternalNotCompress(it) }
            val node = words.getNodeIndex("Google Docs")
            val bits = SuccinctBitVector(words.LBS)
            assertEquals("Google Docs", words.getLetter(node, bits))
            assertEquals("Google Docs", words.getLetter(node, words.LBS.rank0GetIntArray(), words.LBS.rank1GetIntArray()))
            assertEquals("Google Docs", words.getLetterShortArray(node, bits))
            assertEquals("Google Docs", words.getLetterShortArray(node, words.LBS.rank0GetShortArray(), words.LBS.rank1GetShortArray()))
        } finally {
            temporary.deleteRecursively()
        }
    }
    @Test
    fun emitsAllVerifiedCaseCandidatesWithoutChoosingAnIntendedName() {
        val temporary = Files.createTempDirectory("case-candidates").toFile()
        try {
            val decisions = temporary.resolve("decisions.tsv")
            decisions.writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                "tsv:2\ttim\ttim\t700\tinclude\tname-tim,abbr-tim\tverified\thttps://en.wiktionary.org/wiki/Tim\n")
            val corrections = temporary.resolve("corrections.tsv")
            val header = "id\tsource\ttarget\trelation\tevidence\n"
            corrections.writeText(header + "tsv:2\ttim\tTim\tcase_candidates\thttps://en.wiktionary.org/wiki/Tim\n" +
                "tsv:2\ttim\tTIM\tcase_candidates\thttps://en.wiktionary.org/wiki/TIM\n")
            val rows = listOf(SourceRow("tsv:2", "tim", "tim", 700))
            val forms = setOf(FormKey("name-tim", "Tim"), FormKey("abbr-tim", "TIM"))
            assertEquals(listOf(Dictionary("tim", 700, "TIM", true), Dictionary("tim", 700, "Tim", true)),
                selectReviewedRows(rows, decisions, forms, corrections))
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms - FormKey("abbr-tim", "TIM"), corrections) }
            corrections.writeText(header + "tsv:2\ttim\tTim\tcase_candidates\thttps://en.wiktionary.org/wiki/Tim\n")
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms, corrections) }
        } finally {
            temporary.deleteRecursively()
        }
    }
    @Test
    fun appliesOnlyExplicitCaseCorrectionsAndPreservesSourceLedger() {
        val temporary = Files.createTempDirectory("case-correction").toFile()
        try {
            val decisions = temporary.resolve("decisions.tsv")
            decisions.writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                "tsv:2\tlondon\tlondon\t700\tinclude\tplace-london\tverified\thttps://en.wiktionary.org/wiki/London\n")
            val corrections = temporary.resolve("corrections.tsv")
            val header = "id\tsource\ttarget\trelation\tevidence\n"
            corrections.writeText(header + "tsv:2\tlondon\tLondon\tcase_correction\thttps://en.wiktionary.org/wiki/London\n")
            val rows = listOf(SourceRow("tsv:2", "london", "london", 700))
            val forms = setOf(FormKey("place-london", "London"))
            assertEquals(listOf(Dictionary("london", 700, "London", true)),
                selectReviewedRows(rows, decisions, forms, corrections))
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms) }
            corrections.writeText(header + "tsv:2\tlondon\tParis\tcase_correction\thttps://example.org/\n")
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms, corrections) }
            corrections.writeText(header + "tsv:2\tlondon\tLondon\tcase_correction\thttps://example.org/\n" +
                "tsv:2\tlondon\tLondon\tcase_correction\thttps://example.org/\n")
            assertFailsWith<IllegalArgumentException> { selectReviewedRows(rows, decisions, forms, corrections) }
        } finally {
            temporary.deleteRecursively()
        }
    }

    @Test
    fun validatesInputSpellingsWithoutTreatingArbitraryAliasesAsNormalization() {
        val temporary = Files.createTempDirectory("input-spelling").toFile()
        try {
            val relations = temporary.resolve("relations.tsv")
            val header = "relation\tsource\ttarget\tevidence\n"
            relations.writeText(header + "input_spelling\twifi\tWi-Fi\thttps://en.wiktionary.org/wiki/Wi-Fi\n")
            validateRelations(relations, setOf("Wi-Fi"))
            relations.writeText(header + "input_spelling\tcicd\tCI/CD\thttps://en.wiktionary.org/wiki/CI/CD\n")
            validateRelations(relations, setOf("CI/CD"))
            relations.writeText(header + "input_alias\tcsharp\tC#\thttps://github.com/github-linguist/linguist\n")
            validateRelations(relations, setOf("C#"))
            relations.writeText(header + "input_alias\tcake script\tC#\thttps://github.com/github-linguist/linguist\n")
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("C#")) }
            relations.writeText(header + "input_spelling\thttpie\thttp\thttps://example.org/\n")
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("httpie", "http")) }
            relations.writeText(header + "capitalization\tdog\tCAT\thttps://example.org/\n")
            assertFailsWith<IllegalArgumentException> { validateRelations(relations, setOf("dog", "CAT")) }
        } finally {
            temporary.deleteRecursively()
        }
    }

    @Test
    fun preservesHyphensAndDotsInCanonicalMappedSurfaces() {
        val temporary = Files.createTempDirectory("canonical-surfaces").toFile()
        try {
            writeReviewedPayloads(listOf(Dictionary("wifi", 800, "Wi-Fi", true),
                Dictionary("usa", 900, "U.S.A.", true), Dictionary("cicd", 1000, "CI/CD", true),
                Dictionary("pokémon", 1100, "Pokémon", true), Dictionary("csharp", 1200, "C#", true)), temporary)
            fun read(name: String) = ObjectInputStream(temporary.resolve(name).inputStream())
            val reading = read("reading.dat").use { LOUDSWithTermId().readExternalNotCompress(it) }
            val words = read("word.dat").use { LOUDS().readExternalNotCompress(it) }
            val tokens = TokenArray().also { array -> read("token.dat").use { array.readExternal(it) } }
            val consumer = engine.EnglishEngine(reading, words, tokens, SuccinctBitVector(reading.LBS),
                SuccinctBitVector(words.LBS), SuccinctBitVector(reading.isLeaf), SuccinctBitVector(tokens.bitvector))
            assertEquals("Wi-Fi", consumer.getPrediction("wifi").single().word)
            assertEquals("U.S.A.", consumer.getPrediction("usa").single().word)
            assertEquals("CI/CD", consumer.getPrediction("cicd").single().word)
            assertEquals("Pokémon", consumer.getPrediction("pokémon").single().word)
            assertEquals("C#", consumer.getPrediction("csharp").single().word)
        } finally {
            temporary.deleteRecursively()
        }
    }

    @Test
    fun rejectsLexicallyClassifiedRowsStillPendingDistributionReview() {
        val temporary = Files.createTempDirectory("pending-review").toFile()
        try {
            val decisions = temporary.resolve("decisions.tsv")
            decisions.writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                "tsv:2\tmake\tmake\t700\tpending\tword-make\tsense_review_required\thttps://wordnet.princeton.edu/\n")
            val failure = assertFailsWith<IllegalArgumentException> {
                selectReviewedRows(listOf(SourceRow("tsv:2", "make", "make", 700)), decisions,
                    setOf(FormKey("word-make", "make")))
            }
            assertTrue(failure.message.orEmpty().contains("1 pending decisions"))
        } finally {
            temporary.deleteRecursively()
        }
    }

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
