package com.kazumaproject.ngram

import java.nio.file.Files
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ContextualCorrectionDictionaryTest {
    @Test
    fun parserReadsLiteralSlotAndTargetPattern() {
        val rule = ContextualCorrectionRuleParser.parse(
            ContextualCorrectionSourceRule(
                id = "cloth_wipe_object",
                pattern = "lit(ぬので,布で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)",
                source = "test",
                comment = "",
                sourceFile = "test.tsv",
                lineNumber = 2,
            )
        )

        assertEquals("cloth_wipe_object", rule.id)
        assertEquals(4, rule.items.size)
        assertEquals(3, rule.targetIndex)
        assertEquals(ContextualCorrectionPatternKind.SLOT, rule.items[1].kind)
        assertEquals(ContextualCorrectionCoarseClass.NOUN, rule.items[1].coarseClass)
        assertEquals("拭く", rule.items[3].replacementSurface)
    }

    @Test
    fun binaryRoundTripMatchesClothNounObjectWipeRule() {
        val dictionary = dictionaryFromRules(clothRule())
        val tokens = listOf(
            token("ぬので", "布で", ContextualCorrectionCoarseClass.UNKNOWN),
            token("ふるーと", "フルート", ContextualCorrectionCoarseClass.NOUN),
            token("を", "を", ContextualCorrectionCoarseClass.PARTICLE),
            token("ふく", "吹く", ContextualCorrectionCoarseClass.VERB),
        )

        val candidate = dictionary.lookupBest(tokens)

        assertEquals("cloth_wipe_object", candidate?.ruleId)
        assertEquals(listOf("布で", "フルート", "を", "拭く"), candidate?.surfaces)
        assertEquals("布でフルートを拭く", candidate?.surfaceText)
    }

    @Test
    fun slotClassMustMatch() {
        val dictionary = dictionaryFromRules(clothRule())
        val tokens = listOf(
            token("ぬので", "布で", ContextualCorrectionCoarseClass.UNKNOWN),
            token("すぐ", "すぐ", ContextualCorrectionCoarseClass.UNKNOWN),
            token("を", "を", ContextualCorrectionCoarseClass.PARTICLE),
            token("ふく", "吹く", ContextualCorrectionCoarseClass.VERB),
        )

        assertNull(dictionary.lookupBest(tokens))
    }

    @Test
    fun literalAndTargetSurfaceMustMatchExactly() {
        val dictionary = dictionaryFromRules(clothRule())
        val wrongLiteral = listOf(
            token("ぬので", "布", ContextualCorrectionCoarseClass.UNKNOWN),
            token("ふるーと", "フルート", ContextualCorrectionCoarseClass.NOUN),
            token("を", "を", ContextualCorrectionCoarseClass.PARTICLE),
            token("ふく", "吹く", ContextualCorrectionCoarseClass.VERB),
        )
        val wrongTarget = listOf(
            token("ぬので", "布で", ContextualCorrectionCoarseClass.UNKNOWN),
            token("ふるーと", "フルート", ContextualCorrectionCoarseClass.NOUN),
            token("を", "を", ContextualCorrectionCoarseClass.PARTICLE),
            token("ふく", "拭く", ContextualCorrectionCoarseClass.VERB),
        )

        assertNull(dictionary.lookupBest(wrongLiteral))
        assertNull(dictionary.lookupBest(wrongTarget))
    }

    @Test
    fun compilerReadsManifestAndDedupeExactDuplicates() {
        val dir = Files.createTempDirectory("context-correction-")
        try {
            dir.resolve("sources_manifest.tsv").writeText(
                """
                enabled	file	kind	description
                true	rules.tsv	contextual_correction	test rules
                """.trimIndent() + "\n"
            )
            dir.resolve("rules.tsv").writeText(
                """
                id	pattern	source	comment
                cloth_wipe_object	lit(ぬので,布で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)	test	first
                cloth_wipe_object	lit(ぬので,布で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)	test	duplicate
                """.trimIndent() + "\n"
            )

            val compiled = ContextualCorrectionCompiler.compile(dir)

            assertEquals(listOf("rules.tsv"), compiled.sourceReadResult.sourceFiles)
            assertEquals(2, compiled.sourceReadResult.sourceRowCount)
            assertEquals(1, compiled.rules.size)
            assertEquals(1, compiled.duplicateCount)
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun generatorVerifierAndManifestRoundTrip() {
        val dir = Files.createTempDirectory("context-correction-generate-")
        try {
            dir.resolve("sources_manifest.tsv").writeText(
                """
                enabled	file	kind	description
                true	rules.tsv	contextual_correction	test rules
                """.trimIndent() + "\n"
            )
            dir.resolve("rules.tsv").writeText(
                """
                id	pattern	source	comment
                cloth_wipe_object	lit(ぬので,布で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)	test	first
                """.trimIndent() + "\n"
            )
            val data = dir.resolve("context_correction.data")
            val manifest = dir.resolve("context_correction_manifest.json")

            val generated = ContextualCorrectionGenerator.generate(dir, data, manifest)
            val verified = ContextualCorrectionVerifier.verify(dir, data)

            assertEquals(1, generated.ruleCount)
            assertEquals(1, verified)
            assertTrue(Files.readString(manifest).contains("\"lookupMode\""))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun emptyDictionaryReturnsNoCandidates() {
        assertTrue(EmptyBinaryContextualCorrectionDictionary.lookup(emptyList()).isEmpty())
        assertNull(EmptyBinaryContextualCorrectionDictionary.lookupBest(listOf(token("a", "A", ContextualCorrectionCoarseClass.NOUN))))
    }

    @Test
    fun generatedBytesAreDeterministic() {
        val rules = listOf(
            clothRule(),
            ContextualCorrectionRuleParser.parse(
                ContextualCorrectionSourceRule(
                    id = "paper_wipe_object",
                    pattern = "lit(かみで,紙で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)",
                    source = "test",
                    comment = "",
                    sourceFile = "test.tsv",
                    lineNumber = 3,
                )
            )
        )

        val bytes1 = ContextualCorrectionDataWriter().toByteArray(rules)
        val bytes2 = ContextualCorrectionDataWriter().toByteArray(rules)

        assertContentEquals(bytes1, bytes2)
    }

    @Test
    fun lookupDoesNotUsePrefixMatch() {
        val dictionary = dictionaryFromRules(clothRule())
        val tokens = listOf(
            token("ぬのでさらに", "布でさらに", ContextualCorrectionCoarseClass.UNKNOWN),
            token("ふるーと", "フルート", ContextualCorrectionCoarseClass.NOUN),
            token("を", "を", ContextualCorrectionCoarseClass.PARTICLE),
            token("ふく", "吹く", ContextualCorrectionCoarseClass.VERB),
        )

        assertFalse(dictionary.lookup(tokens).isNotEmpty())
    }

    private fun dictionaryFromRules(vararg rules: ContextualCorrectionRule): LoadedContextualCorrectionDictionary =
        ContextualCorrectionDataReader().readBytes(ContextualCorrectionDataWriter().toByteArray(rules.toList()))

    private fun clothRule(): ContextualCorrectionRule =
        ContextualCorrectionRuleParser.parse(
            ContextualCorrectionSourceRule(
                id = "cloth_wipe_object",
                pattern = "lit(ぬので,布で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)",
                source = "test",
                comment = "",
                sourceFile = "test.tsv",
                lineNumber = 2,
            )
        )

    private fun token(
        reading: String,
        surface: String,
        coarseClass: ContextualCorrectionCoarseClass,
    ): ContextualCorrectionToken = ContextualCorrectionToken(reading, surface, coarseClass)
}
