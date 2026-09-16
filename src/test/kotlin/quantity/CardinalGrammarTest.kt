package com.kazumaproject.quantity

import kotlin.test.*

class CardinalGrammarTest {
    @Test fun authoritativeAtomicValuesCoverLongWithoutOverflow() {
        for (value in listOf(0L, 17L, 9_999_999_999_999_999L, 10_000_000_000_000_000L, Long.MAX_VALUE)) {
            val reading = CardinalGrammar.reading(value)
            assertEquals(value, CardinalGrammar.parse(reading)?.value, reading)
        }
        assertNull(CardinalGrammar.parse("せんけい"))
        assertNull(CardinalGrammar.surfaceValue("千京"))
        assertEquals(10_000_000_000_000_000L, CardinalGrammar.surfaceValue("京"))
    }
    @Test fun preservesPhonologyAndComponentRanges() {
        val expression = CardinalGrammar.parse("さんびゃくごじゅうに")!!
        assertEquals(352L, expression.value)
        assertEquals(listOf(3L, 100L, 5L, 10L, 2L), expression.atoms.map { it.value })
        assertEquals(listOf("さん", "びゃく", "ご", "じゅう", "に"), expression.atoms.map { "さんびゃくごじゅうに".substring(it.start, it.end) })
        assertEquals(CardinalGrammar.Features(2, 0, 2), expression.features)
        assertEquals("ひゃく", expression.atoms[1].lexicalReading)
    }
    @Test fun handlesLargeMagnitudesAndContractedReadings() {
        for ((reading, value) in listOf("ろっぴゃく" to 600L, "はっせん" to 8000L,
            "いっちょう" to 1_000_000_000_000L, "じっちょう" to 10_000_000_000_000L,
            "におくさんまんよん" to 200_030_004L)) {
            val expression = CardinalGrammar.parse(reading)!!
            assertEquals(value, expression.value)
            assertEquals(0, expression.atoms.first().start)
            assertEquals(reading.length, expression.atoms.last().end)
            for ((before, after) in expression.atoms.zipWithNext()) assertEquals(before.end, after.start)
        }
        for (reading in listOf("いちちょう", "にじゅうじゅう", "まん", "さんびゃくえん", "にじゅうにじゅう"))
            assertNull(CardinalGrammar.parse(reading), reading)
    }
}
