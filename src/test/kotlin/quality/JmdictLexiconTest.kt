package quality

import com.kazumaproject.quality.*
import java.nio.file.Files
import kotlin.test.*

class JmdictLexiconTest {
    private fun read(xml: String, wanted: Set<Pair<String,String>>): List<LexicalFact> {
        val file = Files.createTempFile("lexical-test-", ".xml").toFile()
        return try { file.writeText(xml); buildList { JmdictLexicon.read(file,wanted) { add(it) } } } finally { file.delete() }
    }
    @Test fun respectsSpellingReadingAndSenseRestrictionsAndInheritance() {
        val xml = """<JMdict><entry><ent_seq>1</ent_seq>
            <k_ele><keb>甲</keb></k_ele><k_ele><keb>乙</keb></k_ele>
            <r_ele><reb>こう</reb><re_restr>甲</re_restr></r_ele><r_ele><reb>おつ</reb><re_restr>乙</re_restr></r_ele>
            <sense><stagk>甲</stagk><stagr>こう</stagr><pos>n</pos></sense>
            <sense><stagk>乙</stagk><stagr>おつ</stagr><field>food</field></sense></entry></JMdict>"""
        val facts = read(xml,setOf("こう" to "甲","こう" to "乙","おつ" to "乙","おつ" to "甲","こう" to "追加語"))
        assertEquals(setOf("こう" to "甲","おつ" to "乙"),facts.map { it.reading to it.surface }.toSet())
        assertEquals(setOf("general"),facts.single { it.surface=="甲" }.categories)
        assertEquals(setOf("food"),facts.single { it.surface=="乙" }.categories)
        assertEquals(setOf("n"),facts.single { it.surface=="乙" }.pos)
    }
    @Test fun kanaOnlyReadingIsNotCrossedWithKanjiAndNamesAreNotGeneral() {
        val xml = """<JMdict><entry><ent_seq>2</ent_seq><k_ele><keb>架空</keb></k_ele>
            <r_ele><reb>かな</reb><re_nokanji/></r_ele><sense><pos>n</pos><misc>work</misc></sense>
            <sense><field>comp</field></sense></entry></JMdict>"""
        val facts=read(xml,setOf("かな" to "架空","かな" to "かな"))
        assertTrue(facts.all { it.surface=="かな" && "general" !in it.categories })
        assertEquals(setOf("work","technical"),facts.flatMap { it.categories }.toSet())
    }
    @Test fun obsoleteSpellingAndExternalEntitiesAreRejected() {
        val xml="""<JMdict><entry><ent_seq>3</ent_seq><k_ele><keb>舊</keb><ke_inf>oK</ke_inf></k_ele><r_ele><reb>きゅう</reb></r_ele><sense><pos>n</pos></sense></entry></JMdict>"""
        assertTrue(read(xml,setOf("きゅう" to "舊")).isEmpty())
        assertFails { read("""<!DOCTYPE JMdict SYSTEM "file:///etc/passwd"><JMdict/>""",emptySet()) }
    }
    @Test fun parsesInternalTagsButDoesNotTreatAllNounsAsGeneral() {
        val xml="""<!DOCTYPE JMdict [<!ENTITY n "noun"><!ENTITY comp "computing">]><JMdict><entry><ent_seq>4</ent_seq><r_ele><reb>アルゴリズム</reb></r_ele><sense><pos>&n;</pos><field>&comp;</field></sense></entry></JMdict>"""
        val fact=read(xml,setOf("あるごりずむ" to "アルゴリズム")).single()
        assertEquals(setOf("technical"),fact.categories)
        assertEquals(setOf("comp"),fact.fields)
        assertEquals("4",fact.entryId)
    }
    @Test fun resolvesFieldsAfterLargeInternalDtdComments() {
        val comment="x".repeat(100000)
        val xml="""<!DOCTYPE JMdict [<!--$comment--><!ENTITY n "noun"><!ENTITY med "medicine">]><JMdict><entry><ent_seq>5</ent_seq><r_ele><reb>いりょう</reb></r_ele><sense><pos>&n;</pos><field>&med;</field></sense></entry></JMdict>"""
        val fact=read(xml,setOf("いりょう" to "いりょう")).single()
        assertEquals(setOf("med"),fact.fields)
        assertEquals(setOf("technical"),fact.categories)
    }

    @Test fun reviewedSenseFixDoesNotCarryIncorrectProductTagToTextTitle() {
        val xml="""<JMdict><entry><ent_seq>5708730</ent_seq><k_ele><keb>臨済録</keb></k_ele><r_ele><reb>りんざいろく</reb></r_ele><sense><pos>n</pos><misc>product</misc><gloss>Linji-lu (Tang-era Buddhist text)</gloss></sense></entry></JMdict>"""
        val fact=read(xml,setOf("りんざいろく" to "臨済録")).single()
        assertEquals(setOf("work"),fact.categories)
        assertEquals(listOf("Linji-lu (Tang-era Buddhist text)"),fact.glosses)
    }

}
