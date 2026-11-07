import dictionary.Dictionary
import grammar.Lexicon
import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

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
                readSupplementEntries(file, base, listOf(Dictionary("examplegap", 100, "Example Gap", true)), emptySet())
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
}
