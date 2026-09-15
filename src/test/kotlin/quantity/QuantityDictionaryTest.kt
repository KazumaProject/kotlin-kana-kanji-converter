package com.kazumaproject.quantity

import java.io.File
import kotlin.test.*

class QuantityDictionaryTest {
    private val dictionary = QuantitySource.parse(File("src/main/quantity"))
    @Test fun roundTripAndChecksum() {
        assertContentEquals(dictionary.write(), QuantityDictionary.read(dictionary.write()).write())
        val broken = dictionary.write(); broken[broken.lastIndex] = (broken.last().toInt() xor 1).toByte()
        assertFailsWith<IllegalArgumentException> { QuantityDictionary.read(broken) }
        assertFailsWith<IllegalArgumentException> { QuantityDictionary.read(dictionary.write() + 0) }
    }
    @Test fun splitAndJoinedQuantitiesMatchTheSameRule() {
        val verify = { reading: String, text: String, unit: String ->
            reading == "ろっけん" && text in setOf("6軒", "６軒", "六軒") && unit == "軒"
        }
        val prefix = listOf(QuantityDictionary.Token("家", "いえ"), QuantityDictionary.Token("が", "が"))
        for (text in listOf("6軒", "６軒", "六軒")) {
            assertTrue(dictionary.matches(prefix + QuantityDictionary.Token(text, "ろっけん"), verify))
            assertTrue(dictionary.matches(prefix + listOf(QuantityDictionary.Token(text.dropLast(1), "ろっ"), QuantityDictionary.Token("軒", "けん")), verify))
        }
        assertFalse(dictionary.matches(prefix + QuantityDictionary.Token("6件", "ろっけん"), verify))
        assertFalse(dictionary.matches(prefix + QuantityDictionary.Token("6軒", "ろっけん", true), verify))
    }
    @Test fun ordinaryWordsDoNotBecomeQuantities() {
        assertFalse(dictionary.matches(listOf(QuantityDictionary.Token("日本語", "にほんご"))) { _, _, _ -> false })
        assertTrue(dictionary.rules.all { rule -> rule.any { it is QuantityDictionary.Feature.Quantity } })
    }
}
