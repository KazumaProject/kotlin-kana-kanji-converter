package english

import com.kazumaproject.english.EnglishDictionaryBuilder
import com.kazumaproject.english.EnglishCandidateStatus
import com.kazumaproject.english.EnglishDictionaryReport
import com.kazumaproject.english.EnglishDictionaryQuality
import com.kazumaproject.english.EnglishQualityFlag
import com.kazumaproject.dictionary.models.Dictionary
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class EnglishDictionaryBuilderTest {

    @Test
    fun parsesMozcFiveColumnRowsAndKeepsEnglishSpaces() {
        val path = Files.createTempFile("english-dictionary-", ".txt")
        try {
            Files.writeString(
                path,
                "あいあん\t1851\t1851\t14500\tiron\n" +
                        "あいあん\t1851\t1851\t14520\tiron (element)\n",
            )

            val entries = EnglishDictionaryBuilder().parse(path, expectedContextId = 1851)

            assertEquals(2, entries.size)
            assertEquals("あいあん", entries[0].yomi)
            assertEquals("iron (element)", entries[1].tango)
            assertEquals(14520, entries[1].cost.toInt())
        } finally {
            Files.deleteIfExists(path)
        }
    }

    @Test
    fun rejectsMalformedRowsAndUnexpectedContextIds() {
        val path = Files.createTempFile("english-dictionary-invalid-", ".txt")
        try {
            Files.writeString(path, "あ\t1\t1\t12000\n")
            assertFailsWith<IllegalArgumentException> {
                EnglishDictionaryBuilder().parse(path)
            }

            Files.writeString(path, "あ\t1\t1\t12000\tah\n")
            assertFailsWith<IllegalArgumentException> {
                EnglishDictionaryBuilder().parse(path, expectedContextId = 1851)
            }
        } finally {
            Files.deleteIfExists(path)
        }
    }

    @Test
    fun groupsCandidatesByReadingInCostOrder() {
        val path = Files.createTempFile("english-dictionary-report-", ".txt")
        try {
            Files.writeString(
                path,
                "あ\t1851\t1851\t12002\tsecond\n" +
                        "あ\t1851\t1851\t12000\tfirst\n" +
                        "い\t1851\t1851\t12000\tonly\n",
            )

            val groups = EnglishDictionaryReport.groupByReading(EnglishDictionaryBuilder().parse(path))

            assertEquals(listOf("あ", "い"), groups.map { it.reading })
            assertEquals(listOf("first", "second"), groups[0].candidates.map { it.tango })
            assertEquals(1, EnglishDictionaryReport.summarize(EnglishDictionaryBuilder().parse(path)).multiCandidateReadings)
            assertTrue(groups.all { it.candidates.isNotEmpty() })
        } finally {
            Files.deleteIfExists(path)
        }
    }

    @Test
    fun qualityFilterKeepsNaturalPhrasesAndSeparatesUnsafeOrExplanatoryRows() {
        val entries = listOf(
            dictionary("あいすくりーむ", "ice cream"),
            dictionary("あいあん", "iron (element)"),
            dictionary("すじ", "counter for small things"),
            dictionary("あ", "-ism"),
            dictionary("あいえぬじー", "doing ..."),
            dictionary("ぷらすまいなす", "+-"),
            dictionary("ゖ", "ke"),
        )

        val assessments = EnglishDictionaryQuality.assessAll(entries)

        assertEquals(EnglishCandidateStatus.PRIMARY, assessments[0].status)
        assertEquals(EnglishCandidateStatus.REVIEW, assessments[1].status)
        assertTrue(EnglishQualityFlag.PARENTHETICAL in assessments[1].flags)
        assertEquals(EnglishCandidateStatus.REVIEW, assessments[2].status)
        assertTrue(EnglishQualityFlag.EXPLANATORY_GLOSS in assessments[2].flags)
        assertEquals(EnglishCandidateStatus.EXCLUDED, assessments[3].status)
        assertEquals(EnglishCandidateStatus.EXCLUDED, assessments[4].status)
        assertEquals(EnglishCandidateStatus.EXCLUDED, assessments[5].status)
        assertEquals("け", assessments[6].normalizedReading)
        assertEquals(EnglishCandidateStatus.EXCLUDED, assessments[6].status)

        val runtime = EnglishDictionaryQuality.runtimeEntriesFromAssessments(assessments)
        assertEquals(runtime, EnglishDictionaryQuality.runtimeEntries(entries))
        assertTrue(runtime.any { it.tango == "ice cream" && it.yomi == "あいすくりーむ" })
        assertTrue(runtime.none { it.tango in setOf("iron (element)", "counter for small things", "-ism", "doing ...", "+-", "ke") })
        assertEquals(1, runtime.size)

        val quality = EnglishDictionaryQuality.summarize(entries)
        assertEquals(1, quality.runtimeEntries)
    }

    @Test
    fun excludesNonLexicalShortCandidatesButKeepsNaturalEnglishTerms() {
        val entries = listOf(
            dictionary("あー", "two"),
            dictionary("いー", "one"),
            dictionary("うー", "five"),
            dictionary("えー", "A"),
            dictionary("おー", "the penny drops!"),
            dictionary("ぜろ", "zero"),
            dictionary("ざん", "the"),
            dictionary("えす", "S"),
            dictionary("ぐふふ", "ha ha ha"),
            dictionary("いひひ", "hee-hee"),
            dictionary("うっぷす", "oops"),
            dictionary("あい", "eye"),
            dictionary("あいあん", "iron"),
            dictionary("あいすくりーむ", "ice cream"),
            dictionary("あめりか", "United States"),
            dictionary("おーけー", "okay"),
            dictionary("いぇす", "yes"),
            dictionary("えびでんす", "evidence-based medicine"),
            dictionary("ぶら", "the way a bra fits"),
        )

        val assessments = EnglishDictionaryQuality.assessAll(entries).associateBy { it.source.tango }

        for (surface in listOf(
            "two",
            "one",
            "five",
            "A",
            "the penny drops!",
            "zero",
            "the",
            "S",
            "ha ha ha",
            "hee-hee",
            "oops",
        )) {
            assertEquals(EnglishCandidateStatus.EXCLUDED, assessments.getValue(surface).status, surface)
        }
        assertTrue(EnglishQualityFlag.VOCALIZATION_READING in assessments.getValue("two").flags)
        assertTrue(EnglishQualityFlag.NUMERIC_SURFACE in assessments.getValue("two").flags)
        assertTrue(EnglishQualityFlag.EXCLAMATORY_SURFACE in assessments.getValue("the penny drops!").flags)
        assertTrue(EnglishQualityFlag.FUNCTION_WORD_SURFACE in assessments.getValue("the").flags)
        assertTrue(EnglishQualityFlag.SINGLE_LETTER_SURFACE in assessments.getValue("S").flags)

        for (surface in listOf(
            "eye",
            "iron",
            "ice cream",
            "United States",
            "okay",
            "yes",
            "evidence-based medicine",
        )) {
            assertEquals(EnglishCandidateStatus.PRIMARY, assessments.getValue(surface).status, surface)
        }
        assertEquals(EnglishCandidateStatus.REVIEW, assessments.getValue("the way a bra fits").status)
        assertTrue(EnglishQualityFlag.DEFINITION_FRAGMENT in assessments.getValue("the way a bra fits").flags)

        val runtime = EnglishDictionaryQuality.runtimeEntriesFromAssessments(assessments.values.toList())
        assertEquals(
            setOf("eye", "iron", "ice cream", "United States", "okay", "yes", "evidence-based medicine"),
            runtime.map { it.tango }.toSet(),
        )
    }

    private fun dictionary(reading: String, surface: String, cost: Int = 18500): Dictionary =
        Dictionary(
            yomi = reading,
            leftId = 1851.toShort(),
            rightId = 1851.toShort(),
            cost = cost.toShort(),
            tango = surface,
        )
}
