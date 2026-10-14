package english

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.english.*
import java.io.ByteArrayInputStream
import java.nio.file.Files
import kotlin.test.*

class EnglishCandidateReviewTest {
    private val header = "reading\tsurface\tdecision\toutput_surface\tsource\treason\n"
    private fun review(rows: String) = EnglishCandidateReview.parse(
        ByteArrayInputStream((header + rows).toByteArray()), "review-fixture.tsv")
    private fun keep(reading: String, surface: String, output: String = surface) =
        "$reading\t$surface\tkeep\t$output\thttps://example.org/evidence\tReviewed case and scope\n"
    private fun row(reading: String, surface: String, cost: Int = 12500) =
        Dictionary(reading, 1851, 1851, cost.toShort(), surface)

    @Test
    fun unknownPairsRemainAuditableButCannotEnterTheRuntimeDictionary() {
        val source = EnglishDictionarySource(listOf(row("こーど", "code"), row("にゅー", "new")), emptyList(),
            review(keep("こーど", "code")))
        assertEquals(listOf("code"), source.runtimeEntries.map { it.tango })
        val unknown = source.assessments.single { it.source.tango == "new" }
        assertEquals(EnglishCandidateStatus.REVIEW, unknown.status)
        assertTrue(EnglishQualityFlag.UNREVIEWED_CANDIDATE in unknown.flags)
        assertNull(unknown.runtimeCost)
        // Neither an uppercase spelling nor another reading inherits an existing keep decision.
        for (candidate in listOf(row("こーど", "CODE"), row("こーでぃんぐ", "code"))) {
            assertTrue(EnglishDictionarySource(listOf(candidate), emptyList(), source.review).runtimeEntries.isEmpty())
        }
    }

    @Test
    fun reviewedCaseSelectionDeduplicatesOrdinaryWordsWithoutCollapsingAbbreviations() {
        val input = listOf(row("こーど", "CODE", 14000), row("こーど", "code", 12500),
            row("すてむ", "stem"), row("すてむ", "STEM", 18501), row("えーぴーあい", "API"), row("ぱいそん", "Python"))
        val decisions = input.joinToString("") { keep(it.yomi, it.tango, if (it.tango == "CODE") "code" else it.tango) }
        val source = EnglishDictionarySource(input, emptyList(), review(decisions))
        assertEquals(5, source.runtimeEntries.size)
        assertEquals(12500, source.runtimeEntries.single { it.tango == "code" }.cost.toInt())
        assertEquals(setOf("stem", "STEM"), source.runtimeEntries.filter { it.yomi == "すてむ" }.map { it.tango }.toSet())
        assertTrue(source.runtimeEntries.any { it.tango == "API" })
        assertTrue(source.runtimeEntries.any { it.tango == "Python" })
    }

    @Test
    fun editorialKeepNeverBypassesTheLexicalGateOrTheCompleteCompoundPair() {
        val input = listOf(row("ぜろ", "zero"), row("あんど", "and"), row("えー", "A"),
            row("ぎゃらりー", "art gallery"), row("さーばー", "server (machine)"))
        val decisions = input.joinToString("") { keep(it.yomi, it.tango) }
        assertTrue(EnglishDictionarySource(input, emptyList(), review(decisions)).runtimeEntries.isEmpty())
    }

    @Test
    fun exclusionAndUnreviewedStatusAreUsedByTheSameReportsAsCompilation() {
        val input = listOf(row("すー", "Sioux"), row("しんく", "sync"), row("にゅー", "new"))
        val decisions = review("すー\tSioux\texclude\t-\thttps://example.org/evidence\tOut of scope\n" + keep("しんく", "sync"))
        val source = EnglishDictionarySource(input, emptyList(), decisions)
        val output = Files.createTempFile("review-quality-", ".tsv")
        try {
            EnglishDictionaryReport.writeQuality(source.entries, output, source.allowedCompounds, source.assessments)
            val lines = Files.readAllLines(output).drop(1).map { it.split('\t') }.associateBy { it[3] }
            assertEquals("excluded", lines.getValue("Sioux")[7])
            assertEquals("", lines.getValue("Sioux")[6])
            assertEquals("review", lines.getValue("new")[7])
            assertEquals("primary", lines.getValue("sync")[7])
            assertEquals(listOf("sync"), source.runtimeEntries.map { it.tango })
        } finally { Files.deleteIfExists(output) }
    }

    @Test
    fun malformedDecisionsFailWithTheSourceAndLineNumber() {
        for (invalid in listOf(
            "こーど\tcode\tkeep\tcode\thttps://example.org\n", // missing reason
            "こーど\tcode\taccept\tcode\thttps://example.org\treason\n",
            "こーど\tcode\tkeep\tcodec\thttps://example.org\treason\n", // spelling change
            "こーど\tcode\texclude\tcode\thttps://example.org\treason\n",
            "コーど\tcode\tkeep\tcode\thttps://example.org\treason\n",
            "こーど\tcode\tkeep\tcode\thttp://example.org\treason\n",
            keep("こーど", "code") + keep("こーど", "code"),
        )) {
            val error = assertFailsWith<IllegalArgumentException> { review(invalid) }
            assertTrue(error.message!!.contains("review-fixture.tsv"))
            assertTrue(error.message!!.contains("line="))
        }
    }

    @Test
    fun shippedInputReviewIsCompleteAndRetainsTheRequestedHomophonesAndFormalSpellings() {
        val source = EnglishDictionarySource.loadResources(1851)
        assertTrue(source.entries.all { it.yomi to it.tango in source.review.decisions })
        assertTrue(source.assessments.none { EnglishQualityFlag.UNREVIEWED_CANDIDATE in it.flags })
        val pairs = source.runtimeEntries.map { it.yomi to it.tango }.toSet()
        for (pair in listOf("しんく" to "sync", "しんく" to "sink", "しんく" to "think",
            "ふぇっち" to "fetch", "えいしんく" to "async", "うぇぶふっく" to "webhook",
            "すてむ" to "stem", "すてむ" to "STEM", "えーぴーあい" to "API", "じぇいそん" to "JSON")) {
            assertTrue(pair in pairs, "Missing $pair")
        }
        assertTrue(pairs.none { it.second in setOf("Sioux", "rigging") })
        assertTrue(pairs.none { it.second in setOf("Boolean", "Internet", "Navy", "Brie", "Sir") })
    }

    @Test
    fun changesDistinguishCaseUpdatesAdditionsRemovalsAndCostChanges() {
        val old = listOf(row("いんたーねっと", "Internet"), row("すー", "Sioux"), row("めい", "may"), row("こーど", "code", 14000))
        val current = listOf(row("いんたーねっと", "internet"), row("めい", "may"), row("めい", "May"), row("こーど", "code"))
        val changes = EnglishDictionaryChanges.compare(old, current)
        assertEquals(mapOf("surface-changed" to 1, "removed" to 1, "added" to 1, "cost-or-pos-changed" to 1),
            changes.groupingBy { it.kind }.eachCount())
        assertEquals("May", changes.single { it.kind == "added" }.after!!.tango)
        assertEquals("Sioux", changes.single { it.kind == "removed" }.before!!.tango)
    }
}
