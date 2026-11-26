package grammar

import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.grammar.*
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.mozc.ConnectionMatrixIO
import createCandidateCliEngineFromResources
import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.*

class GrammarConversionIntegrationTest {
    @Test
    fun ordinaryAndDetailedCandidateRanksMatchOnTheResearchCorpus() {
        val readings = File("docs/grammar-conversion/corpus.txt").readLines()
        assertEquals(readings.distinct(), readings)
        assertTrue(readings.size >= 180)
        for (reading in readings) {
            for (count in listOf(1, 10, 100)) {
                val expected = engine.nBestPath(reading, count)
                val actual = grammar.convert(reading, count)
                assertEquals(expected, actual.candidates.map { it.value }, "$reading / $count")
                assertEquals(engine.convert(reading).value, actual.minimumCostPath?.value, reading)
            }
        }
    }

    @Test
    fun constrainsCopulaButPreservesProhibitionAndConditionalInterpretations() {
        val noun = GrammarSelector(partOfSpeech = "名詞")
        val conditional = GrammarSelector(partOfSpeech = "助動詞", conjugationType = "特殊・ダ", conjugationForm = "仮定形")
        val negativeImperative = GrammarSelector(partOfSpeech = "助詞", subdivisions = listOf("終助詞"))
        for ((input, surface, end) in listOf(
            Triple("いがいな", "意外な", 4), Triple("いがいなけっか", "意外な結果", 4),
            Triple("いがいなもの", "意外なもの", 4), Triple("きれいな", "綺麗な", 4),
            Triple("しずかな", "静かな", 4), Triple("きけんな", "危険な", 4),
        )) {
            val options = grammarOptions(3, end, GrammarSelector(role = GrammarRole.ADJECTIVAL_ATTRIBUTIVE))
            assertTrue(grammar.containsCandidate(input, surface, options), surface)
        }
        val attributive = grammarOptions(3, 4, GrammarSelector(role = GrammarRole.ADJECTIVAL_ATTRIBUTIVE))
        assertTrue("以外な" in engine.nBestPath("いがいな", 100))
        assertFalse(grammar.containsCandidate("いがいな", "以外な", attributive))
        assertFalse(grammar.containsCandidate("いがいなけっか", "以外な結果", attributive))
        assertEquals("意外な", grammar.convert("いがいな", 1, attributive).candidates.single().value)
        assertTrue(grammar.containsCandidate("いがい", "以外", grammarOptions(0, 3, noun)))
        assertTrue(grammar.containsCandidate("いがいなら", "以外なら", grammarOptions(3, 5, conditional)))
        for ((reading, word) in listOf("たべるな" to "食べるな", "いくな" to "行くな", "するな" to "するな")) {
            assertTrue(grammar.containsCandidate(reading, word, grammarOptions(reading.lastIndex, reading.length, negativeImperative)))
        }
    }

    @Test
    fun acceptsDictionaryInflectionEvidenceAndReturnsAlternativeLexemes() {
        assertTrue(grammar.inflect("きる", InflectionForm.TE).map { it.surface }.containsAll(listOf("切って", "着て")))
        assertTrue(grammar.inflect("かえる", InflectionForm.NEGATIVE).map { it.surface }.containsAll(listOf("帰らない", "変えない")))
        val inflected = grammar.inflect("かく", InflectionForm.PAST, "書く")
        assertEquals(listOf("書いた"), inflected.map { it.surface })
        val stem = GrammarSelector(partOfSpeech = "動詞", conjugationType = "五段・カ行イ音便", conjugationForm = "未然形")
        val ending = GrammarSelector(partOfSpeech = "助動詞", conjugationType = "特殊・ナイ", conjugationForm = "基本形")
        val options = GrammarSearchOptions(listOf(
            GrammarConstraint.Span(0, 2, listOf(GrammarInterpretation(stem))),
            GrammarConstraint.Span(2, 4, listOf(GrammarInterpretation(ending))),
        ))
        assertTrue(grammar.containsCandidate("かかない", "書かない", options))
        assertFalse(grammar.containsCandidate("かかない", "蚊かない", options))
    }

    @Test
    fun suppliesParticleConnectionsWithoutForcingOneSurface() {
        val stem = engine.convert("いがいな").bestPath.first().rid.toShort()
        val noun = engine.convert("いがい").bestPath.single().rid.toShort()
        val reading = listOf("な", "の", "に", "は")
        val afterStem = grammar.particleConnections(reading, stem, noun)
        assertTrue(afterStem.any { it.reading == "な" && it.reason == ConnectionReason.ADJECTIVAL_STEM &&
            it.decision == ConnectionDecision.SUPPORTED && it.followingConnectionCost != null })
        val afterNoun = grammar.particleConnections(reading, noun)
        assertTrue(afterNoun.any { it.reading == "な" && it.reason == ConnectionReason.ADJECTIVAL_STEM &&
            it.decision == ConnectionDecision.INCOMPATIBLE })
        assertTrue(afterNoun.filter { it.decision == ConnectionDecision.SUPPORTED }.map { it.reading }
            .containsAll(listOf("に", "の")))
    }

    @Test
    fun metadataIsDeterministicAndChecksBothDictionaryContextAssets() {
        val directory = createTempDirectory("grammar-metadata-test").toFile()
        try {
            val copy = directory.resolve("metadata.dat")
            GrammarMetadata.generate(resources.resolve("id.def"), resources, copy)
            assertContentEquals(metadata.readBytes(), copy.readBytes())
            val matrix = ConnectionMatrixIO.read(resources.resolve("connectionId.dat").toPath())
            val tokens = TokenArray().apply { readPOSTable(1, resources.resolve("pos_table.dat").path) }
            val fingerprints = GrammarMetadata.fingerprints(matrix, tokens)
            for (asset in fingerprints.indices) {
                val bad = fingerprints.mapIndexed { index, bytes -> if (index == asset) ByteArray(32) else bytes }
                assertFailsWith<IllegalArgumentException> {
                    GrammarMetadata.read(copy, bad, matrix.size)
                }
            }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun appliesConstraintsAfterMergingAdditionalDictionaryNodes() {
        val directory = createTempDirectory("grammar-extra-test").toFile()
        try {
            val primary = listOf(Dictionary("しずか", 1, 1, 20, "静か"), Dictionary("な", 2, 2, 0, "な"))
            val additional = listOf(Dictionary("しずかな", 1, 2, -100, "別候補"))
            val all = (primary + additional).groupBy { it.yomi }.toSortedMap()
            val buildPos = directory.resolve("pos_table_for_build.dat")
            TokenArray().apply {
                buildPOSTable(all, mode = 1, outputPath = directory.resolve("pos_table.dat").path)
                buildPOSTableWithIndex(all, mode = 1, outputPath = buildPos.path)
            }
            val extra = directory.resolve("extra").apply { mkdirs() }
            for ((records, target) in listOf(primary to directory, additional to extra)) {
                buildAndWriteDictionaryArtifacts(records.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it })),
                    target.resolve("yomi.dat").path, target.resolve("tango.dat").path, target.resolve("token.dat").path,
                    posTableForBuildPath = buildPos.path)
            }
            ConnectionMatrixIO.writeRaw(ConnectionMatrix(3, ShortArray(9)), directory.resolve("connectionId.dat").toPath())
            val idDef = directory.resolve("id.def").apply {
                writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,形容動詞語幹,*,*,*,*,*\n2 助動詞,*,*,*,特殊・ダ,体言接続,だ\n")
            }
            val grammarFile = directory.resolve("metadata.dat")
            GrammarMetadata.generate(idDef, directory, grammarFile)
            val engine = KanaKanjiEngine().apply {
                buildEngineFromResourceDirectory(directory.path, 1, listOf(extra.path))
            }
            assertEquals("別候補", engine.nBestPath("しずかな", 1).single())
            val augmented = engine.grammar(grammarFile)
            val options = grammarOptions(3, 4, GrammarSelector(role = GrammarRole.ADJECTIVAL_ATTRIBUTIVE))
            assertEquals("静かな", augmented.convert("しずかな", 10, options).candidates.single().value)
            assertFalse(augmented.containsCandidate("しずかな", "別候補", options))
        } finally {
            directory.deleteRecursively()
        }
    }

    private fun grammarOptions(start: Int, end: Int, selector: GrammarSelector) =
        GrammarSearchOptions(listOf(GrammarConstraint.Span(start, end, listOf(GrammarInterpretation(selector)))))

    private companion object {
        val resources = File("src/main/resources")
        val engine by lazy { createCandidateCliEngineFromResources(resources) }
        val metadata by lazy {
            File.createTempFile("grammar-test", ".dat").apply {
                deleteOnExit()
                GrammarMetadata.generate(resources.resolve("id.def"), resources, this)
            }
        }
        val grammar by lazy { engine.grammar(metadata) }
    }
}
