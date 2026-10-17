import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.PrintStream
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.*
import kotlin.test.*

class CandidateCliTest {
    @Test
    fun selectsAllThirtyOrIndividualCategoriesAndRejectsInvalidConfiguration() {
        assertEquals(30, availableCandidateCategories().size)
        assertEquals(availableCandidateCategories().keys,
            parseCandidateCliOptions(arrayOf("--categories", "all", "そらとぶ")).categories)
        assertEquals(setOf("person", "medical"), parseCandidateCliOptions(
            arrayOf("--categories=person", "--categories", "medical", "あ")).categories)
        assertTrue(parseCandidateCliOptions(arrayOf("あ")).categories.isEmpty())
        assertTrue(parseCandidateCliOptions(arrayOf("--list-categories")).listCategories)
        for (args in listOf(
            arrayOf("--categories", "../person", "あ"), arrayOf("--categories=person,", "あ"),
            arrayOf("--count", "0", "あ"), arrayOf("--predict", "あ"),
            arrayOf("--resource-dir", "a", "--assets-zip", "b", "あ"), arrayOf("--assets-zip"),
            arrayOf("--categories", "person", "--predict=false", "あ"),
        )) assertFailsWith<IllegalArgumentException> { parseCandidateCliOptions(args) }
    }

    private fun fixture(test: (File) -> Unit) {
        val root = Files.createTempDirectory("candidate-cli-test").toFile()
        try {
            val system = listOf(
                Dictionary("そらとぶ", 1, 1, 12000, "空飛ぶ"),
                Dictionary("あ", 1, 1, 100, "亜"),
            )
            val categories = availableCandidateCategories().keys.associateWith { id -> when (id) {
                "work_other" -> listOf(Dictionary("そらとぶいえ", 1, 1, 8400, "空とぶ家"),
                    Dictionary("そらとぶいえ", 1, 1, 8500, "別の家"))
                "person" -> listOf(Dictionary("たろう", 1, 1, 1000, "太郎"))
                "medical" -> listOf(Dictionary("やまい", 1, 1, 2000, "病"))
                else -> emptyList()
            } }
            val all = (system + categories.values.flatten()).groupBy { it.yomi }.toSortedMap()
            TokenArray().buildPOSTable(all, 1, File(root, "pos_table.dat").path)
            val posBuild = File(root, "pos-build.dat")
            TokenArray().buildPOSTableWithIndex(all, 1, posBuild.path)
            fun build(entries: List<Dictionary>, output: File) {
                output.mkdirs()
                buildAndWriteDictionaryArtifacts(entries.groupBy { it.yomi }.toSortedMap(),
                    File(output, "yomi.dat").path, File(output, "tango.dat").path, File(output, "token.dat").path,
                    posTableForBuildPath = posBuild.path)
            }
            build(system, root)
            categories.forEach { (id, entries) -> build(entries, File(root, "dictionary_categories/$id")) }
            File(root, "connectionId.dat").writeBytes(ByteArray(8))
            test(root)
        } finally {
            root.deleteRecursively()
        }
    }

    private fun options(root: File, vararg args: String) =
        parseCandidateCliOptions(arrayOf("--resource-dir", root.path, *args))

    @Test
    fun readsOnlySelectedBinariesAndFindsCategoryNodesInsideCompounds() = fixture { root ->
        val system = createCandidateCliEngine(options(root, "たろう"))
        assertTrue(system.nBestPath("たろう", 5).isEmpty())
        val person = createCandidateCliEngine(options(root, "--categories", "person", "たろう"))
        assertEquals(listOf("太郎"), person.nBestPath("たろう", 5))
        assertEquals("亜太郎", person.nBestPath("あたろう", 1).single())
        assertTrue(person.nBestPath("やまい", 5).isEmpty())
        File(root, "dictionary_categories/medical/token.dat").delete()
        createCandidateCliEngine(options(root, "--categories", "person", "たろう"))
        assertFailsWith<java.io.IOException> {
            createCandidateCliEngine(options(root, "--categories", "medical", "やまい"))
        }
    }

    @Test
    fun predictionUsesThePrefixEvenWhenItIsNotATerminalAndKeepsConversionSeparate() = fixture { root ->
        val engine = createCandidateCliEngine(options(root, "--categories", "all", "そらとぶ"))
        assertEquals(listOf("空飛ぶ"), engine.nBestPath("そらとぶ", 10))
        val predicted = engine.candidates("そらとぶ", 10, predict = true)
        assertEquals(listOf("空とぶ家", "別の家", "空飛ぶ"), predicted.map { it.text })
        assertEquals(11400, predicted.first().score)
        assertEquals("そらとぶいえ", predicted.first().reading)
        assertEquals("work_other", predicted.first().category)
        assertEquals("prediction", predicted.first().kind)
        assertEquals("conversion", predicted.last().kind)
        assertEquals(listOf("空とぶ家", "別の家"), engine.nBestPath("そらとぶいえ", 10))
        assertTrue(engine.candidates("そら", 10, predict = true).isEmpty())
    }

    @Test
    fun shippedZipLoadsItsOwnSystemPosAndSelectedCategoryAssets() = fixture { root ->
        val archive = File(root, "distribution.zip")
        ZipOutputStream(archive.outputStream()).use { zip ->
            fun add(path: String, bytes: ByteArray) {
                zip.putNextEntry(ZipEntry("app/src/main/assets/$path")); zip.write(bytes); zip.closeEntry()
            }
            fun dictionary(directory: File, prefix: String) {
                for (name in listOf("yomi", "tango", "token")) {
                    val nested = ByteArrayOutputStream()
                    ZipOutputStream(nested).use {
                        it.putNextEntry(ZipEntry("$name.dat"))
                        it.write(File(directory, "$name.dat").readBytes()); it.closeEntry()
                    }
                    add("$prefix/$name.dat.zip", nested.toByteArray())
                }
            }
            dictionary(root, "system")
            dictionary(File(root, "dictionary_categories/work_other"), "categories/work_other")
            add("pos_table.dat", File(root, "pos_table.dat").readBytes())
            val connection = ByteArrayOutputStream()
            ZipOutputStream(connection).use {
                it.putNextEntry(ZipEntry("connectionId.dat")); it.write(ByteArray(8)); it.closeEntry()
            }
            add("connectionId.dat.zip", connection.toByteArray())
        }
        val options = parseCandidateCliOptions(arrayOf("--assets-zip", archive.path,
            "--categories", "work_other", "そらとぶ"))
        val zipped = createCandidateCliEngine(options).candidates("そらとぶ", 10, predict = true)
        val generated = createCandidateCliEngine(options(root, "--categories", "work_other", "そらとぶ"))
            .candidates("そらとぶ", 10, predict = true)
        assertEquals(generated, zipped)
        val stdout = System.out
        val buffer = ByteArrayOutputStream()
        try {
            System.setOut(PrintStream(buffer))
            main(arrayOf("--assets-zip", archive.path, "--categories", "work_other",
                "--predict", "--details", "そらとぶ"))
        } finally { System.setOut(stdout) }
        val json = Json.parseToJsonElement(buffer.toString()).jsonObject
        assertEquals("空とぶ家", json.getValue("candidates").jsonArray.first().jsonObject.getValue("text").jsonPrimitive.content)
    }
}
