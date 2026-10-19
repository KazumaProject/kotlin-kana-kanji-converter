package classification

import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.classification.personDistributionData
import kotlinx.serialization.json.*
import java.io.File
import java.nio.file.Files
import java.util.zip.GZIPOutputStream
import kotlin.test.*

class PersonDictionaryDistributionTest {
    @Test
    fun activeFactoryUsesReviewedTopologyAndExcludesLegacyAndAdultCategories() {
        val data = personDistributionData()
        val taxonomy = Json.parseToJsonElement(File("src/main/classification/person-taxonomy.json").readText())
            .jsonObject.getValue("categories").jsonArray
            .map { it.jsonObject.getValue("id").jsonPrimitive.content }
        val expectedPersonIds = taxonomy.filterNot { it == "adult_performer" }.map { "person_$it" }.toSet()
        assertEquals(51, data.categoryIds.size)
        assertEquals(expectedPersonIds, data.categoryIds.filter { it.startsWith("person_") }.toSet())
        assertEquals(24, expectedPersonIds.size)
        assertFalse("person" in data.records)
        assertFalse("adult_performer" in data.records)
        assertFalse("person_adult_performer" in data.records)
        assertTrue(data.records.getValue("person_surname").isNotEmpty())
        assertTrue(data.records.getValue("person_given_name").isNotEmpty())
    }

    @Test
    fun originalConstructorStillReadsFrozenBaselineFixtureForSpecialistInventory() {
        val root = Files.createTempDirectory("person-baseline-test").toFile()
        try {
            File("src/main/classification/categories.json").copyTo(File(root, "categories.json"))
            val idDef = File(root, "id.def").apply {
                writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n")
            }
            GZIPOutputStream(File(root, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
                it.write("person\tやまだ\t1\t1\t100\t山田\n")
            }
            val original = ClassifiedDictionaryData(root, idDef)
            assertEquals(28, original.categoryIds.size)
            assertEquals("山田", original.records.getValue("person").single().tango)
            assertFalse(original.categoryIds.any { it.startsWith("person_") })
            assertFailsWith<IllegalArgumentException> { personDistributionData(root, idDef) }
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun activeFactoryPreservesSourcePosAndCostWithoutRewritingNameRows() {
        val root = Files.createTempDirectory("person-curated-test").toFile()
        try {
            File("src/main/classification/person-subclassification/distribution/categories.json")
                .copyTo(File(root, "categories.json"))
            val idDef = File(root, "id.def").apply {
                writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n")
            }
            GZIPOutputStream(File(root, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
                it.write("person_surname\tやまだ\t1\t0\t-100\t山田\n")
                it.write("person_given_name\tたろう\t0\t1\t250\t太郎\n")
            }
            val active = personDistributionData(root, idDef)
            val surname = active.records.getValue("person_surname").single()
            assertEquals(1.toShort(), surname.leftId)
            assertEquals(0.toShort(), surname.rightId)
            assertEquals((-100).toShort(), surname.cost)
            assertEquals(250.toShort(), active.records.getValue("person_given_name").single().cost)
            assertTrue(active.records.getValue("person_actor").isEmpty())
            GZIPOutputStream(File(root, "distribution-candidates.tsv.gz").outputStream()).bufferedWriter().use {
                it.write("person\tやまだ\t1\t1\t100\t山田\n")
            }
            assertFailsWith<IllegalStateException> { personDistributionData(root, idDef) }
        } finally {
            root.deleteRecursively()
        }
    }
}
