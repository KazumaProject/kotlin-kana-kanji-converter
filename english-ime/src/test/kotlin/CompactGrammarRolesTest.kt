import conversion.PhraseConverter
import conversion.ReviewedDictionary
import dictionary.Dictionary
import grammar.CompactGrammarRoles
import grammar.Lexicon
import grammar.lookupKey
import java.io.File
import java.nio.ByteBuffer
import java.nio.file.Files
import java.util.zip.CRC32
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class CompactGrammarRolesTest {
    @Test
    fun preservesExactAndNormalizedRolesAndConvertsWithoutTsv() = inTemporaryDirectory { root ->
        val grammar = root.resolve("grammar").apply { mkdir() }
        for (name in tsvNames) File("data/grammar", name).copyTo(grammar.resolve(name))
        grammar.resolve("categories.tsv").appendText("contraction\tContracted spelling\tdon’t\n")
        grammar.resolve("forms.tsv").appendText(
            "fixture-He\tHe\tHe\thttps://example.org/surname\n" +
                "fixture-word\tPokémon\tPokémon\thttps://example.org/name\n" +
                "fixture-dont\tdon’t\tdon’t\thttps://example.org/contraction\n",
        )
        grammar.resolve("memberships.tsv").appendText(
            "noun_proper\tfixture-He\tHe\nnoun_proper\tfixture-word\tPokémon\n" +
                "contraction\tfixture-dont\tdon’t\n",
        )
        val lexicon = Lexicon.load(grammar)
        writeReviewedPayloads(listOf("he", "can", "take", "takes").map { Dictionary(it, 100, it, false) }, root)
        val metadata = grammar.resolve("bundle.properties")
        metadata.writeText("schemaVersion=1\nreviewComplete=true\n")
        val legacy = PhraseConverter(ReviewedDictionary.load(root)).convert("hecantake", false, 10)
        assertEquals("he can take", legacy.first().text)

        val compact = grammar.resolve("categories.ecat")
        writeCompactCategories(lexicon, compact)
        metadata.appendText("categories.ecat.sha256=${categoryFileHash(compact)}\n")
        tsvNames.forEach { Files.delete(grammar.resolve(it).toPath()) }
        val dictionary = ReviewedDictionary.load(root)
        val surfaces = lexicon.forms.map { it.key.surface }.toSet() +
            listOf("He", "HE", "he", "POKÉMON", "don’t", "don't", "DON'T", "unknown")
        for (surface in surfaces) {
            val expected = lexicon.lookup(surface).flatMap { it.dictionaries }.toSet()
            assertEquals(expected, dictionary.grammarRoles.lookup(surface, lookupKey(surface)), surface)
        }
        assertEquals(legacy, PhraseConverter(dictionary).convert("hecantake", false, 10))
    }

    @Test
    fun acceptsAnEmptyLowercaseIndex() = inTemporaryDirectory { grammar ->
        grammar.resolve("categories.tsv").writeText("category\tdefinition\texamples\nnoun\tnoun\tHe\n")
        grammar.resolve("forms.tsv").writeText("lexeme_id\tlemma\tsurface\tevidence\nname\tHe\tHe\thttps://example.org\n")
        grammar.resolve("memberships.tsv").writeText("category\tlexeme_id\tsurface\nnoun\tname\tHe\n")
        val compact = grammar.resolve("categories.ecat")
        writeCompactCategories(Lexicon.load(grammar), compact)
        val roles = CompactGrammarRoles.load(compact.toPath(), null)
        assertEquals(setOf("noun"), roles.lookup("He", "he"))
        assertEquals(emptySet(), roles.lookup("he", "he"))
    }

    @Test
    fun rejectsCorruptDataAndInvalidPostingsEvenWithAValidCrc() = inTemporaryDirectory { root ->
        val compact = root.resolve("categories.ecat")
        writeCompactCategories(Lexicon.load(File("data/grammar")), compact)
        val bytes = compact.readBytes()
        val wrongHash = assertFailsWith<IllegalArgumentException> {
            CompactGrammarRoles.load(compact.toPath(), "0".repeat(64))
        }
        assertTrue(wrongHash.message.orEmpty().contains("SHA-256 mismatch"))

        val payload = ByteBuffer.wrap(bytes)
        payload.putInt(payload.getInt(76), Int.MAX_VALUE)
        compact.writeBytes(bytes)
        val corrupt = assertFailsWith<IllegalArgumentException> {
            CompactGrammarRoles.load(compact.toPath(), null)
        }
        assertTrue(corrupt.message.orEmpty().contains("payload checksum"))

        payload.putInt(12, CRC32().apply { update(bytes, 96, bytes.size - 96) }.value.toInt())
        compact.writeBytes(bytes)
        val invalid = assertFailsWith<IllegalArgumentException> {
            CompactGrammarRoles.load(compact.toPath(), null)
        }
        assertTrue(invalid.message.orEmpty().contains("Invalid posting form"))
    }

    private fun inTemporaryDirectory(test: (File) -> Unit) {
        val root = Files.createTempDirectory("compact-grammar").toFile()
        try {
            test(root)
        } finally {
            root.deleteRecursively()
        }
    }

    private companion object {
        val tsvNames = listOf("categories.tsv", "forms.tsv", "memberships.tsv")
    }
}
