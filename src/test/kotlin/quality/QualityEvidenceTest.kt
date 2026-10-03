package quality

import com.kazumaproject.quality.*
import com.kazumaproject.dictionary.models.Dictionary
import kotlinx.serialization.json.*
import java.nio.file.Files
import kotlin.test.*

class QualityEvidenceTest {
    @Test fun verifiesAliasesSeparatelyAndDoesNotLetAnUnrelatedReadingVetoMozc() {
        val dir=Files.createTempDirectory("pair-proof-").toFile()
        try {
            val entity=buildJsonObject {
                put("id","Q100");put("labels",buildJsonObject { put("ja",buildJsonObject { put("value","本名") }) })
                put("aliases",buildJsonObject { put("ja",buildJsonArray { add(buildJsonObject { put("value","ニック") });add(buildJsonObject { put("value","別名") }) }) })
                put("sitelinks",buildJsonObject { put("jawiki",buildJsonObject { put("title","本名") }) })
                put("claims",buildJsonObject {
                    put("P31",buildJsonArray { add(buildJsonObject { put("mainsnak",buildJsonObject { put("datavalue",buildJsonObject { put("value",buildJsonObject { put("id","Q5") }) }) }) }) })
                    put("P1814",buildJsonArray { add(buildJsonObject { put("mainsnak",buildJsonObject { put("datavalue",buildJsonObject { put("value","ほんみょう") }) }) }) })
                })
            }
            MetadataCatalog(cacheFile=dir.resolve("cache.sqlite"),apiBudget=1,transport={ buildJsonObject { put("entities",buildJsonObject { put("Q100",entity) }) } }).use { catalog ->
                catalog.prepare(listOf("本名","ニック","別名"))
                val lexical=LexicalEvidence(listOf(LexicalFact("にっく","ニック",setOf("person"),"https://example.test/official-alias")))
                val quality=QualityEvaluator(catalog,mapOf("別名" to setOf("べつめい")),lexical)
                fun row(y:String,s:String)=SourceRow("wiki",1,Dictionary(y,1,1,10,s))
                assertEquals("accepted",quality.evaluate(row("にっく","ニック")).state)
                assertEquals("accepted",quality.evaluate(row("べつめい","別名")).state)
                assertEquals("held",QualityEvaluator(catalog,emptyMap(),LexicalEvidence()).evaluate(row("にっく","ニック")).state)
                assertEquals(setOf("unclassified"),SemanticClassifier(catalog).classify(row("にっく","ニック"),true).categories)
                assertEquals(setOf("person"),lexical.facts("にっく","ニック").single().categories)
                assertEquals("held",quality.evaluate(row("まちがい","本名")).state)
                assertEquals("held",quality.evaluate(row("ほんみょう","別名")).state)
                assertEquals(setOf("unclassified"),SemanticClassifier(catalog).classify(row("まちがい","本名"),true).categories)
                val parsed=catalog.entity("Q100")!!
                assertEquals(setOf("alias:ja"),parsed.nameKinds["ニック"])
                assertEquals(setOf("本名"),parsed.readingNames)
            }
        } finally { dir.deleteRecursively() }
    }
    @Test fun writtenVariantsDoNotTransferReadingToDifferentNames() {
        val entity=MetadataEntity("Q1",setOf("斬 歌舞伎","斬歌舞伎","別名","OUTRAGE","Outrage","三田文學","三田文学"),emptySet(),emptySet(),setOf("ざんかぶき"),readingNames=setOf("斬 歌舞伎","Outrage","三田文学"))
        assertTrue(entity.readingAppliesTo("斬歌舞伎"))
        assertTrue(entity.readingAppliesTo("OUTRAGE"))
        assertTrue(entity.readingAppliesTo("三田文學"))
        assertFalse(entity.readingAppliesTo("別名"))
        assertFalse(entity.readingAppliesTo("斬歌舞伎(舞台)"))
    }
    @Test fun qualifiedReadingBelongsOnlyToItsSpecifiedName() {
        val e=MetadataEntity("Q1",setOf("本名","別名"),emptySet(),emptySet(),setOf("ほんみょう","べつめい"),readingNames=setOf("本名"),readingPairs=mapOf("別名" to setOf("べつめい")),primaryReadings=setOf("ほんみょう"))
        assertEquals(setOf("ほんみょう"),e.readingsFor("本名"))
        assertEquals(setOf("べつめい"),e.readingsFor("別名"))
        assertEquals(emptySet(),e.readingsFor("無関係"))
        val parsed=MetadataCatalog.parseEntity(Json.parseToJsonElement("""{"id":"Q1","labels":{"ja":{"value":"本名"}},"claims":{"P1814":[{"mainsnak":{"datavalue":{"value":"べつめい"}},"qualifiers":{"P5168":[{"datavalue":{"value":{"text":"別名","language":"ja"}}}]}}]}}"""))!!
        assertEquals(setOf("べつめい"),parsed.readingsFor("別名"))
        assertEquals(emptySet(),parsed.readingsFor("本名"))
    }
    @Test fun kanaEqualityRequiresIndependentExistenceAndLexicalProofDoesNotInventCategory() {
        val dir=Files.createTempDirectory("unattested-").toFile()
        try { MetadataCatalog(cacheFile=dir.resolve("cache.sqlite"),offline=true).use { catalog ->
            val row=SourceRow("neologd",1,Dictionary("かにぱん",1,1,10,"かにぱん"))
            assertEquals("held",QualityEvaluator(catalog,emptyMap(),LexicalEvidence()).evaluate(row).state)
            val lexical=LexicalEvidence(listOf(LexicalFact("かにぱん","かにぱん",emptySet(),"https://example.test/proof")))
            assertEquals("accepted",QualityEvaluator(catalog,emptyMap(),lexical).evaluate(row).state)
            assertEquals(setOf("unclassified"),SemanticClassifier(catalog).classify(row).categories)
        } } finally { dir.deleteRecursively() }
    }
}
