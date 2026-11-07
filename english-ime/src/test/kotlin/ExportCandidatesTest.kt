import conversion.ReviewedDictionary
import dictionary.Dictionary
import java.io.File
import java.nio.file.Files
import kotlinx.serialization.json.*
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class ExportCandidatesTest {
    @Test
    fun exportsActualBinaryPairsCostsAndCanonicalSpellingWithoutOverwriting() {
        val root = Files.createTempDirectory("export-candidates").toFile()
        try {
            val assets = root.resolve("assets").apply { mkdir() }
            val grammar = File("data/grammar")
            val decisions = root.resolve("decisions.tsv").apply {
                writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n" +
                    "1\tfixture\tfixture\t1\tinclude\tnoun\tverified\thttps://example.org/fixture\n")
            }
            val notices = root.resolve("notices").apply { mkdir() }
            notices.resolve("TEST.txt").writeText("Synthetic fixture notice\n")
            writeReviewedPayloads(listOf(Dictionary("yall", 700, "y'all", true),
                Dictionary("esim", 900, "eSIM", true), Dictionary("esim", 1000, "eSIM", true)), assets)
            writeReviewedCategoryBundle(grammar, grammar.resolve("relations.tsv"), decisions, notices, assets)
            val output = root.resolve("candidates.jsonl")
            exportCandidates(assets, output)
            val records = output.readLines().map { Json.parseToJsonElement(it).jsonObject }
            val pairs = records.associate { (it.getValue("reading").jsonPrimitive.content to
                it.getValue("surface").jsonPrimitive.content) to it.getValue("cost").jsonPrimitive.int }
            assertEquals(mapOf(("yall" to "y'all") to 700, ("esim" to "eSIM") to 900), pairs)
            assertEquals(ReviewedDictionary.load(assets).allCandidates().count(), records.size)
            val original = output.readText()
            assertFailsWith<java.nio.file.FileAlreadyExistsException> { exportCandidates(assets, output) }
            assertEquals(original, output.readText())
            val runtime = root.resolve("runtime")
            conversion.packReviewedRuntime(assets, runtime)
            val packedExport = root.resolve("runtime.jsonl")
            exportCandidates(runtime, packedExport)
            assertEquals(original, packedExport.readText())
        } finally { root.deleteRecursively() }
    }
}
