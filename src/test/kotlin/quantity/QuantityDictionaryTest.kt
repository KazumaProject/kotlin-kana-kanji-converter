package com.kazumaproject.quantity

import java.io.File
import kotlin.test.*

class QuantityDictionaryTest {
    private val dictionary = QuantitySource.parse(File("src/main/quantity"))
    @Test fun wordClassesExpandIntoLiteralContexts() {
        for (word in listOf("りんご", "卵", "おにぎり")) {
            assertTrue(listOf(QuantityDictionary.Feature.Word(word), QuantityDictionary.Feature.Word("を"),
                QuantityDictionary.Feature.Quantity("個")) in dictionary.rules)
        }
        assertEquals(dictionary.rules.size, dictionary.rules.distinct().size)
    }
    @Test fun wordClassSourcesRejectUnsafeNamesAndEmptyClasses() {
        val dir = kotlin.io.path.createTempDirectory("quantity-source").toFile()
        try {
            File("src/main/quantity").copyRecursively(dir, overwrite = true)
            val rule = File(dir, "invalid.ngram")
            for (name in listOf("../objects.words", "/objects.words", "empty.words")) {
                File(dir, "empty.words").writeText("# no words\n")
                rule.writeText("words(\"$name\") + quantity(\"個\")")
                assertFailsWith<IllegalArgumentException>(name) { QuantitySource.parse(dir) }
            }
        } finally { dir.deleteRecursively() }
    }
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
    @Test fun lexicalAliasesCopyMetadataWithoutReplacingNames() {
        val name = com.kazumaproject.dictionary.models.Dictionary("さんぼん", 1923, 1923, 6144, "三本")
        val number = com.kazumaproject.dictionary.models.Dictionary("さんぽん", 2046, 2011, 5712, "三本")
        val aliases = QuantityLexicalAliases.build(listOf(name, number),
            listOf(QuantityLexicalAliases.Reading(3, "本", "さんぼん")), setOf(2046))
        assertEquals(listOf(number.copy(yomi = "さんぼん")), aliases)
        assertTrue(QuantityLexicalAliases.build(listOf(name, number) + aliases,
            listOf(QuantityLexicalAliases.Reading(3, "本", "さんぼん")), setOf(2046)).isEmpty())
    }
    @Test fun ruleFilterSeparatesSemanticContextFromGenericSuffixes() {
        val generic = listOf(QuantityDictionary.Token("8件", "はっけん"), QuantityDictionary.Token("だけ", "だけ"))
        val semantic = listOf(QuantityDictionary.Token("事件", "じけん"), QuantityDictionary.Token("が", "が"), QuantityDictionary.Token("8件", "はっけん"))
        val contextual: (List<QuantityDictionary.Feature>) -> Boolean = { it.first() is QuantityDictionary.Feature.Word }
        assertEquals(0, dictionary.matchStrength(generic, contextual) { _, _, _, _, _ -> true })
        assertEquals(3, dictionary.matchStrength(semantic, contextual) { _, _, _, _, unit -> unit == "件" })
    }
}
