package grammar

import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ContextEvaluatorTest {
    private val lexicon = Lexicon.load(File("data/grammar"))
    private val evaluator = ContextEvaluator(lexicon)

    @Test
    fun exactProperNameDoesNotHideSentenceInitialPronounOrMergeItsIdentity() {
        val temporary = Files.createTempDirectory("proper-name-pronoun").toFile()
        try {
            for (name in listOf("categories.tsv", "forms.tsv", "memberships.tsv")) {
                File("data/grammar", name).copyTo(temporary.resolve(name))
            }
            temporary.resolve("forms.tsv").appendText("fixture-He\tHe\tHe\thttps://example.org/surname\n")
            temporary.resolve("memberships.tsv").appendText("noun\tfixture-He\tHe\nnoun_proper\tfixture-He\tHe\n")
            val expanded = Lexicon.load(temporary)
            assertEquals(FormKey("fixture-He", "He"), expanded.lookup("He").first().key)
            assertTrue(expanded.lookup("He").any { "pronoun_subject_3sg" in it.dictionaries })
            assertTrue(expanded.lookup("he").none { it.key.lexemeId == "fixture-He" })
            val grammar = ContextEvaluator(expanded)
            assertEquals(1, grammar.evaluate("He <candidate>", listOf("takes")).single().score)
            assertEquals(-1, grammar.evaluate("He <candidate>", listOf("take")).single().score)
            assertEquals(1, grammar.evaluate("He can <candidate>", listOf("take")).single().score)
        } finally { temporary.deleteRecursively() }
    }

    @Test
    fun wordLevelDomainMembershipDoesNotInventOrObscureASyntacticReading() {
        val temporary = Files.createTempDirectory("domain-membership").toFile()
        try {
            for (name in listOf("categories.tsv", "forms.tsv", "memberships.tsv")) {
                File("data/grammar", name).copyTo(temporary.resolve(name))
            }
            temporary.resolve("forms.tsv").appendText("domain-take\ttake\ttake\thttps://example.org/list\n" +
                "domain-unknown\tunknownzz\tunknownzz\thttps://example.org/list\n")
            temporary.resolve("memberships.tsv").appendText("domain_daily\tdomain-take\ttake\n" +
                "domain_daily\tdomain-unknown\tunknownzz\n")
            temporary.resolve("categories.tsv").appendText("identifier_command_line\tCommand identifier without lexical POS\ttake\n")
            temporary.resolve("forms.tsv").appendText("command-take\ttake\ttake\thttps://example.org/command\n")
            temporary.resolve("memberships.tsv").appendText("identifier_command_line\tcommand-take\ttake\n")
            val expanded = ContextEvaluator(Lexicon.load(temporary))
            assertEquals(-1, expanded.evaluate("He <candidate>", listOf("take")).single().score)
            assertEquals(1, expanded.evaluate("He can <candidate>", listOf("take")).single().score)
            assertEquals(0, expanded.evaluate("He <candidate>", listOf("unknownzz")).single().score)
        } finally {
            temporary.deleteRecursively()
        }
    }

    @Test
    fun doesNotSupportABareSingularCountNounAfterBe() {
        val temporary = Files.createTempDirectory("be-complement").toFile()
        try {
            for (name in listOf("categories.tsv", "forms.tsv", "memberships.tsv")) {
                File("data/grammar", name).copyTo(temporary.resolve(name))
            }
            temporary.resolve("forms.tsv").appendText("n-take\ttake\ttake\thttps://en.wiktionary.org/wiki/take\n")
            temporary.resolve("memberships.tsv").appendText("noun\tn-take\ttake\nnoun_count_singular\tn-take\ttake\n")
            val expanded = ContextEvaluator(Lexicon.load(temporary))
            val result = expanded.evaluate("It was <candidate>", listOf("take", "taken"))
            assertEquals(listOf("taken" to 1, "take" to 0), result.map { it.candidate to it.score })
            assertEquals(1, expanded.evaluate("It was a <candidate>", listOf("take")).single().score)
            assertEquals(1, expanded.evaluate("It was <candidate>", listOf("water")).single().score)
        } finally {
            temporary.deleteRecursively()
        }
    }

    @Test
    fun acceptsAPluralNounSubjectThatAlsoHasAVerbReading() {
        val result = evaluator.evaluate("Books <candidate>", listOf("takes", "take"))
        assertEquals(listOf("take" to 1, "takes" to -1), result.map { it.candidate to it.score })
    }

    @Test
    fun keepsTheArticleReadingWhenTheInitialWordAlsoHasAPrepositionReading() {
        val temporary = Files.createTempDirectory("article-reading").toFile()
        try {
            for (name in listOf("categories.tsv", "forms.tsv", "memberships.tsv")) {
                File("data/grammar", name).copyTo(temporary.resolve(name))
            }
            temporary.resolve("memberships.tsv").appendText("preposition\tword-the\tthe\n")
            val expanded = ContextEvaluator(Lexicon.load(temporary))
            val result = expanded.evaluate("The list of items <candidate>", listOf("are", "is"))
            assertEquals(listOf("is" to 1, "are" to -1), result.map { it.candidate to it.score })
        } finally {
            temporary.deleteRecursively()
        }
    }

    @Test
    fun evaluatesAgreementAndAuxiliaryComplements() {
        val examples = listOf(
            Triple("He <candidate>", "takes", "take"),
            Triple("He <candidate>", "is", "are"),
            Triple("He often <candidate>", "takes", "take"),
            Triple("He can <candidate>", "take", "takes"),
            Triple("He does not <candidate>", "take", "takes"),
            Triple("Does he <candidate>?", "take", "takes"),
            Triple("<candidate> he take?", "Does", "Do"),
            Triple("He has <candidate>", "taken", "took"),
            Triple("He <candidate>", "took", "taken"),
            Triple("He and I <candidate>", "take", "takes"),
            Triple("They <candidate>", "are", "is"),
            Triple("I <candidate>", "am", "is"),
            Triple("You <candidate>", "were", "was"),
            Triple("The list of items <candidate>", "is", "are"),
            Triple("She is <candidate>", "taking", "took"),
            Triple("It was <candidate>", "taken", "take"),
            Triple("a <candidate>", "book", "books"),
            Triple("many <candidate>", "books", "book"),
            Triple("much <candidate>", "water", "books"),
        )
        for ((text, good, bad) in examples) {
            val result = evaluator.evaluate(text, listOf(bad, good))
            assertEquals(listOf(good to 1, bad to -1), result.map { it.candidate to it.score }, text)
        }
    }

    @Test
    fun keepsLexemeIdentityAndValidAmbiguity() {
        assertEquals(setOf("v-see", "v-saw", "n-saw"), lexicon.lookup("saw").map { it.key.lexemeId }.toSet())
        assertEquals(setOf("v-book", "n-book"), lexicon.lookup("books").map { it.key.lexemeId }.toSet())
        assertTrue(lexicon.lookup("cut").single().dictionaries.containsAll(
            setOf("verb_base", "verb_past", "verb_past_participle"),
        ))
        assertTrue(lexicon.lookup("sheep").single().dictionaries.containsAll(
            setOf("noun_count_singular", "noun_count_plural"),
        ))
        val result = evaluator.evaluate("He <candidate>", listOf("took", "takes", "xyzzy"))
        assertEquals(listOf("took" to 1, "takes" to 1, "xyzzy" to 0), result.map { it.candidate to it.score })
        assertEquals(0, evaluator.evaluate("He often <candidate>", listOf("tak")).single().score)
        assertEquals(0, evaluator.evaluate("Unknown <candidate>", listOf("take")).single().score)
        assertEquals(0, evaluator.evaluate("I look forward to <candidate>", listOf("seeing")).single().score)
        assertTrue(lexicon.lookup("to").single().dictionaries.containsAll(setOf("preposition", "infinitive_marker")))
    }
}
