package specialist

import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.classification.DictionaryFilter
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.specialist.effectiveSurface
import com.kazumaproject.specialist.pairKey
import com.kazumaproject.specialist.restoredSurface
import com.kazumaproject.specialist.writeInventory
import java.io.File
import java.nio.file.Files
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream
import kotlin.test.*

class SpecialistDictionaryTest {
    @Test
    fun inventoryUsesEncodedKanaSurfaceAndIgnoresPosAndCost() {
        val root = Files.createTempDirectory("specialist-inventory").toFile()
        try {
            fun entry(reading: String, surface: String, cost: Short = 9000) = Dictionary(reading, 1, 1, cost, surface)
            assertEquals("ろ", effectiveSurface(entry("ろ", "ひらがな")))
            assertEquals("ロ", effectiveSurface(entry("ろ", "ローマ")))
            assertEquals("がん", effectiveSurface(entry("がん", "か\u3099ん")))
            assertEquals("エー", effectiveSurface(entry("えー", "E\u0301"), setOf("E\u0301")))
            assertEquals("É", effectiveSurface(entry("えー", "E\u0301"), setOf("E\u0301", "É")))
            val entries = listOf(entry("がん", "癌"), entry("がん", "癌", 100), entry("ろ", "ローマ"), entry("か", "甲\t説明"))
            val a = File(root, "a.gz"); val b = File(root, "b.gz")
            writeInventory(mapOf("system" to entries), a)
            writeInventory(mapOf("system" to entries.reversed()), b)
            assertContentEquals(a.readBytes(), b.readBytes())
            val text = GZIPInputStream(a.inputStream()).bufferedReader().use { it.readText() }
            assertEquals(3, text.lines().count { it.isNotBlank() })
            assertTrue("\\t説明" in text)
            assertTrue("\"surface\":\"ロ\"" in text)
        } finally { root.deleteRecursively() }
    }

    @Test
    fun duplicateKeyKeepsWidthCaseAndVariantDifferencesInSurface() {
        assertEquals("がん" to "癌", pairKey(" ｶﾞﾝ ", " 癌 "))
        assertEquals(pairKey("ガン", "癌"), pairKey("がん", "癌"))
        assertNotEquals(pairKey("えーびー", "ＡＢ"), pairKey("えーびー", "AB"))
        assertNotEquals(pairKey("えーびー", "Ab"), pairKey("えーびー", "AB"))
        assertNotEquals(pairKey("がん", "癌"), pairKey("かん", "癌"))
    }

    @Test
    fun reconstructedSurfaceUsesCurrentSentinelsAndLiteralNodes() {
        val tree = PrefixTree().apply { insert("癌") }
        val tango = Converter().convert(tree.root).apply { convertListToBitSet() }
        assertEquals("癌", restoredSurface("がん", tango.getNodeIndex("癌"), tango))
        assertEquals("がん", restoredSurface("がん", -2, tango))
        assertEquals("ガン", restoredSurface("がん", -1, tango))
        assertEquals("ゔ", restoredSurface("ゔ", -1, tango))
    }

    @Test
    fun specialistCategoriesUseSharedNounPosAndBuildDistinctFiles() {
        val root = Files.createTempDirectory("specialist-categories").toFile()
        try {
            File(root, "categories.json").writeText("""{"categories":[{"id":"kampo"},{"id":"medical"}]}""")
            val id = File(root, "id.def").apply { writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n") }
            GZIPOutputStream(File(root, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
                it.write("kampo\tかっこんとう\t1\t1\t9000\t葛根湯\nmedical\tがん\t1\t1\t9000\t癌\n")
            }
            val data = ClassifiedDictionaryData(root, id, expectedCategoryCount = 2, dictionaryFilter = DictionaryFilter.empty())
            val posInput = data.records.values.flatten().groupBy { it.yomi }.toSortedMap()
            val pos = File(root, "pos.dat")
            TokenArray().buildPOSTableWithIndex(posInput, 1, pos.path)
            data.build(File(root, "assets"), pos.path)
            data.categoryIds.forEach { category ->
                listOf("yomi", "tango", "token").forEach { assertTrue(File(root, "assets/$category/$it.dat").length() > 0) }
            }
            assertEquals(1, data.records.getValue("kampo").size)
            assertEquals(1, data.records.getValue("medical").size)
        } finally { root.deleteRecursively() }
    }
}
