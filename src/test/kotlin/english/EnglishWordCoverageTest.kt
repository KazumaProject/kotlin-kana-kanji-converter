package english

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.english.*
import java.io.ByteArrayInputStream
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class EnglishWordCoverageTest {
    private val csvHeader = "Lemma,SFI Rank,SFI,Adjusted Frequency per Million (U)\n"
    private fun stream(text: String) = ByteArrayInputStream(text.toByteArray())
    private fun wordList(rows: String) = EnglishWordCoverage.parseWordList(stream(csvHeader + rows), "fixture.csv")
    private fun entry(reading: String, surface: String, cost: Int = 12500) = Dictionary(reading, 1851, 1851, cost.toShort(), surface)
    private fun target(word: String, rank: Int) = EnglishWordTarget(word, rank, "ngsl-1.2")

    @Test
    fun countsTheGeneralStemAsAnAdditionAndReadsBothCaseDistinctBaselineRows() {
        val abbreviation = entry("すてむ", "STEM", 18501)
        val ordinary = entry("すてむ", "stem")
        val coverage = EnglishWordCoverage(listOf(target("stem", 1)), listOf(abbreviation), listOf(abbreviation, ordinary))
        assertEquals(EnglishWordCoverageStatus.ADDED, coverage.rows.single().status)
        assertEquals(listOf(ordinary), coverage.addedPairs)
        val baseline = "reading\tleft_id\tright_id\tcost\tsurface\nすてむ\t1851\t1851\t18501\tSTEM\nすてむ\t1851\t1851\t12500\tstem\n"
        assertEquals(listOf(abbreviation, ordinary), EnglishWordCoverage.parseBaseline(stream(baseline), "case-baseline.tsv"))
    }

    @Test
    fun distinguishesCanonicalHeadwordsFromAbbreviationsAndCompounds() {
        val baseline = listOf(entry("あっぷる", "apple"), entry("あいてぃー", "IT"), entry("ぎゃらりー", "art gallery"), entry("めい", "May"))
        val runtime = baseline + listOf(entry("せーぶ", "save"), entry("さーばー", "server"), entry("さーば", "server", 12800))
        val targets = listOf(target("apple", 1), target("save", 2), target("server", 3), target("it", 4), target("art", 5), target("may", 6))
        val coverage = EnglishWordCoverage(targets, baseline, runtime)
        val byWord = coverage.rows.associateBy { it.target.word }
        assertEquals(EnglishWordCoverageStatus.EXISTING, byWord.getValue("apple").status)
        assertEquals(EnglishWordCoverageStatus.ADDED, byWord.getValue("save").status)
        assertEquals(EnglishWordCoverageStatus.ADDED, byWord.getValue("server").status)
        assertEquals(EnglishWordCoverageStatus.EXCLUDED, byWord.getValue("it").status)
        assertTrue(byWord.getValue("it").runtimeReadings.isEmpty())
        assertEquals(EnglishWordCoverageStatus.DEFERRED, byWord.getValue("art").status)
        assertEquals(EnglishWordCoverageStatus.DEFERRED, byWord.getValue("may").status)
        assertTrue(byWord.getValue("may").runtimeReadings.isEmpty())
        assertEquals(2, coverage.rows.count { it.status == EnglishWordCoverageStatus.ADDED })
        assertEquals(3, coverage.addedPairs.size)
        assertEquals(1, coverage.addedReadingsForNewSurfaces)
        assertEquals(setOf("save", "server"), coverage.newSingleWordSurfaces)
    }

    @Test
    fun keepsFunctionNumericAndSingleLetterExclusionsInAudit() {
        val targets = listOf(target("the", 1), target("one", 2), target("a", 3), target("whether", 4), target("review", 5))
        val coverage = EnglishWordCoverage(targets, emptyList(), emptyList())
        assertTrue(coverage.rows.take(3).all { it.status == EnglishWordCoverageStatus.EXCLUDED })
        assertTrue(coverage.rows[0].reason.contains("function-word-surface"))
        assertTrue(coverage.rows[1].reason.contains("numeric-surface"))
        assertTrue(coverage.rows[2].reason.contains("single-letter-surface"))
        assertEquals(EnglishWordCoverageStatus.EXCLUDED, coverage.rows[3].status)
        assertTrue(coverage.rows[3].reason.contains("explanatory-gloss"))
        assertEquals(EnglishWordCoverageStatus.DEFERRED, coverage.rows[4].status)
        assertTrue(coverage.rows.all { it.reason.isNotBlank() })
    }

    @Test
    fun countsExtraReadingsWithoutCountingThemAsHeadwordsOrInferringForms() {
        val baseline = listOf(entry("さーばー", "server"), entry("みーてぃんぐ", "meeting"))
        val runtime = baseline + listOf(entry("さーば", "server", 12800), entry("れびゅー", "review"),
            entry("れびゅーず", "reviews"), entry("ちーむみーてぃんぐ", "team meeting"))
        val coverage = EnglishWordCoverage(listOf(target("server", 1), target("review", 2)), baseline, runtime)
        assertEquals(1, coverage.rows.count { it.status == EnglishWordCoverageStatus.ADDED })
        assertEquals(1, coverage.addedReadingsForBaselineSurfaces)
        assertEquals(setOf("reviews"), coverage.newNonTargetSingleWordSurfaces)
        assertEquals(1, coverage.addedCompoundPairs)
    }

    @Test
    fun reportsCaseChangesSeparatelyFromNewPairs() {
        val old = entry("めい", "May", 18500)
        val current = entry("めい", "may", 12500)
        val coverage = EnglishWordCoverage(listOf(target("may", 1)), listOf(old), listOf(current))
        assertEquals(EnglishWordCoverageStatus.ADDED, coverage.rows.single().status)
        assertTrue(coverage.addedPairs.isEmpty())
        assertEquals(listOf(old to current), coverage.changedExistingPairs)
        assertEquals(0, coverage.removedPairs)
    }

    @Test
    fun explicitReviewReasonsArePreservedAndCannotOverrideRuntimeOrPolicy() {
        val targets = listOf(target("review", 1), target("the", 2), target("save", 3))
        val decision = EnglishWordReviewDecision("review", "rejected", "Unresolved full pronunciation correspondence", "reviews.tsv: line=2")
        val coverage = EnglishWordCoverage(targets, emptyList(), listOf(entry("せーぶ", "save")), listOf(decision))
        assertTrue(coverage.rows[0].reason.contains("Review rejected: Unresolved"))
        for (word in listOf("the", "save", "unknown")) {
            val error = assertFailsWith<IllegalArgumentException> {
                EnglishWordCoverage(targets, emptyList(), listOf(entry("せーぶ", "save")), listOf(decision.copy(word = word)))
            }
            assertTrue(error.message!!.contains("reviews.tsv: line=2"))
        }
    }

    @Test
    fun validatesCsvColumnsNumbersQuotingAndDuplicatesWithLineNumbers() {
        assertEquals(listOf("apple", "save"), wordList("\"apple\",1,70.1,100\n\"save\",2,69,90\n").map { it.word })
        for (rows in listOf(
            "apple,1,70\n", "apple,0,70,100\n", "apple,2,70,100\n", "Apple,1,70,100\n",
            "apple,1,NaN,100\n", "apple,1,70,-1\n", "\"apple,1,70,100\n",
            "\"apple\"x,1,70,100\n", "apple,1,70,100\napple,2,69,90\n", "apple,1,70,100\nsave,1,69,90\n",
        )) {
            val error = assertFailsWith<IllegalArgumentException> { wordList(rows) }
            assertTrue(error.message!!.contains("fixture.csv: line="), error.message)
        }
        assertFailsWith<IllegalArgumentException> { EnglishWordCoverage.parseWordList(stream("word,rank\n"), "bad.csv") }
    }

    @Test
    fun productionWordListRequiresPinnedOfficialBytes() {
        val path = Files.createTempFile("ngsl-fixture", ".csv")
        try {
            Files.writeString(path, csvHeader + "apple,1,70,100\n")
            assertEquals(1, EnglishWordCoverage.readWordList(path, verifyOfficial = false).size)
            assertFailsWith<IllegalArgumentException> { EnglishWordCoverage.readWordList(path) }
        } finally {
            Files.deleteIfExists(path)
        }
    }

    @Test
    fun validatesReviewDecisionsAndRuntimeSnapshotsWithLineNumbers() {
        val decisions = EnglishWordCoverage.parseDecisions(stream("word\tstatus\treason\nreview\tdeferred\tNo attested reading\n"), "review.tsv")
        assertEquals("No attested reading", decisions.single().reason)
        for (rows in listOf("review\tapproved\treason\n", "review\tdeferred\t\n", "review\tdeferred\treason\nreview\trejected\tother\n")) {
            val error = assertFailsWith<IllegalArgumentException> {
                EnglishWordCoverage.parseDecisions(stream("word\tstatus\treason\n" + rows), "review.tsv")
            }
            assertTrue(error.message!!.contains("review.tsv: line="))
        }
        val header = "reading\tleft_id\tright_id\tcost\tsurface\n"
        val parsed = EnglishWordCoverage.parseBaseline(stream(header + "さーばー\t1851\t1851\t12500\tserver\n"), "runtime.tsv")
        assertEquals(listOf(entry("さーばー", "server")), parsed)
        for (rows in listOf("サーバー\t1851\t1851\t12500\tserver\n", "さーばー\t32768\t1851\t12500\tserver\n",
            "さーばー\t1851\t1851\t0\tserver\n", "さーばー\t1851\t1851\t12500\tserver\nさーばー\t1851\t1851\t12500\tserver\n")) {
            val error = assertFailsWith<IllegalArgumentException> { EnglishWordCoverage.parseBaseline(stream(header + rows), "runtime.tsv") }
            assertTrue(error.message!!.contains("runtime.tsv: line="))
        }
    }

    @Test
    fun reportsAreStableAcrossInputOrderingAndDoNotClaimApplicationCoverage() {
        val targets = listOf(target("save", 2), target("apple", 1), EnglishWordTarget("deploy", null, "development-work"))
        val baseline = listOf(entry("あっぷる", "apple"))
        val runtime = baseline + listOf(entry("せーぶ", "save"), entry("せいぶ", "save", 12800))
        val first = Files.createTempDirectory("english-coverage-first")
        val second = Files.createTempDirectory("english-coverage-second")
        try {
            EnglishWordCoverage(targets, baseline, runtime).write(first)
            EnglishWordCoverage(targets.reversed(), baseline.reversed(), runtime.reversed()).write(second)
            for (file in listOf("targets.tsv", "added-pairs.tsv", "summary.md")) {
                assertEquals(Files.readString(first.resolve(file)), Files.readString(second.resolve(file)))
            }
            assertTrue(Files.readString(first.resolve("summary.md")).contains("内訳は未確認"))
            assertTrue(Files.readString(first.resolve("summary.md")).contains("実端末の候補順位も示しません"))
        } finally {
            first.toFile().deleteRecursively()
            second.toFile().deleteRecursively()
        }
    }

    @Test
    fun fixedDevelopmentTargetsAreAddedOnceWithNoFrequencyRank() {
        val base = listOf(target("apple", 1), target("deploy", 2))
        val all = EnglishWordCoverage.withAdditionalWords(base)
        assertEquals(24, all.size)
        assertEquals(1, all.count { it.word == "deploy" })
        assertTrue(all.map { it.word }.containsAll(listOf("sync", "async", "fetch", "webhook")))
        assertEquals(all.size, all.map { it.word }.distinct().size)
        assertTrue(all.filter { it.word !in setOf("apple", "deploy") }.all { it.rank == null && it.origin == "development-work" })
    }

    @Test
    fun explicitlyMapsBooleanSourceSpellingsAndKeepsIAsSingleLetter() {
        val targets = wordList("I,1,70,100\nTRUE,2,69,90\nFALSE,3,68,80\n")
        assertEquals(listOf("I", "true", "false"), targets.map { it.word })
        assertEquals(listOf("I", "TRUE", "FALSE"), targets.map { it.sourceWord })
        val runtime = listOf(entry("とぅるー", "true"), entry("ふぉーるす", "false"))
        val rows = EnglishWordCoverage(targets, runtime, runtime).rows
        assertEquals(EnglishWordCoverageStatus.EXCLUDED, rows[0].status)
        assertTrue(rows.drop(1).all { it.status == EnglishWordCoverageStatus.EXISTING })
        assertFailsWith<IllegalArgumentException> { wordList("TRUE,1,70,100\ntrue,2,69,90\n") }
    }
}
