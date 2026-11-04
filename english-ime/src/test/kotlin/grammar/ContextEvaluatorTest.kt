package grammar

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ContextEvaluatorTest {
    private val lexicon = Lexicon.load(File("data/grammar"))
    private val evaluator = ContextEvaluator(lexicon)

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
