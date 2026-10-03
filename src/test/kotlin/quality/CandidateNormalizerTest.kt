package quality

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.quality.*
import kotlin.test.*

class CandidateNormalizerTest {
    private val normalizer = CandidateNormalizer(mapOf("赤坂" to setOf("あかさか"), "渋谷" to setOf("しぶや"), "藍畑" to setOf("あいはた"), "高畑" to setOf("たかばたけ", "たかはた", "たかばた")))
    private fun row(reading: String, surface: String, source: String = "place") = SourceRow(source, 1, Dictionary(reading, 1, 1, 8000, surface))
    @Test fun splitsSpellingAndReadingTogether() {
        val result = normalizer.normalize(row("あいはたたかばたけ", "藍畑(高畑)"))
        assertEquals(listOf("あいはた" to "藍畑", "たかばたけ" to "高畑"), result.entries.map { it.yomi to it.tango })
        assertEquals(result.entries, normalizer.normalize(row("あいはたたかばたけ", "藍畑（高畑）")).entries)
    }
    @Test fun removesFloorAndPostalConcatenation() {
        val result = normalizer.normalize(row("あかさかあかさかとらすとたわーさんじゅういちかい", "赤坂赤坂トラストタワー(31階)"))
        assertEquals(listOf("あかさかとらすとたわー" to "赤坂トラストタワー"), result.entries.map { it.yomi to it.tango })
        assertTrue(result.reason.startsWith("canonical-building:"))
        assertEquals(listOf("藍畑"), normalizer.normalize(row("あいはたいっかい", "藍畑(1階)")).entries.map { it.tango })
    }
    @Test fun preservesLegitimateParenthesesAndRepeatedWords() {
        val work = row("みていかり", "未定(仮)", "wiki")
        assertEquals(listOf(work.word), normalizer.normalize(work).entries)
        val repeated = row("ささ", "佐々")
        assertEquals(listOf(repeated.word), normalizer.normalize(repeated).entries)
    }
    @Test fun holdsMalformedOrAmbiguousRows() {
        listOf("藍畑(高畑", "藍畑高畑)", "藍畑((高畑))", "藍畑(高畑)住所").forEach {
            assertTrue(normalizer.normalize(row("あいはたたかばたけ", it)).entries.isEmpty())
        }
        assertTrue(normalizer.normalize(row("なぞたかばたけ", "謎(高畑)")).entries.isEmpty())
        val ambiguous = CandidateNormalizer(mapOf("町" to setOf("まち", "まちも")))
        assertTrue(ambiguous.normalize(row("まちもも", "町(桃)")).entries.isEmpty())
    }
    @Test fun preservesNumericPlaceAndRepairsConfirmedBuildings() {
        assertEquals(listOf("藍畑", "第十"), normalizer.normalize(row("あいはただいじゅう", "藍畑(第十)")).entries.map { it.tango })
        assertEquals(listOf("赤坂Bizタワー"), normalizer.normalize(row("あかさかあかさかびずたわー", "赤坂赤坂Bizタワー")).entries.map { it.tango })
        assertEquals(listOf("渋谷スクランブルスクエア"), normalizer.normalize(row("しぶやしぶやすくらんぶるすくえあ", "渋谷渋谷スクランブルスクエア")).entries.map { it.tango })
        listOf("市原市原田", "一円", "明野ハイツ").forEach { surface -> assertEquals(surface, normalizer.normalize(row("よみ", surface)).entries.single().tango) }
        assertEquals("excluded", normalizer.normalize(row("よみ", "岡谷市岡谷市の次に番地がくる場合")).state)
        assertEquals("held", normalizer.normalize(row("なぞまちなぞまちたわー", "謎町謎町タワー")).state)
    }
    @Test fun repairsRepeatedTownInMiddleOnlyWithCanonicalEvidence() {
        val lexical = LexicalEvidence(listOf(LexicalFact("なかのしまだいびる", "中之島ダイビル", setOf("facility"), "https://example.org/building")))
        val cleaner = CandidateNormalizer(mapOf("大阪市北区中之島" to setOf("おおさかしきたくなかのしま")), lexical = lexical)
        assertEquals("中之島ダイビル", cleaner.normalize(row("おおさかしきたくなかのしまなかのしまだいびる", "大阪市北区中之島中之島ダイビル")).entries.single().tango)
        assertTrue(cleaner.normalize(row("おおさかしきたくなかのしままちがい", "大阪市北区中之島中之島ダイビル")).entries.isEmpty())
    }
    @Test fun neverEmitsAnnotationAsPlace() {
        assertEquals(listOf("藍畑"), normalizer.normalize(row("あいはたちょうめ", "藍畑(丁目)")).entries.map { it.tango })
    }
    @Test fun keepsAttestedRepeatedFacilityHeadWhenRemovingFloor() {
        val facts = LexicalEvidence(listOf(
            LexicalFact("ひがしまちひがしまちたわー", "東町東町タワー", setOf("facility"), "https://example.org/full-name"),
            LexicalFact("ひがしまちたわー", "東町タワー", setOf("facility"), "https://example.org/short-name"),
        ))
        val cleaner = CandidateNormalizer(mapOf("東町" to setOf("ひがしまち")), lexical = facts)
        val result = cleaner.normalize(row("ひがしまちひがしまちたわーさんじゅういちかい", "東町東町タワー(31階)"))
        assertEquals(listOf("ひがしまちひがしまちたわー" to "東町東町タワー"), result.entries.map { it.yomi to it.tango })
    }
}
