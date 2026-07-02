package com.kazumaproject.ngram

import java.nio.file.Files
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class NgramPresenceDictionaryTest {
    @Test
    fun tsvReaderReadsSpecAndAtokStyleHeaders() {
        val dir = Files.createTempDirectory("ngram-tsv-")
        try {
            dir.resolve("atok.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	source_id	update_no	update_date	improved
                2	きょうは	今日	は			ATOK-1	1	2026/01/01	今日は
                """.trimIndent() + "\n"
            )
            dir.resolve("spec.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	surface5	source	comment
                1	明日	明日				test	comment
                """.trimIndent() + "\n"
            )

            val result = NgramSourceTsvReader().readDirectory(dir)

            assertEquals(2, result.sourceRowCount)
            assertEquals(listOf("atok.tsv", "spec.tsv"), result.sourceFiles)
            assertEquals(listOf("今日", "は", "", "", ""), result.rules.first { it.order == 2 }.surfaces)
            assertEquals("ATOK-1", result.rules.first { it.order == 2 }.source)
            assertEquals("今日は", result.rules.first { it.order == 2 }.comment)
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun sourceSetManifestSelectsEnabledFilesOnly() {
        val dir = Files.createTempDirectory("ngram-source-set-")
        try {
            dir.resolve("sources_manifest.tsv").writeText(
                """
                enabled	file	kind	orders	description
                true	enabled.tsv	presence	1,2	enabled fixture
                false	disabled.tsv	presence	1	disabled fixture
                """.trimIndent() + "\n"
            )
            dir.resolve("enabled.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	surface5	source	comment
                1	きょう	今日				test	enabled
                """.trimIndent() + "\n"
            )
            dir.resolve("disabled.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	surface5	source	comment
                1	あす	明日				test	disabled
                """.trimIndent() + "\n"
            )

            val sourceSet = NgramSourceSetManifestReader.read(dir)
            val result = NgramSourceTsvReader().readDirectory(dir)

            assertEquals(listOf("enabled.tsv"), sourceSet?.enabledFiles)
            assertEquals(1, result.sourceRowCount)
            assertEquals(listOf("enabled.tsv"), result.sourceFiles)
            assertEquals("きょう", result.rules.single().reading)
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun sourceSetManifestValidatesDeclaredOrders() {
        val dir = Files.createTempDirectory("ngram-source-set-order-")
        try {
            dir.resolve("sources_manifest.tsv").writeText(
                """
                enabled	file	kind	orders	description
                true	rules.tsv	presence	1	only unigrams
                """.trimIndent() + "\n"
            )
            dir.resolve("rules.tsv").writeText(
                """
                order	reading	surface1	surface2	surface3	surface4	surface5	source	comment
                2	きょうは	今日	は			test	invalid
                """.trimIndent() + "\n"
            )

            assertFailsWith<IllegalArgumentException> {
                NgramSourceTsvReader().readDirectory(dir)
            }
        } finally {
            dir.toFile().deleteRecursively()
        }
    }

    @Test
    fun normalizerDetectsDuplicatesAndValidatesSurfaceArity() {
        val rules = listOf(
            rule(2, "きょうは", "今日", "は"),
            rule(2, "きょうは", "今日", "は"),
            rule(1, "あす", "明日"),
        )

        val result = NgramRuleNormalizer.normalizeAndDedupe(rules)

        assertEquals(2, result.rules.size)
        assertEquals(1, result.duplicateCount)
    }

    @Test
    fun fullReadingSegmentResolverResolvesSurfaceSequenceIntoTokens() {
        val terms = listOf(
            term(1, "きょう", "今日", 10, 11, 100),
            term(2, "は", "は", 12, 13, 50),
            term(3, "きょうは", "今日は", 14, 15, 80),
        )
        val resolver = FullReadingSegmentResolver(NgramTermResolver(terms))

        val resolved = resolver.resolve(rule(2, "きょうは", "今日", "は"))

        assertNotNull(resolved)
        assertEquals(listOf(terms[0].nodeKey, terms[1].nodeKey), resolved.terms.map { it.nodeKey })
    }

    @Test
    fun twoBitArrayRoundTrip() {
        val values = intArrayOf(0, 1, 2, 3, 2, 1, 0, 3, 1)
        val packed = TwoBitArray.fromIntArray(values)
        val unpacked = TwoBitArray.fromByteArray(values.size, packed.toByteArray())

        assertContentEquals(values, unpacked.toIntArray())
    }

    @Test
    fun rankBitVectorRanksOnesInclusively() {
        val rank = RankBitVector.fromBooleans(booleanArrayOf(true, false, true, true, false, false, true))

        assertTrue(rank.get(0))
        assertFalse(rank.get(1))
        assertEquals(1, rank.rank1(0))
        assertEquals(1, rank.rank1(1))
        assertEquals(3, rank.rank1(3))
        assertEquals(4, rank.rank1(6))
    }

    @Test
    fun bdzPeelingBuildsAWorkingSection() {
        val entries = (1..200).map { value ->
            NgramKeySequence(3, longArrayOf(value.toLong(), (value + 1).toLong(), (value + 2).toLong()))
        }

        val section = BdzMphfBuilder().build(3, entries)
        val dictionary = readDictionaryFromSections(section)

        entries.forEach { entry ->
            assertTrue(dictionary.contains3(entry.keys[0], entry.keys[1], entry.keys[2]))
        }
    }

    @Test
    fun binaryWriterReaderRoundTripsContains1Through5AndNegatives() {
        val entries = listOf(
            seq(1, 101),
            seq(2, 201, 202),
            seq(3, 301, 302, 303),
            seq(4, 401, 402, 403, 404),
            seq(5, 501, 502, 503, 504, 505),
        )
        val dictionary = readDictionaryFromEntries(entries)

        assertTrue(dictionary.contains1(101))
        assertTrue(dictionary.contains2(201, 202))
        assertTrue(dictionary.contains3(301, 302, 303))
        assertTrue(dictionary.contains4(401, 402, 403, 404))
        assertTrue(dictionary.contains5(501, 502, 503, 504, 505))
        assertFalse(dictionary.contains1(102))
        assertFalse(dictionary.contains2(201, 999))
        assertFalse(dictionary.contains3(301, 302, 999))
        assertFalse(dictionary.contains4(401, 402, 403, 999))
        assertFalse(dictionary.contains5(501, 502, 503, 504, 999))
    }

    @Test
    fun rawKeySequenceVerificationPreventsFalsePositiveAfterMphfIndexHit() {
        val entry = seq(1, 42)
        val dictionary = readDictionaryFromEntries(listOf(entry))
        val section = dictionary.section(1) ?: error("missing section")
        val trueIndex = section.index(42, 0, 0, 0, 0)
        var collidingKey = 43L
        while (collidingKey < 100_000L && section.index(collidingKey, 0, 0, 0, 0) != trueIndex) {
            collidingKey += 1
        }

        assertTrue(collidingKey < 100_000L, "Expected to find an MPHF index hit for the one-entry fixture")
        assertFalse(section.contains(collidingKey, 0, 0, 0, 0))
    }

    @Test
    fun emptyDictionaryAlwaysReturnsFalse() {
        assertFalse(EmptyBinaryNgramPresenceDictionary.contains1(1))
        assertFalse(EmptyBinaryNgramPresenceDictionary.contains2(1, 2))
        assertFalse(EmptyBinaryNgramPresenceDictionary.contains3(1, 2, 3))
        assertFalse(EmptyBinaryNgramPresenceDictionary.contains4(1, 2, 3, 4))
        assertFalse(EmptyBinaryNgramPresenceDictionary.contains5(1, 2, 3, 4, 5))
    }

    @Test
    fun generatedBytesAreDeterministic() {
        val entries = (1..5).flatMap { order ->
            (1..20).map { index ->
                NgramKeySequence(order, LongArray(order) { keyIndex -> order * 10_000L + index * 10L + keyIndex })
            }
        }

        val sections1 = buildSections(entries)
        val sections2 = buildSections(entries)
        val bytes1 = NgramPresenceDataWriter().toByteArray(sections1)
        val bytes2 = NgramPresenceDataWriter().toByteArray(sections2)

        assertContentEquals(bytes1, bytes2)
    }

    @Test
    fun tokenTermIdSidecarRoundTripsCompactPostingIds() {
        val dictionaries = listOf(
            dictionary("きょう", "今日", 10, 11, 100),
            dictionary("きょう", "京", 12, 13, 200),
            dictionary("は", "は", 14, 15, 50),
            dictionary("きょう", "今日", 16, 17, 300),
        )
        val build = NgramTokenTermIdBuilder.build(dictionaries)
        val tempDir = Files.createTempDirectory("ngram-token-term-id-")
        try {
            val output = tempDir.resolve("token_term_id.data")
            val checksum = NgramTokenTermIdDataWriter().write(output, build)
            val loaded = NgramTokenTermIdDataReader().read(output)

            assertEquals(checksum, loaded.contentChecksumHex)
            assertEquals(build.buildIdHex, loaded.buildIdHex)
            assertEquals(build.uniqueTermCount, loaded.uniqueTermCount)
            assertContentEquals(build.termIdsByTokenPosting, loaded.termIdsByTokenPosting)
            assertTrue(Files.size(output) < 128L)
        } finally {
            tempDir.toFile().deleteRecursively()
        }
    }

    private fun readDictionaryFromSections(vararg sections: BdzSectionBuild): LoadedNgramPresenceDictionary {
        val byOrder = sections.associateBy { it.order }
        val allSections = (1..NGRAM_SECTION_COUNT).map { order ->
            byOrder[order] ?: BdzMphfBuilder().build(order, emptyList())
        }
        val bytes = NgramPresenceDataWriter().toByteArray(allSections)
        return NgramPresenceDataReader().readBytes(bytes)
    }

    private fun readDictionaryFromEntries(entries: List<NgramKeySequence>): LoadedNgramPresenceDictionary {
        val bytes = NgramPresenceDataWriter().toByteArray(buildSections(entries))
        return NgramPresenceDataReader().readBytes(bytes)
    }

    private fun buildSections(entries: List<NgramKeySequence>): List<BdzSectionBuild> =
        (1..NGRAM_SECTION_COUNT).map { order -> BdzMphfBuilder().build(order, entries.filter { it.order == order }) }

    private fun rule(order: Int, reading: String, vararg surfaces: String): NgramRule {
        return NgramRule(
            order = order,
            reading = reading,
            surfaces = (surfaces.toList() + List(NGRAM_SECTION_COUNT) { "" }).take(NGRAM_SECTION_COUNT),
            source = "test",
            comment = "",
            sourceFile = "test.tsv",
            lineNumber = 1,
        )
    }

    private fun term(termId: Int, reading: String, surface: String, leftId: Int, rightId: Int, cost: Int): NgramTerm {
        return NgramTerm(
            termId = termId,
            reading = reading,
            surface = surface,
            leftId = leftId.toShort(),
            rightId = rightId.toShort(),
            cost = cost.toShort(),
        )
    }

    private fun dictionary(reading: String, surface: String, leftId: Int, rightId: Int, cost: Int) =
        com.kazumaproject.dictionary.models.Dictionary(
            yomi = reading,
            tango = surface,
            leftId = leftId.toShort(),
            rightId = rightId.toShort(),
            cost = cost.toShort(),
        )

    private fun seq(order: Int, vararg keys: Long): NgramKeySequence = NgramKeySequence(order, keys)
}
