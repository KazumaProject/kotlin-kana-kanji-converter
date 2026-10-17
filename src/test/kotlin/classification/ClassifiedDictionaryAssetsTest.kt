package classification

import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.dictionary.TokenArray
import java.io.File
import java.io.ObjectOutputStream
import java.nio.file.Files
import java.util.zip.*
import kotlin.test.*

class ClassifiedDictionaryAssetsTest {
    @Test
    fun frozenReviewAdmitsUzumakiBorutoAndExcludesReportedFragments() {
        val data = ClassifiedDictionaryData()
        val name = data.records.getValue("character").single {
            it.yomi == "うずまきぼると" && it.tango == "うずまきボルト"
        }
        assertEquals(1851.toShort(), name.leftId)
        assertEquals(1851.toShort(), name.rightId)
        assertEquals(8400.toShort(), name.cost)
        val reported = setOf("淋蒔", "うず巻", "UZUMAKI")
        assertFalse(data.records.values.flatten().any { it.yomi == "うずまき" && it.tango in reported })
    }

    private fun fixture(test: (File, ClassifiedDictionaryData, File) -> Unit) {
        val root = Files.createTempDirectory("category-assets-test").toFile()
        try {
            File("src/main/classification/categories.json").copyTo(File(root, "categories.json"))
            val id = File(root, "id.def").apply { writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n") }
            GZIPOutputStream(File(root, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
                it.write("person\tあ\t1\t1\t100\t甲\n")
                it.write("person\tあ\t1\t1\t200\t乙\n")
                it.write("person\tあい\t1\t1\t300\tアイ\n")
                it.write("place\tあ\t1\t1\t100\t甲\n")
                it.write("work_other\tそらとぶいえ\t1\t1\t8400\t空とぶ家\n")
                it.write("work_other\tそらとぶいえ\t1\t1\t8500\t空とぶ家\n")
            }
            val data = ClassifiedDictionaryData(root, id)
            val posInput = data.records.values.flatten().groupBy { it.yomi }.toSortedMap()
            TokenArray().buildPOSTable(posInput, 1, File(root, "pos_table.dat").path)
            TokenArray().buildPOSTableWithIndex(posInput, 1, File(root, "pos_build.dat").path)
            data.build(File(root, "binaries"), File(root, "pos_build.dat").path)
            test(root, data, id)
        } finally {
            root.deleteRecursively()
        }
    }

    private fun archive(root: File, data: ClassifiedDictionaryData): File {
        val archive = File(root, "distribution.zip")
        ZipOutputStream(archive.outputStream()).use { out ->
            fun add(name: String, bytes: ByteArray) {
                out.putNextEntry(ZipEntry("app/src/main/assets/$name"))
                out.write(bytes)
                out.closeEntry()
            }
            fun nested(name: String, bytes: ByteArray): ByteArray {
                val buffer = java.io.ByteArrayOutputStream()
                ZipOutputStream(buffer).use { zip ->
                    zip.putNextEntry(ZipEntry(name)); zip.write(bytes); zip.closeEntry()
                }
                return buffer.toByteArray()
            }
            add("pos_table.dat", File(root, "pos_table.dat").readBytes())
            add("connectionId.dat.zip", nested("connectionId.dat", ByteArray(8)))
            data.categoryIds.forEach { category ->
                listOf("yomi.dat", "tango.dat", "token.dat").forEach { name ->
                    add("categories/$category/$name.zip", nested(name, File(root, "binaries/$category/$name").readBytes()))
                }
            }
        }
        return archive
    }

    @Test
    fun roundTripWithSharedPosMultipleCategoriesPrefixAndEmptyCategories() = fixture { root, data, _ ->
        data.verifyArchive(archive(root, data))
        assertEquals(3, data.records.getValue("person").size)
        assertEquals(1, data.records.getValue("place").size)
        assertTrue(data.records.getValue("work_game").isEmpty())
    }

    @Test
    fun packagedCostsChangeOnceWhileSourceRecordsAndVariantsRemainIntact() = fixture { root, data, _ ->
        val raw = data.records.getValue("work_other")
        assertEquals(setOf<Short>(8400, 8500), raw.map { it.cost }.toSet())
        val tokens = File(root, "binaries/work_other/token.dat")
        val before = tokens.readBytes()
        java.io.ObjectInputStream(tokens.inputStream()).use { input ->
            val array = TokenArray().also { it.readExternalNotCompressStrict(input) }
            assertEquals(listOf<Short>(9900, 10000), array.getListDictionaryByYomiTermId(1).map { it.wordCost })
        }
        data.build(File(root, "binaries"), File(root, "pos_build.dat").path)
        assertContentEquals(before, tokens.readBytes())
        assertEquals(setOf<Short>(8400, 8500), raw.map { it.cost }.toSet())
        data.verifyArchive(archive(root, data))
    }

    @Test
    fun mismatchedCommonPosTableIsRejected() = fixture { root, data, _ ->
        ObjectOutputStream(File(root, "pos_table.dat").outputStream()).use {
            it.writeObject(shortArrayOf(0)); it.writeObject(shortArrayOf(1))
        }
        assertFailsWith<IllegalStateException> { data.verifyArchive(archive(root, data)) }
    }

    @Test
    fun corruptedCategoryBinaryIsRejected() = fixture { root, data, _ ->
        File(root, "binaries/person/token.dat").writeBytes(byteArrayOf(0))
        assertFails { data.verifyArchive(archive(root, data)) }
    }

    @Test
    fun truncatedEmptyCategoryBinaryIsRejected() = fixture { root, data, _ ->
        ObjectOutputStream(File(root, "binaries/work_game/token.dat").outputStream()).close()
        assertFails { data.verifyArchive(archive(root, data)) }
    }

    @Test
    fun invalidPosIdsAreRejected() = fixture { root, _, id ->
        GZIPOutputStream(File(root, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
            it.write("person\tあ\t2\t1\t100\t甲\n")
        }
        assertFailsWith<IllegalArgumentException> { ClassifiedDictionaryData(root, id) }
    }
}
