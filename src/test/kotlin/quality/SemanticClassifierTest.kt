package quality

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.quality.*
import kotlinx.serialization.json.*
import java.nio.file.Files
import kotlin.test.*

class SemanticClassifierTest {
    @Test fun generalMozcPosDoesNotProveMeaning() = withCatalog { classifier ->
        assertEquals(setOf("unclassified"), classify(classifier, "広い概念"))
        val root = Files.createTempDirectory("general-pos-").toFile()
        try {
            MetadataCatalog(cacheFile = root.resolve("cache.sqlite"), offline = true).use { catalog ->
                val classifier = SemanticClassifier(catalog, mapOf(("よみ" to "未知の語") to setOf("general")))
                assertEquals(setOf("unclassified"), classify(classifier, "未知の語"))
            }
        } finally { root.deleteRecursively() }
    }
    @Test fun prefersConcreteTypesAndDoesNotClassifyBuildingsAsWorks() = withCatalog { classifier ->
        assertEquals(setOf("facility"), classify(classifier, "建物"))
        assertEquals(setOf("station"), classify(classifier, "駅"))
        assertEquals(setOf("organization"), classify(classifier, "学校"))
        assertEquals(setOf("place"), classify(classifier, "市"))
        assertEquals(setOf("character"), classify(classifier, "架空人物"))
        assertEquals(setOf("organization"), classify(classifier, "役割未解決"))
    }
    @Test fun specificLanguageAndIndependentServiceRoles() = withCatalog { classifier ->
        assertEquals(setOf("technical"), classify(classifier, "言語"))
        assertEquals(setOf("product", "organization"), classify(classifier, "サービス会社"))
    }
    @Test fun distinctReferentsWithMatchingReadingsCanSupplyMultipleCategories() = withCatalog { classifier ->
        assertEquals(setOf("person", "work"), classify(classifier, "同名"))
        assertEquals(setOf("person"), classify(classifier, "未読同名"))
        assertEquals(setOf("person"), classifier.confirmedCategories(SourceRow("person", 1, Dictionary("よみ", 1, 1, 10, "未読同名"))).categories)
    }
    private fun classify(classifier: SemanticClassifier, name: String) = classifier.classify(SourceRow("wiki", 1, Dictionary("よみ", 1, 1, 10, name))).categories
    private fun withCatalog(block: (SemanticClassifier) -> Unit) {
        val root = Files.createTempDirectory("semantic-classifier-").toFile()
        try {
            val entities = listOf(
                entity("Q100", "建物", listOf("Q41176")), entity("Q101", "駅", listOf("Q55488")),
                entity("Q102", "学校", listOf("Q3914")), entity("Q103", "市", listOf("Q515")),
                entity("Q104", "架空人物", listOf("Q5", "Q95074")), entity("Q105", "役割未解決", listOf("Q3918", "Q41176")),
                entity("Q108", "言語", listOf("Q9143", "Q7397")), entity("Q109", "サービス会社", listOf("Q7397", "Q4830453")),
                entity("Q106", "同名", listOf("Q5")), entity("Q107", "同名", listOf("Q11424")),
                entity("Q110", "未読同名", listOf("Q5")), entity("Q111", "未読同名", listOf("Q515"), reading = null),
                entity("Q112", "広い概念", listOf("Q151885")),
                entity("Q41176", "building type", emptyList(), listOf("Q386724", "Q43229")),
                entity("Q55488", "station type", emptyList(), listOf("Q41176")),
                entity("Q3914", "school type", emptyList(), listOf("Q43229", "Q41176")),
                entity("Q515", "city type", emptyList(), listOf("Q43229")),
            )
            MetadataCatalog(cacheFile = root.resolve("cache.sqlite"), apiBudget = 1, transport = { buildJsonObject {
                put("entities", buildJsonObject { entities.forEach { put(it.getValue("id").jsonPrimitive.content, it) } })
            } }).use { catalog ->
                catalog.prepare(listOf("建物", "駅", "学校", "市", "架空人物", "役割未解決", "同名", "未読同名", "広い概念", "言語", "サービス会社"))
                block(SemanticClassifier(catalog))
            }
        } finally { root.deleteRecursively() }
    }
    private fun entity(id: String, name: String, types: List<String>, parents: List<String> = emptyList(), reading: String? = "よみ") = buildJsonObject {
        put("id", id); put("labels", buildJsonObject { put("ja", buildJsonObject { put("value", name) }) })
        put("sitelinks", buildJsonObject { put("jawiki", buildJsonObject { put("title", name) }) })
        put("claims", buildJsonObject {
            fun relation(values: List<String>) = buildJsonArray { values.forEach { id -> add(buildJsonObject {
                put("mainsnak", buildJsonObject { put("datavalue", buildJsonObject { put("value", buildJsonObject { put("id", id) }) }) })
            }) } }
            put("P31", relation(types)); put("P279", relation(parents))
            if (reading != null) put("P1814", buildJsonArray { add(buildJsonObject { put("mainsnak", buildJsonObject { put("datavalue", buildJsonObject { put("value", reading) }) }) }) })
        })
    }
}
