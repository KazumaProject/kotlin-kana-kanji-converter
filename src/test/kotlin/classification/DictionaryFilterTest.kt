package classification

import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.classification.DictionaryFilter
import com.kazumaproject.classification.PersonDictionaryData
import com.kazumaproject.dictionary.models.Dictionary
import java.io.File
import java.nio.file.Files
import java.util.zip.GZIPOutputStream
import kotlin.test.*

class DictionaryFilterTest {
    private fun fixture(test: (File, DictionaryFilter) -> Unit) {
        val root = Files.createTempDirectory("dictionary-filter-test").toFile()
        try {
            File(root, "manifest.json").writeText("""{"schemaVersion":1}""")
            File(root, "snapshot.json").writeText(
                """{"schemaVersion":1,"repository":"KazumaProject/dictionary_filter_list","revision":"${"a".repeat(40)}"}""",
            )
            val category = File(root, "categories/person/test.jsonl")
            category.parentFile.mkdirs()
            category.writeText(
                """{"reading":"かな","surface":"仮名","status":"hold","evidence":[{"kind":"test"}]}""" + "\n" +
                    """{"reading":"よみ","surface":"よみ","status":"hold","evidence":[{"kind":"test"}]}""" + "\n",
            )
            test(root, DictionaryFilter.load(root))
        } finally {
            root.deleteRecursively()
        }
    }

    private fun word(reading: String, surface: String, cost: Int = 100): Dictionary =
        Dictionary(reading, 1, 1, cost.toShort(), surface)

    @Test
    fun matchesExactPairAcrossPosVariantsAndReconstructedKanaSurface() = fixture { _, filter ->
        val entries = listOf(
            word("かな", "仮名"), word("かな", "仮名", 200),
            word("かな", "佳奈"), word("かめ", "仮名"), word("よみ", "かな"),
        )
        val retained = filter.filterRecords(entries)
        assertEquals(listOf(word("かな", "佳奈"), word("かめ", "仮名")), retained)
        assertFalse(filter.contains("かめ", "仮名"))
    }

    @Test
    fun filteredPairsAreRemovedFromEveryClassifiedCategory() = fixture { root, filter ->
        val source = File(root, "classified").apply { mkdirs() }
        File(source, "categories.json").writeText("""{"categories":[{"id":"person"},{"id":"place"}]}""")
        val id = File(root, "id.def").apply { writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n") }
        GZIPOutputStream(File(source, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
            it.write("person\tかな\t1\t1\t100\t仮名\n")
            it.write("place\tかな\t1\t1\t200\t仮名\n")
            it.write("place\tかな\t1\t1\t100\t佳奈\n")
        }
        val data = ClassifiedDictionaryData(source, id, dictionaryFilter = filter)
        assertTrue(data.records.getValue("person").isEmpty())
        assertEquals(setOf(word("かな", "佳奈")), data.records.getValue("place"))
    }

    @Test
    fun personSourceFiltersBeforeCreatingCategoryRecords() = fixture { root, filter ->
        val source = File(root, "person-source").apply { mkdirs() }
        File("src/main/classification/person-taxonomy.json").copyTo(File(source, "person-taxonomy.json"))
        File(source, "crime-offender-exclusion-keys.sha256").writeText("0".repeat(64) + "\n")
        val id = File(root, "id.def").apply { writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n") }
        GZIPOutputStream(File(source, "person-dictionary-candidates.tsv.gz").outputStream()).bufferedWriter().use {
            it.write("actor\tかな\t1\t1\t100\t仮名\t\n")
            it.write("personal_name_origin_unconfirmed\tかな\t1\t1\t100\t佳奈\t\n")
        }
        val data = PersonDictionaryData(source, id, filter)
        assertTrue(data.records.getValue("actor").isEmpty())
        assertEquals(listOf(word("かな", "佳奈")), data.records.getValue("personal_name_origin_unconfirmed"))
    }

    @Test
    fun invalidOrDuplicateRecordsFailClosed() = fixture { root, _ ->
        val category = File(root, "categories/person/test.jsonl")
        category.appendText(category.readLines().first() + "\n")
        assertFailsWith<IllegalArgumentException> { DictionaryFilter.load(root) }
        File(root, "snapshot.json").delete()
        assertFails { DictionaryFilter.load(root) }
    }
}
