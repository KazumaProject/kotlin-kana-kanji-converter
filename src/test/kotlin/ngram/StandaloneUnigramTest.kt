package com.kazumaproject.ngram

import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.viterbi.FindPath
import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class StandaloneUnigramTest {
    private val words = listOf("しろ", "ごと", "したい", "はいる", "みた")
    private val rules = NgramSourceParser.parseUnigramDirectory(File("src/main/ngram-standalone-unigram"))

    private fun binary(version: Int = NgramEncoding.STANDALONE_UNIGRAM_VERSION): ByteArray {
        val directory = createTempDirectory("standalone-unigram").toFile()
        try {
            val output = directory.resolve("dictionary.dat")
            SystemNgramBinaryBuilder.build(rules, File("src/main/resources/id.def"), output, version)
            return output.readBytes()
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun separateAssetContainsExactlyTheFiveRequestedWordsAndBuildsDeterministically() {
        assertEquals(words.toSet(), rules.map { (it.features.single() as NgramFeature.Word).value }.toSet())
        val bytes = binary()
        assertContentEquals(bytes, binary())
        SystemNgramBinaryReader(bytes).verify()
        val dictionary = PackedStandaloneUnigramDictionary.read(bytes)
        assertEquals(5, dictionary.ruleCount)
        words.forEach {
            assertTrue(dictionary.mayMatchInput(it), it)
            assertTrue(dictionary.matches(it, listOf(node(it))), it)
        }
        assertFalse(dictionary.mayMatchInput("しろい"))
        assertFalse(dictionary.mayMatchInput("こと"))
        assertFalse(dictionary.matches("なら", listOf(node("なら"))))
        assertFailsWith<IllegalArgumentException> { PackedSystemUnigramDictionary.read(bytes) }
        assertFailsWith<IllegalArgumentException> { PackedSystemNgramDictionary.read(bytes) }
        assertFailsWith<IllegalArgumentException> { PackedStandaloneUnigramDictionary.read(binary(NgramEncoding.UNIGRAM_VERSION)) }
    }

    @Test
    fun standaloneDictionaryRequiresTheCompleteOriginalInputAndOneNode() {
        val dictionary = PackedStandaloneUnigramDictionary.read(binary())
        assertFalse(dictionary.matches("", emptyList()))
        assertFalse(dictionary.matches("しろ", listOf(node("し"), node("ろ", start = 1))))
        assertFalse(dictionary.matches("しろ", listOf(node("しろ", start = 1))))
        assertFalse(dictionary.matches("しろ", listOf(node("しろ", length = 1))))
        assertFalse(dictionary.matches("こと", listOf(node("ごと"))))
        assertFalse(dictionary.matches("ごと", listOf(node("ごと", reading = "こと"))))
        assertFalse(dictionary.matches("しろい", listOf(node("しろ"), node("医", start = 2, reading = "い"))))
        assertFalse(dictionary.matches("しろくろ", listOf(node("しろ"), node("黒", start = 2, reading = "くろ"))))
        assertFalse(dictionary.matches("しろあり", listOf(node("しろ"), node("蟻", start = 2, reading = "あり"))))
    }

    @Test
    fun pathSearchPromotesStandaloneWordsButRetainsCompoundCostOrdering() {
        val dictionary = PackedStandaloneUnigramDictionary.read(binary())
        words.forEach { word ->
            val nodes = arrayOf(node("別候補", reading = word, cost = 0), node(word, cost = 100))
            assertEquals(listOf(word, "別候補"), candidates(word, dictionary, *nodes), word)
            assertEquals(listOf("別候補", word), candidates(word, EmptyStandaloneUnigramDictionary, *nodes), word)
        }
        listOf("しろい" to "医", "しろくろ" to "黒", "しろあり" to "蟻").forEach { (input, suffix) ->
            val alternative = mapOf("しろい" to "白い", "しろくろ" to "白黒", "しろあり" to "シロアリ").getValue(input)
            val nodes = arrayOf(node(alternative, reading = input, cost = 100), node("しろ", cost = 200),
                node(suffix, start = 2, reading = input.drop(2), cost = 300))
            assertEquals(listOf(alternative, "しろ$suffix"), candidates(input, dictionary, *nodes), input)
        }
        assertEquals(listOf("こと", "ごと"), candidates("こと", dictionary,
            node("こと", cost = 100), node("ごと", cost = 2000)))
        assertEquals(listOf("仕事", "しごと"), candidates("しごと", dictionary,
            node("仕事", reading = "しごと", cost = 0), node("し", cost = 0), node("ごと", start = 1, cost = 100)))
    }

    @Test
    fun laterStandalonePathPromotesTheExistingSurfaceWithoutDuplicatingIt() {
        val dictionary = PackedStandaloneUnigramDictionary.read(binary())
        assertEquals(listOf("したい", "時代"), candidates("したい", dictionary,
            node("時代", reading = "したい", cost = 0), node("し", cost = 0),
            node("たい", start = 1, cost = 10), node("したい", cost = 100)))
    }

    @Test
    fun enginePromotesAllFiveWordsAndPreservesCompoundResults() {
        val dictionary = PackedStandaloneUnigramDictionary.read(binary())
        val engine = KanaKanjiEngine(standaloneUnigramDictionary = dictionary).apply { buildEngine() }
        val baseline = KanaKanjiEngine().apply { buildEngine() }
        words.forEach { input ->
            listOf(1, 4, 10).forEach { count ->
                val candidates = engine.nBestPath(input, count)
                assertEquals(input, candidates.first(), "$input count=$count")
                assertEquals(1, candidates.count { it == input }, input)
            }
        }
        listOf("しろい", "しろくろ", "しろあり", "しろのなか", "しごと", "ものごと",
            "したいです", "べんきょうしたい", "はいると", "みたい", "こと").forEach { input ->
            listOf(1, 4, 10).forEach { count ->
                assertEquals(baseline.nBestPath(input, count), engine.nBestPath(input, count), "$input count=$count")
            }
        }
    }

    @Test
    fun mitaPreferenceRetainsTheKanjiAlternative() {
        val dictionary = PackedStandaloneUnigramDictionary.read(binary())
        val engine = KanaKanjiEngine(standaloneUnigramDictionary = dictionary).apply { buildEngine() }
        val candidates = engine.nBestPath("みた", 10)
        assertEquals("みた", candidates.first())
        assertEquals(1, candidates.count { it == "みた" })
        assertTrue("見た" in candidates)
    }

    private fun candidates(input: String, dictionary: StandaloneUnigramDictionary, vararg nodes: Node): List<String> {
        val graph = List(input.length + 2) { mutableListOf<MutableList<Node>>() }
        graph[0].add(mutableListOf(node("BOS", reading = "", length = 0, cost = 0)))
        graph[input.length + 1].add(mutableListOf(node("EOS", start = input.length, reading = "", length = 0, cost = 0)))
        nodes.forEach { graph[it.sPos + it.len].add(mutableListOf(it)) }
        return FindPath(standaloneUnigramDictionary = dictionary).backwardAStar(
            graph, input.length, ConnectionMatrix(1, shortArrayOf(0)), 10, input,
        )
    }

    private fun node(surface: String, start: Int = 0, reading: String = surface, length: Int = reading.length, cost: Int = 100) =
        Node(l = 0, r = 0, score = cost, f = cost, tango = surface, len = length.toShort(), sPos = start, key = reading)
}
