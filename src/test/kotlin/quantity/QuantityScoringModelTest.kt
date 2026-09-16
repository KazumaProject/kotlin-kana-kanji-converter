package com.kazumaproject.quantity

import kotlin.test.*

class QuantityScoringModelTest {
    private fun model() = QuantityScoringModel("a".repeat(64), "b".repeat(64),
        listOf(QuantityScoringModel.Lexeme("に", "二", 2, 2046, 2046, 4797)),
        listOf(QuantityScoringModel.UnitLexeme("ほん", "本", QuantityScoringModel.UnitRole.COUNTER, 2011, 2011, 2000)),
        intArrayOf(-100, 0, -200), mapOf("本" to 1L),
        listOf(QuantityScoringModel.LexicalClass("買う", 800, 800, 1L)),
        listOf(QuantityScoringModel.Rule(listOf(QuantityScoringModel.Feature(QuantityScoringModel.FeatureKind.QUANTITY, 1),
            QuantityScoringModel.Feature(QuantityScoringModel.FeatureKind.LEXICAL, 1)), -300)))
    @Test fun roundTripAndIdentityPreserveTypedData() {
        val original = model(); val restored = QuantityScoringModel.read(original.write())
        assertContentEquals(original.write(), restored.write())
        assertEquals(2L, restored.numbers("に").single().value)
        assertEquals(1L, restored.classes("買う", 800, 800))
        assertEquals(0L, restored.classes("買う", 1923, 1923))
        assertEquals(-500, restored.constructionCost(CardinalGrammar.Features(1, 0, 2)))
        for (position in listOf(0, 4, 8, 16, original.write().lastIndex)) {
            val damaged = original.write(); damaged[position] = (damaged[position].toInt() xor 1).toByte()
            assertFails { QuantityScoringModel.read(damaged) }
        }
    }
    @Test fun calibrationGeneralizesSharedFeaturesWithoutPerExampleWeights() {
        val anchors = listOf(QuantityRankCalibrator.Anchor(doubleArrayOf(1.0, 0.0), -1000.0))
        val preferences = listOf(QuantityRankCalibrator.Preference(doubleArrayOf(0.0, 1.0), 800.0),
            QuantityRankCalibrator.Preference(doubleArrayOf(0.0, -1.0), -2000.0))
        val weights = QuantityRankCalibrator.fit(2, anchors, preferences)
        assertTrue(weights[0] in -1000..-900)
        assertTrue(weights[1] in -1100..-900)
        assertTrue(600 + weights[1] < 0) // Held-out cost, same semantic relation.
        assertTrue(-1800 - weights[1] < 0) // Ordinary-word counterexample remains preferred.
        assertContentEquals(weights, QuantityRankCalibrator.fit(2, anchors, preferences))
    }
    @Test fun modelSourceUsesRealNumericAndUnitRolesAndInflectedVerbClasses() {
        val model = QuantityModelSource.numericModel(java.io.File("src/main/resources"), java.io.File("src/main/quantity"))
        assertTrue(model.numericLexemes.none { it.text in setOf("二重", "五重", "五獣") })
        assertTrue(model.numbers("さんびゃく").none { it.left == 1923 })
        assertTrue(model.quantities("はつか").any { it.value == 20L && it.unit == "日" && it.text == "二十日" })
        assertTrue(model.quantities("いつか").any { it.value == 5L && it.unit == "日" })
        assertTrue(model.quantityLexemes.none { it.text in setOf("初夏", "羽塚", "独り") || it.left in 1922..1929 })
        for (unit in listOf("円", "人", "分", "時", "本", "台", "冊", "日", "月", "足", "つ"))
            assertTrue(model.unitLexemes.any { it.text == unit && it.role == QuantityScoringModel.UnitRole.COUNTER }, unit)
        assertTrue(model.units("かん").none { it.left == 1923 })
        assertTrue(model.units("かん").any { it.text == "間" && it.role == QuantityScoringModel.UnitRole.SUFFIX })
        val basic = model.lexicalClasses.filter { it.text == "使う" }.fold(0L) { bits, entry -> bits or entry.classes }
        assertTrue(basic != 0L)
        assertTrue(model.lexicalClasses.any { it.text == "使っ" && it.classes and basic != 0L })
        val contexts = java.io.File("src/main/resources/id.def").readLines()
            .associate { it.substringBefore(' ').toInt() to it.substringAfter(' ') }
        assertTrue(model.lexicalClasses.filter { it.text == "使い" && it.classes and basic != 0L }
            .all { contexts.getValue(it.left).startsWith("動詞,") })
        assertContentEquals(model.write(), QuantityScoringModel.read(model.write()).write())
    }

    @Test fun contextInflectionsPreservePartOfSpeechAndConjugation() {
        val forms = QuantityContextSource.inflections("使う", "動詞,自立,*,*,五段・ワ行促音便,基本形", 1)
        assertTrue(forms.any { it.text == "使っ" && it.conjugation == "連用タ接続" })
        assertTrue(forms.any { it.text == "使い" && it.conjugation == "連用形" })
        assertTrue(forms.all { it.family.startsWith("動詞,自立,") })
        assertTrue(QuantityContextSource.inflections("使い", "名詞,一般,*,*,*,*", 1).isEmpty())
        assertTrue(QuantityContextSource.inflections("使っ", "動詞,自立,*,*,五段・ワ行促音便,連用タ接続", 1).isEmpty())
        assertTrue(QuantityContextSource.inflections("分かれる", "動詞,自立,*,*,一段,基本形", 2)
            .any { it.text == "分かれ" && it.conjugation == "連用形" })
    }

    @Test fun ruleFeaturesRejectAmbiguousClassMasksBeforeInstallation() {
        val source = model()
        assertFailsWith<IllegalArgumentException> {
            QuantityScoringModel(source.posFingerprint, source.connectionFingerprint,
                source.numericLexemes, source.unitLexemes, source.constructionWeights,
                source.quantityClasses, source.lexicalClasses, listOf(QuantityScoringModel.Rule(
                    listOf(QuantityScoringModel.Feature(QuantityScoringModel.FeatureKind.QUANTITY, 3),
                        QuantityScoringModel.Feature(QuantityScoringModel.FeatureKind.LEXICAL, 1)), -100)))
        }
    }

    @Test fun numericArcsDoNotChargeInsideAnExistingCompoundLexemeTwice() {
        val words = listOf(
            QuantityScoringModel.Lexeme("に", "2", 2, 1, 1, 10),
            QuantityScoringModel.Lexeme("じゅう", "十", 10, 1, 1, 20),
            QuantityScoringModel.Lexeme("にじゅう", "二十", 20, 1, 1, 25))
        val source = model()
        val numeric = QuantityScoringModel(source.posFingerprint, source.connectionFingerprint, words, emptyList(),
            intArrayOf(-5, 0, -7), emptyMap(), emptyList(), emptyList())
        val graph = NumericGrammarGraph("にじゅうに", CardinalGrammar.parse("にじゅうに")!!, numeric)
        assertEquals(CardinalGrammar.Features.ZERO, graph.starts[0].single { it.end == 2 }.joining)
        assertEquals(CardinalGrammar.Features(1, 0, 0), graph.starts[1].single().joining)
        assertEquals(CardinalGrammar.Features(0, 0, 1), graph.starts[2].single().joining)
        assertEquals(3, graph.size)
    }

}
