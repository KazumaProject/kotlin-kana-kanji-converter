import dictionary.Dictionary
import grammar.Lexicon
import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlinx.serialization.json.*

class ReviewedSupplementTest {
    @Test
    fun readingsComeFromTheConfirmedSurface() {
        assertEquals(setOf("two-factor authentication", "twofactor authentication", "twofactorauthentication"),
            supplementReadings("two-factor authentication"))
        assertEquals(setOf("carry-on", "carryon"), supplementReadings("carry-on"))
        assertEquals(setOf("y'all", "yall"), supplementReadings("y’all"))
        assertFailsWith<IllegalArgumentException> { supplementReadings("do  not") }
        assertFailsWith<IllegalArgumentException> { supplementReadings("a@b") }
    }

    @Test
    fun rejectsDuplicateIdentitiesUnknownCategoriesAndExistingOrExcludedSurfaces() {
        val directory = createTempDirectory("reviewed-supplement-test").toFile()
        try {
            val file = directory.resolve("entries.tsv")
            val base = Lexicon.load(File("data/grammar"))
            val header = "lexeme_id\tlemma\tsurface\tcategories\tdomain\tevidence\tsource_ref\n"
            val row = "supp-example\texample gap\texample gap\tnoun,domain_daily\tdaily\thttps://example.org/gap\tverified:1\n"
            file.writeText(header + row)
            assertEquals("example gap", readSupplementEntries(file, base, emptyList(), emptySet()).single().key.surface)
            assertFailsWith<IllegalArgumentException> {
                readSupplementEntries(file, base, listOf(Dictionary("examplegap", 100, "example gap", true)), emptySet())
            }
            assertFailsWith<IllegalArgumentException> {
                readSupplementEntries(file, base, emptyList(), setOf("example gap"))
            }
            file.writeText(header + row + row)
            assertFailsWith<IllegalArgumentException> { readSupplementEntries(file, base, emptyList(), emptySet()) }
            file.writeText(header + row.replace("noun,domain_daily", "noun,domain_daily,imaginary_category"))
            assertFailsWith<IllegalArgumentException> { readSupplementEntries(file, base, emptyList(), emptySet()) }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun acceptsAttestedCaseVariantsAndFunctionWordFormsWithoutRelaxingExclusions() {
        val directory = createTempDirectory("reviewed-display-case-test").toFile()
        try {
            val file = directory.resolve("entries.tsv")
            val base = Lexicon.load(File("data/grammar"))
            val header = "lexeme_id\tlemma\tsurface\tcategories\tdomain\tevidence\tsource_ref\n"
            file.writeText(header + "month-may\tMay\tMay\tnoun,noun_proper,domain_daily\tdaily\thttps://example.org/calendar\tcalendar:May\n")
            val original = listOf(Dictionary("may", 100, "may", false))
            assertEquals("May", readSupplementEntries(file, base, original, emptySet()).single().key.surface)
            assertFailsWith<IllegalArgumentException> { readSupplementEntries(file, base, original, setOf("may")) }
            file.writeText(header + "pronoun-we\twe\tus\tpronoun,domain_daily\tdaily\thttps://example.org/pronouns\tverified:us\n")
            assertEquals("us", readSupplementEntries(file, base, emptyList(), emptySet()).single().key.surface)
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun metadataAddsTopicsWithoutDuplicatingCandidatesOrChangingTheirCosts() {
        val root = createTempDirectory("topic-supplement").toFile()
        try {
            val grammar = File("data/grammar")
            val base = Lexicon.load(grammar)
            val original = listOf(Dictionary("fast", 123, "fast", false))
            val header = "lexeme_id\tlemma\tsurface\tcategories\tdomain\tevidence\tsource_ref\n"
            val decisions = root.resolve("decisions.tsv").apply {
                writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                    "1\tfast\tfast\t123\tinclude\tadj-fast\tfixture\thttps://example.org/fast\n")
            }
            val sourceManifest = root.resolve("base.json").apply { writeText("{}") }
            val supp = root.resolve("supplement").apply { mkdir() }
            supp.resolve("entries.tsv").writeText(header +
                "topic-gap\tsample gap\tsample gap\tnoun,domain_science,topic_fixture\tscience\thttps://example.org/gap\tfixture:gap\n")
            supp.resolve("metadata.tsv").writeText(header +
                "adj-fast\tfast\tfast\tdomain_technology,topic_fixture\ttechnology\thttps://example.org/fast\tfixture:fast\n")
            supp.resolve("categories.tsv").writeText("category\tdefinition\texamples\n" +
                "topic_fixture\tAttested fixture vocabulary\tfast, sample gap\n")
            supp.resolve("notices").mkdir()
            supp.resolve("notices/SOURCE.txt").writeText("Synthetic source notice\n")
            supp.resolve("manifest.json").writeText(buildJsonObject {
                put("kind", "reviewed-english-supplement-v2")
                put("schemaVersion", 2)
                put("baseManifestSha256", categoryFileHash(sourceManifest))
                putJsonObject("files") {
                    for (name in listOf("entries.tsv", "metadata.tsv", "categories.tsv", "notices/SOURCE.txt"))
                        put(name, categoryFileHash(supp.resolve(name)))
                }
            }.toString())
            val extension = ReviewedSupplement.load(supp, sourceManifest, base, original, decisions)
            assertTrue(extension.candidates.none { it.word == "fast" })
            val assets = root.resolve("assets").apply { mkdir() }
            val notices = root.resolve("notices").apply { mkdir(); resolve("BASE.txt").writeText("Fixture base notice") }
            writeReviewedPayloads(original + extension.candidates, assets)
            writeReviewedCategoryBundle(grammar, grammar.resolve("relations.tsv"), decisions, notices, assets, base, extension)
            val dictionary = conversion.ReviewedDictionary.load(assets)
            assertEquals(123, dictionary.allCandidates().single { it.surface == "fast" }.cost)
            assertTrue("topic_fixture" in dictionary.grammarRoles.lookup("fast", "fast"))
            assertTrue("domain_science" in dictionary.grammarRoles.lookup("sample gap", "sample gap"))
            val lexicon = Lexicon.load(assets.resolve("grammar"))
            val fast = lexicon.forms.single { it.key.lexemeId == "adj-fast" && it.key.surface == "fast" }
            assertTrue(fast.dictionaries.containsAll(base.lookup("fast").first { it.key.lexemeId == "adj-fast" }.dictionaries))
            val runtime = root.resolve("runtime")
            conversion.packReviewedRuntime(assets, runtime)
            assertEquals(dictionary.allCandidates().toList(), conversion.ReviewedDictionary.load(runtime).allCandidates().toList())
            assertEquals(dictionary.grammarRoles.lookup("fast", "fast"),
                conversion.ReviewedDictionary.load(runtime).grammarRoles.lookup("fast", "fast"))
        } finally { root.deleteRecursively() }
    }

    @Test
    fun metadataRequiresAnExistingFormAndCannotAddGrammaticalRoles() {
        val root = createTempDirectory("topic-metadata-validation").toFile()
        try {
            val base = Lexicon.load(File("data/grammar"))
            val file = root.resolve("metadata.tsv")
            val header = "lexeme_id\tlemma\tsurface\tcategories\tdomain\tevidence\tsource_ref\n"
            val row = "adj-fast\tfast\tfast\tdomain_technology,topic_fixture\ttechnology\thttps://example.org/fast\tfixture\n"
            val original = listOf(Dictionary("fast", 123, "fast", false))
            file.writeText(header + row)
            assertEquals(1, readSupplementMetadata(file, base, original, emptyList(), setOf("topic_fixture")).size)
            for (bad in listOf(row.replace("adj-fast", "unknown-id"), row.replace("\tfast\tfast", "\tslow\tfast"),
                row.replace("domain_technology,topic_fixture", "verb,topic_fixture"))) {
                file.writeText(header + bad)
                assertFailsWith<IllegalArgumentException> {
                    readSupplementMetadata(file, base, original, emptyList(), setOf("topic_fixture"))
                }
            }
            val specialGrammar = root.resolve("grammar").apply { mkdir() }
            for (name in listOf("categories.tsv", "forms.tsv", "memberships.tsv"))
                File("data/grammar", name).copyTo(specialGrammar.resolve(name))
            specialGrammar.resolve("forms.tsv").appendText("lang-cpp\tC++\tC++\thttps://example.org/cpp\n")
            specialGrammar.resolve("memberships.tsv").appendText("abbreviation\tlang-cpp\tC++\n")
            val withSpecial = Lexicon.load(specialGrammar)
            file.writeText(header + "lang-cpp\tC++\tC++\tdomain_technology,topic_fixture\ttechnology\thttps://example.org/cpp\tfixture\n")
            assertEquals("C++", readSupplementMetadata(file, withSpecial,
                listOf(Dictionary("cpp", 100, "C++", true)), emptyList(), setOf("topic_fixture")).single().key.surface)
        } finally { root.deleteRecursively() }
    }
}
