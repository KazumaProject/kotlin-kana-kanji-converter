package com.kazumaproject.ngram

import java.nio.file.Files
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NgramCorrectionDictionaryTest {
    @Test
    fun binaryWriterReaderRoundTripsOrders1Through5() {
        val candidates = listOf(
            candidate(1, "あす", "明日"),
            candidate(2, "きょうは", "今日", "は"),
            candidate(3, "とうきょうへいく", "東京", "へ", "行く"),
            candidate(4, "あおいそらをみる", "青い", "空", "を", "見る"),
            candidate(5, "きょうのてんきははれ", "今日", "の", "天気", "は", "晴れ"),
        )

        val dictionary = NgramCorrectionDataReader().readBytes(NgramCorrectionDataWriter().toByteArray(candidates))

        candidates.forEach { expected ->
            val results = dictionary.lookup(expected.reading)
            assertTrue(results.any { it.order == expected.order && it.surfaces == expected.surfaces })
        }
        assertEquals("明日", dictionary.lookupBest("あす")?.surfaceText)
        assertTrue(dictionary.lookup("missing").isEmpty())
    }

    @Test
    fun bestCandidatePreservesSourceOrderWithinSameReading() {
        val candidates = listOf(
            candidate(2, "きょうは", "今日", "は"),
            candidate(1, "きょうは", "今日は"),
        )

        val dictionary = NgramCorrectionDataReader().readBytes(NgramCorrectionDataWriter().toByteArray(candidates))
        val results = dictionary.lookup("きょうは")

        assertEquals(listOf("今日", "は"), results[0].surfaces)
        assertEquals(listOf("今日は"), results[1].surfaces)
        assertEquals(listOf("今日", "は"), dictionary.lookupBest("きょうは")?.surfaces)
    }

    @Test
    fun compilerDedupeExactDuplicatesAndKeepsAlternativeCandidates() {
        val dir = Files.createTempDirectory("ngram-correction-source-")
        try {
            dir.resolve("sources_manifest.tsv").writeText(
                """
                enabled	file	kind	orders	description
                true	rules.tsv	correction	1,2	test rules
                """.trimIndent() + "\n"
            )
            dir.resolve("rules.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	surface5	source	comment
                2	きょうは	今日	は				test	first
                2	きょうは	今日	は				test	duplicate
                1	きょうは	今日は					test	alternative
                """.trimIndent() + "\n"
            )

            val compiled = NgramCorrectionCompiler.compile(dir)

            assertEquals(listOf("rules.tsv"), compiled.sourceReadResult.sourceFiles)
            assertEquals(3, compiled.sourceReadResult.sourceRowCount)
            assertEquals(1, compiled.duplicateCount)
            assertEquals(2, compiled.candidates.size)
            assertEquals(listOf("今日", "は"), compiled.candidates.first().surfaces)
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun verifierChecksEveryGeneratedCandidateStrictly() {
        val dir = Files.createTempDirectory("ngram-correction-verify-")
        try {
            dir.resolve("rules.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	surface5	source	comment
                1	あす	明日					test	
                2	きょうは	今日	は				test	
                3	とうきょうへいく	東京	へ	行く			test	
                4	あおいそらをみる	青い	空	を	見る		test	
                5	きょうのてんきははれ	今日	の	天気	は	晴れ	test	
                """.trimIndent() + "\n"
            )
            val output = dir.resolve("ngram_correction.data")
            val manifest = dir.resolve("ngram_correction_manifest.json")

            val generated = NgramCorrectionGenerator.generate(dir, output, manifest)
            val verified = NgramCorrectionVerifier.verify(dir, output)

            assertEquals(5, generated.candidateCount)
            assertEquals(5, verified)
            assertTrue(Files.readString(manifest).contains("\"lookupMode\""))
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun exactReadingLookupPreventsPrefixOrMutatedFalsePositive() {
        val dictionary = NgramCorrectionDataReader().readBytes(
            NgramCorrectionDataWriter().toByteArray(listOf(candidate(1, "とうきょう", "東京")))
        )

        assertNotNull(dictionary.lookupBest("とうきょう"))
        assertNull(dictionary.lookupBest("とうきょ"))
        assertNull(dictionary.lookupBest("とうきょう "))
        assertFalse(dictionary.lookup("東京").isNotEmpty())
    }

    @Test
    fun emptyCorrectionDictionaryReturnsNoCandidates() {
        assertTrue(EmptyBinaryNgramCorrectionDictionary.lookup("あす").isEmpty())
        assertNull(EmptyBinaryNgramCorrectionDictionary.lookupBest("あす"))
    }

    @Test
    fun generatedCorrectionBytesAreDeterministic() {
        val candidates = (1..5).flatMap { order ->
            (1..20).map { index ->
                candidate(
                    order,
                    "よみ$order-$index",
                    *Array(order) { surfaceIndex -> "語$order-$index-$surfaceIndex" },
                )
            }
        }

        val bytes1 = NgramCorrectionDataWriter().toByteArray(candidates)
        val bytes2 = NgramCorrectionDataWriter().toByteArray(candidates)

        assertContentEquals(bytes1, bytes2)
    }

    private fun candidate(order: Int, reading: String, vararg surfaces: String): NgramCorrectionCandidate {
        assertEquals(order, surfaces.size)
        return NgramCorrectionCandidate(order = order, reading = reading, surfaces = surfaces.toList())
    }
}
