package com.kazumaproject.ngram

import SingleNodeUnigramDictionary

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
        mapOf(
            "てのきせき" to "手の軌跡",
            "しゃりんのきせき" to "車輪の軌跡",
            "だんどうのきせき" to "弾道の軌跡",
            "ぼーるのきせき" to "ボールの軌跡",
            "だきゅうのきせき" to "打球の軌跡",
            "ひこうきのきせき" to "飛行機の軌跡",
            "えいせいのきせき" to "衛星の軌跡",
            "きせきをえがく" to "軌跡を描く",
            "きせきをたどる" to "軌跡をたどる",
            "きせきをおう" to "軌跡を追う",
            "きせきをのこす" to "軌跡を残す",
            "きせきがのこる" to "軌跡が残る",
            "きせきにそって" to "軌跡に沿って",
        ).forEach { (input, expected) ->
            assertEquals(expected, engine.nBestPath(input, 1).single(), input)
        }
        assertEquals("ドーハの奇跡", engine.nBestPath("どーはのきせき", 1).single())
    }

    @Test
    fun exactPhraseCandidateRemainsFirstWhenSystemNgramRerankingIsEnabled() {
        val root = File(System.getProperty("user.dir"))
        val output = createTempDirectory("system-ngram-exact-phrase").resolve("system_ngram.dat").toFile()
        SystemNgramBinaryBuilder.build(
            rules = NgramSourceParser.parseDirectory(root.resolve("src/main/ngram")),
            idDef = root.resolve("src/main/resources/id.def"),
            output = output,
        )
        val dictionary = PackedSystemNgramDictionary.fromFile(output)
        val engine = KanaKanjiEngine(systemNgramDictionary = dictionary).apply { buildEngine() }

        assertTrue(engine.nBestPath("とはなに", 1).single() in setOf("とはなに", "とは何"))
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

        assertEquals(473, dictionary.ruleCount)
        assertTrue(dictionary.matches(node("カワボ")))
        assertFalse(dictionary.matches(node("存在しない候補")))
        val engine = KanaKanjiEngine(systemUnigramDictionary = dictionary).apply { buildEngine() }
        assertEquals("カワボ", engine.nBestPath("かわぼ", 1).single())
    }

    @Test
    fun standaloneHiraganaRulesMatchJapaneseKeyboardSingleNodePolicy() {
        val root = File(System.getProperty("user.dir"))
        val output = createTempDirectory("standalone-hiragana").resolve("system_ngram_unigram.dat").toFile()
        SystemNgramBinaryBuilder.build(
            rules = NgramSourceParser.parseUnigramDirectory(root.resolve("src/main/ngram-unigram")),
            idDef = root.resolve("src/main/resources/id.def"),
            output = output,
            formatVersion = NgramEncoding.UNIGRAM_VERSION,
        )
        val dictionary = SingleNodeUnigramDictionary(PackedSystemUnigramDictionary.fromFile(output))
        val engine = KanaKanjiEngine(systemUnigramDictionary = dictionary).apply { buildEngine() }
        val baseline = KanaKanjiEngine().apply { buildEngine() }

        mapOf("なのか" to "七日", "しろ" to "白").forEach { (input, alternative) ->
            dictionary.inputLength = input.length
            assertEquals(listOf(input), engine.nBestPath(input, 1))
            val candidates = engine.nBestPath(input, 10)
            assertEquals(input, candidates.first())
            assertEquals(1, candidates.count { it == input })
            assertTrue(alternative in candidates)
            assertEquals(emptyList(), engine.nBestPath(input, 0))
        }

        listOf("しろい", "しろくろ", "しろあり", "しろのなか", "なのかな", "なのかもしれない")
            .forEach { input ->
                dictionary.inputLength = input.length
                assertEquals(baseline.nBestPath(input, 10), engine.nBestPath(input, 10), input)
            }

        dictionary.inputLength = 3
        assertFalse(dictionary.matches(node("しろ").copy(len = 2)))
        assertFalse(dictionary.matches(node("しろ").copy(len = 3, sPos = 1)))
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
