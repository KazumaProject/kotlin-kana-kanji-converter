package com.kazumaproject.quantity

import com.kazumaproject.engine.KanaKanjiEngine
import java.io.File
import kotlin.test.*

/** Reads the newly built dictionary, not hand-written lattice nodes. */
class QuantityLexicalIntegrationTest {
    @Test fun generatedDictionaryKeepsCounterPathsAndOrdinaryWords() {
        val engine = KanaKanjiEngine().apply { buildEngine() }
        val dictionary = QuantityDictionary.read(File("src/main/resources/quantity/quantity.dat").readBytes())
        for ((input, expected) in mapOf("さんぼんだけ" to "3本だけ", "ふたりぶん" to "2人分", "さんねん" to "3年")) {
            assertTrue(expected in engine.nBestPath(input, 64), "$input -> $expected")
        }
        for (input in listOf("にほんご", "しんぶん", "よんで", "さんご", "かんまつ")) {
            val tokens = engine.convert(input).bestPath.map { QuantityDictionary.Token(it.value, it.key) }
            assertEquals(0, dictionary.matchStrength(tokens) { _, _, _, _, _ -> false }, input)
        }
        // Actual tokenizer boundaries must be accepted by a semantic span rule.
        val tokens = engine.convert("さんぼんだけ").bestPath.map { QuantityDictionary.Token(it.value, it.key) }
        assertTrue(dictionary.matches(tokens) { reading, text, unit ->
            reading == "さんぼん" && text in setOf("3本", "３本", "三本") && unit == "本"
        }, tokens.toString())
    }
}
