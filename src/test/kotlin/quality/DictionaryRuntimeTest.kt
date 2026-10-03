package quality

import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.cli.DictionaryCli
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.LoadedDictionary
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.quality.sha256
import kotlinx.serialization.json.*
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.nio.file.Files
import kotlin.test.*

internal fun fixture(directory: File, words: List<Dictionary>, skipKanaOnlyTango: Boolean = false): LoadedDictionary {
    directory.mkdirs()
    val sorted = words.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    val pos = File(directory, "pos_table_for_build.dat")
    TokenArray().buildPOSTable(sorted, 1, File(directory, "pos_table.dat").path)
    TokenArray().buildPOSTableWithIndex(sorted, 1, pos.path)
    buildAndWriteDictionaryArtifacts(sorted, File(directory, "yomi.dat").path, File(directory, "tango.dat").path, File(directory, "token.dat").path, posTableForBuildPath = pos.path, skipKanaOnlyTango = skipKanaOnlyTango)
    pos.delete()
    return LoadedDictionary.load(directory.name, directory)
}

class DictionaryRuntimeTest {
    @Test fun exactAndSurfaceIterationDecodeKanaAndRejectPrefixes() = temporary { root ->
        val loaded = fixture(File(root, "person"), listOf(Dictionary("やまだ", 1, 2, 10, "山田"), Dictionary("かな", 1, 2, 20, "かな"), Dictionary("かたかな", 1, 2, 30, "カタカナ")))
        assertTrue(loaded.lookup("やま").isEmpty())
        assertEquals("山田", loaded.lookup("やまだ").single().surface)
        assertEquals("かな", loaded.lookup("かな").single().surface)
        assertEquals("カタカナ", loaded.lookup("かたかな").single().surface)
        assertEquals(setOf("やまだ", "かな", "かたかな"), loaded.readings().toSet())
        assertEquals(1, loaded.lookup("やまだ").single().leftId)
        assertEquals(2, loaded.lookup("やまだ").single().rightId)
    }
    @Test fun preservesKanaSurfacesThatDifferFromReading() = temporary { root ->
        for (skip in listOf(false, true)) {
            val loaded = fixture(File(root, "kana-$skip"), listOf(
                Dictionary("あい", 1, 1, 10, "ゆい"),
                Dictionary("べとなむ", 1, 1, 10, "アン"),
                Dictionary("が", 1, 1, 10, "か\u3099"),
                Dictionary("かな", 1, 1, 10, "カナ")
            ), skipKanaOnlyTango = skip)
            assertEquals("ゆい", loaded.lookup("あい").single().surface)
            assertEquals("アン", loaded.lookup("べとなむ").single().surface)
            assertEquals("が", loaded.lookup("が").single().surface)
            assertEquals("カナ", loaded.lookup("かな").single().surface)
        }
    }
    @Test fun mixesPosTablesAndRetainsRuntimeProvenance() = temporary { root ->
        val system = fixture(File(root, "system"), listOf(Dictionary("は", 1, 1, 10, "は")))
        val person = fixture(File(root, "person"), listOf(Dictionary("やまだ", 2, 2, 20, "山田")))
        val matrix = File(root, "connectionId.dat")
        ConnectionIdBuilder().writeMatrixAsBytes(ConnectionMatrix(3, ShortArray(9)), matrix.path)
        val engine = KanaKanjiEngine().apply { loadDictionaries(listOf(system, person, person.copy(id = "other")), matrix) }
        assertEquals("山田は", engine.convert("やまだは").value)
        assertEquals(listOf("person", "system"), engine.convertDetailed("やまだは").dictionaries)
        assertEquals(listOf(2, 1), engine.convert("やまだは").bestPath.map { it.lid })
        assertEquals(listOf("山田は"), engine.nBestPath("やまだは", 10))
        assertTrue(engine.convert("ない").bestPath.isEmpty())
    }
    @Test fun emptyDictionaryHasNoMatches() = temporary { root ->
        val empty = fixture(root, emptyList())
        assertTrue(empty.lookup("あ").isEmpty())
        assertTrue(empty.readings().none())
    }
    @Test fun cliRegressionAndValidation() = temporary { root ->
        val pack = File(root, "person")
        fixture(pack, listOf(Dictionary("やまだ", 1, 1, 10, "山田")))
        File(pack, "pos_table.dat").copyTo(File(root, "pos_table.dat"))
        File(root, "manifest.json").writeText(buildJsonObject {
            put("format", "legacy-louds-triplets-v1")
            put("artifacts", buildJsonObject { listOf("pos_table.dat", "person/yomi.dat", "person/tango.dat", "person/token.dat").forEach { put(it, sha256(File(root, it))) } })
        }.toString())
        fun run(vararg arguments: String): Pair<Int, String> {
            val out = StringWriter(); val err = StringWriter()
            val code = DictionaryCli.run(arrayOf(*arguments, "--dict-dir", root.path, "--categories", "person", "--no-system"), PrintWriter(out), PrintWriter(err))
            return code to (out.toString() + err.toString())
        }
        assertEquals(0, run("lookup", "--reading", "やまだ").first)
        assertTrue(run("lookup", "--surface", "山田").second.contains("やまだ"))
        assertEquals(2, run("lookup", "--reading", "やまだ", "--unknown", "x").first)
        val cases = File(root, "cases.tsv").apply { writeText("operation\tinput\tassertion\texpected\tcategories\nlookup\tやまだ\tcontains\t山田\tperson\nlookup\tやま\texcludes\t山田\tperson\n") }
        assertEquals(0, run("test", "--cases", cases.path).first)
        cases.appendText("lookup\tやまだ\tcontains\t山本\tperson\n")
        assertEquals(1, run("test", "--cases", cases.path).first)
        File(pack, "token.dat").appendBytes(byteArrayOf(1))
        assertEquals(2, run("lookup", "--reading", "やまだ").first)
    }
    private fun temporary(block: (File) -> Unit) {
        val root = Files.createTempDirectory("dictionary-runtime-").toFile()
        try { block(root) } finally { root.deleteRecursively() }
    }
}
