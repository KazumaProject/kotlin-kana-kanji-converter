package com.kazumaproject.ngram

import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.graph.Node
import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SystemNgramRuntimeTest {
    @Test
    fun packedNgramDictionaryReranksTrajectoryCandidatesUsingCheckedInRules() {
        val root = File(System.getProperty("user.dir"))
        val output = createTempDirectory("system-ngram-runtime").resolve("system_ngram.dat").toFile()
        SystemNgramBinaryBuilder.build(
            rules = NgramSourceParser.parseDirectory(root.resolve("src/main/ngram")),
            idDef = root.resolve("src/main/resources/id.def"),
            output = output,
        )
        val dictionary = PackedSystemNgramDictionary.fromFile(output)
        assertTrue(dictionary.matches(node("指"), node("の"), node("軌跡"), null, null))
        assertFalse(dictionary.matches(node("動く", contextId = 434), node("の"), node("軌跡"), null, null))

        val baselineEngine = KanaKanjiEngine().apply { buildEngine() }
        assertEquals("指の奇跡", baselineEngine.nBestPath("ゆびのきせき", 1).single())
        val engine = KanaKanjiEngine(systemNgramDictionary = dictionary).apply { buildEngine() }

        assertEquals("指の軌跡", engine.nBestPath("ゆびのきせき", 1).single())
        assertEquals("タイヤの軌跡", engine.nBestPath("たいやのきせき", 1).single())
        assertEquals("軌跡に沿って", engine.nBestPath("きせきにそって", 1).single())
    }

    @Test
    fun packedUnigramDictionaryReranksAnExistingOneNodeCandidate() {
        val root = File(System.getProperty("user.dir"))
        val source = createTempDirectory("system-unigram-runtime").toFile()
        source.resolve("trajectory.ngram").writeText("\"軌跡\"\n")
        val output = source.resolve("system_ngram_unigram.dat")
        SystemNgramBinaryBuilder.build(
            rules = NgramSourceParser.parseUnigramDirectory(source),
            idDef = root.resolve("src/main/resources/id.def"),
            output = output,
            formatVersion = NgramEncoding.UNIGRAM_VERSION,
        )
        val dictionary = PackedSystemUnigramDictionary.fromFile(output)
        val engine = KanaKanjiEngine(systemUnigramDictionary = dictionary).apply { buildEngine() }

        assertEquals("軌跡", engine.nBestPath("きせき", 1).single())
    }

    @Test
    fun packedReadersMatchTheCheckedInAtokUnigramAssetSource() {
        val root = File(System.getProperty("user.dir"))
        val output = createTempDirectory("atok-unigram-runtime").resolve("system_ngram_unigram.dat").toFile()
        SystemNgramBinaryBuilder.build(
            rules = NgramSourceParser.parseUnigramDirectory(root.resolve("src/main/ngram-unigram")),
            idDef = root.resolve("src/main/resources/id.def"),
            output = output,
            formatVersion = NgramEncoding.UNIGRAM_VERSION,
        )
        val dictionary = PackedSystemUnigramDictionary.fromFile(output)

        assertEquals(471, dictionary.ruleCount)
        assertTrue(dictionary.matches(node("カワボ")))
        assertFalse(dictionary.matches(node("存在しない候補")))
        val engine = KanaKanjiEngine(systemUnigramDictionary = dictionary).apply { buildEngine() }
        assertEquals("カワボ", engine.nBestPath("かわぼ", 1).single())
    }

    private fun node(tango: String, contextId: Int = 1851): Node = Node(
        l = contextId.toShort(),
        r = contextId.toShort(),
        score = 0,
        f = 0,
        tango = tango,
        len = 1,
        sPos = 0,
    )
}
