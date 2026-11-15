package engine

import com.kazumaproject.Constants
import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.mozc.ConnectionMatrix
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class AllCategoryConversionTest {
    @Test
    fun swipePrecedesOptionalNamesInOneSharedLattice() {
        val directory = Files.createTempDirectory("all-category-conversion-").toFile()
        try {
            val swipe = Constants.RESCORE_WORDS.single { it.yomi == "すわいぷ" }
            val noun = swipe.leftId
            val system = listOf(swipe, Dictionary("する", noun, noun, 100, "する"))
            val organization = listOf(Dictionary("すわいぷ", noun, noun, 9431, "Swip"))
            val technology = listOf(Dictionary("すわいぷ", noun, noun, 9431, "Swipe"))
            val all = system + organization + technology
            val pos = File(directory, "pos_table.dat").path
            val buildPos = File(directory, "pos_table_for_build.dat").path
            TokenArray().buildPOSTable(all.groupBy { it.yomi }.toSortedMap(), mode = 1, outputPath = pos)
            TokenArray().buildPOSTableWithIndex(all.groupBy { it.yomi }.toSortedMap(), mode = 1, outputPath = buildPos)
            fun write(name: String, records: List<Dictionary>): String {
                val target = File(directory, name).apply { mkdirs() }
                buildAndWriteDictionaryArtifacts(
                    records.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it })),
                    File(target, "yomi.dat").path, File(target, "tango.dat").path,
                    File(target, "token.dat").path, posTableForBuildPath = buildPos,
                )
                return target.path
            }
            write(".", system)
            val extras = listOf(write("organization", organization), write("technology", technology))
            ConnectionIdBuilder().writeMatrixAsBytes(
                ConnectionMatrix(noun.toInt() + 1, ShortArray((noun.toInt() + 1) * (noun.toInt() + 1))),
                File(directory, "connectionId.dat").path,
            )
            val engine = KanaKanjiEngine().apply {
                buildEngineFromResourceDirectory(directory.path, mode = 1, additionalResourceDirectories = extras)
            }
            val candidates = engine.nBestPath("すわいぷ", 3)
            assertEquals("スワイプ", candidates.first())
            assertEquals(setOf("スワイプ", "Swip", "Swipe"), candidates.toSet())
            assertEquals("スワイプする", engine.nBestPath("すわいぷする", 1).single())
            assertTrue("Swipする" in engine.nBestPath("すわいぷする", 3))
            assertEquals("スワイプする", engine.convert("すわいぷする").value)
        } finally {
            directory.deleteRecursively()
        }
    }
}
