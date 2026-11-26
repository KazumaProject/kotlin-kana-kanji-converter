package grammar

import com.kazumaproject.grammar.*
import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.ngram.StandaloneUnigramDictionary
import com.kazumaproject.ngram.SystemNgramDictionary
import com.kazumaproject.ngram.SystemUnigramDictionary
import com.kazumaproject.viterbi.FindPath
import kotlin.random.Random
import kotlin.test.*

class GrammarSearchTest {
    private val table = GrammarTable(listOf(
        "BOS/EOS,*,*,*,*,*,*",
        "名詞,一般,*,*,*,*,*",
        "名詞,形容動詞語幹,*,*,*,*,*",
        "助動詞,*,*,*,特殊・ダ,体言接続,だ",
        "動詞,自立,*,*,五段・ラ行,基本形,*",
        "助詞,終助詞,*,*,*,*,な",
    ))

    @Test
    fun randomizedAStarAndViterbiAgreeWithExhaustiveEnumeration() {
        val random = Random(0x1847)
        repeat(700) { sample ->
            val length = random.nextInt(1, 6)
            val input = "あ".repeat(length)
            val matrix = ConnectionMatrix(6, ShortArray(36) { random.nextInt(-30, 31).toShort() })
            val words = buildList {
                for (start in 0 until length) {
                    for (end in start + 1..length) {
                        repeat(random.nextInt(0, 4)) {
                            add(node(('a' + random.nextInt(3)).toString(), start, end,
                                random.nextInt(-30, 31), random.nextInt(1, 6), random.nextInt(1, 6)))
                        }
                    }
                }
            }
            val graph = graph(length, words)
            val offset = random.nextInt(length)
            val boundary = random.nextInt(length + 1)
            val constraints = listOf(GrammarConstraint.Boundary(boundary), GrammarConstraint.Span(
                offset, offset + 1, listOf(
                    GrammarInterpretation(GrammarSelector(partOfSpeech = "助動詞"),
                        previous = GrammarSelector(role = GrammarRole.ADJECTIVAL_STEM)),
                    GrammarInterpretation(GrammarSelector(partOfSpeech = "名詞"),
                        following = GrammarSelector(partOfSpeech = "動詞")),
                ),
            )).take(when (sample % 4) { 0 -> 0; 1 -> 1; else -> 2 })
            val allowed = paths(length, words).filter { path ->
                val safeBoundary = constraints.isEmpty() || path.none { it.sPos < boundary && it.sPos + it.len > boundary }
                safeBoundary && (constraints.size < 2 || path.withIndex().any { (index, word) ->
                    word.sPos == offset && word.len.toInt() == 1 &&
                        ((word.l.toInt() == 3 && word.r.toInt() == 3 && path.getOrNull(index - 1)?.r?.toInt() == 2) ||
                         (word.l.toInt() in 1..2 && word.r.toInt() in 1..2 && path.getOrNull(index + 1)?.l?.toInt() == 4))
                })
            }
            val penalty = sample % 19
            val reference = allowed.groupBy { path -> path.joinToString("") { it.tango } }
                .mapValues { (_, alternatives) -> alternatives.minOf { path -> cost(path, matrix, penalty) } }
            val engine = GrammarConversion(table, matrix, FindPath()) { graph }
            val options = GrammarSearchOptions(constraints, penalty)
            val result = engine.convert(input, 1_000, options)
            val actual = result.candidates.associate { it.value to it.totalCost }
            assertEquals(reference, actual, "sample $sample")
            assertEquals(reference.values.sorted(), result.candidates.map { it.totalCost }, "sample $sample")
            assertEquals(reference.values.minOrNull(), result.minimumCostPath?.totalCost, "sample $sample")
            assertEquals(reference.isEmpty(), result.failure != null)
            result.candidates.forEach { assertEquals(it.totalCost, it.annotations.sumOf { annotation ->
                annotation.incomingConnectionCost.toLong() + annotation.incomingGrammarPenalty
            } + it.path.bestPath.sumOf { word -> word.wcost.toLong() } + it.eosConnectionCost) }
            if (sample % 10 == 0) {
                val allSurfaces = paths(length, words).take(30).map { path -> path.joinToString("") { it.tango } }
                allSurfaces.forEach { assertEquals(it in reference, engine.containsCandidate(input, it, options)) }
            }
        }
    }

    @Test
    fun alternativesCorrelateLeftAndRightAcrossAStateSharedBySeveralPaths() {
        val graph = graph(3, listOf(
            node("P", 0, 1, 0, 1, 2), node("Q", 0, 1, 8, 2, 1),
            node("X", 1, 2, 0, 1, 1),
            node("R", 2, 3, 0, 4, 1), node("S", 2, 3, 5, 5, 1),
        ))
        val selector = GrammarSelector(partOfSpeech = "名詞")
        val options = GrammarSearchOptions(listOf(GrammarConstraint.Span(1, 2, listOf(
            GrammarInterpretation(selector, GrammarSelector(role = GrammarRole.ADJECTIVAL_STEM),
                GrammarSelector(partOfSpeech = "助詞")),
            GrammarInterpretation(selector, GrammarSelector(subdivisions = listOf("一般")),
                GrammarSelector(partOfSpeech = "動詞")),
        ))), includeLattice = true)
        val result = GrammarConversion(table, ConnectionMatrix(6, ShortArray(36)), FindPath()) { graph }
            .convert("あああ", 10, options)
        assertEquals(listOf("PXS", "QXR"), result.candidates.map { it.value })
        assertEquals(listOf(listOf(0), listOf(1)), result.candidates.map { it.constraintMatches.single().alternativeIndices })
        val lattice = assertNotNull(result.lattice)
        val allowed = lattice.edges.filter { it.rejection == null }
        assertEquals(2, allowed.filter { lattice.nodes[it.to].value == "X" }.map { it.toState }.distinct().size)
        assertTrue(lattice.edges.any { it.rejection?.reason == RejectionReason.FOLLOWING_CONTEXT_MISMATCH })
    }

    @Test
    fun rejectsCrossingAndDuplicateSurfacesBeforeAnyRankingRuleCanPromoteThem() {
        val graph = graph(2, listOf(
            node("Aな", 0, 2, -200, 1, 1),
            node("Bな", 0, 2, -190, 2, 3),
            node("A", 0, 1, -500, 2, 1), // The departing context is nominal.
            node("B", 0, 1, 12, 1, 2),
            node("な", 1, 2, -600, 5, 5), // Prohibitive particle.
            node("な", 1, 2, 100, 3, 3),
        ))
        val rules = FindPath(systemNgramDictionary = object : SystemNgramDictionary {
            override val ruleCount = 1
            override val storageBytes = 0
            override fun matches(node0: Node, node1: Node, node2: Node?, node3: Node?, node4: Node?) =
                node0.tango == "A" || node1.r.toInt() == 5
        }, systemUnigramDictionary = object : SystemUnigramDictionary {
            override val ruleCount = 1
            override val storageBytes = 0
            override fun matches(node: Node) = node.tango == "Aな" || node.r.toInt() == 5
        }, standaloneUnigramDictionary = object : StandaloneUnigramDictionary {
            override val ruleCount = 1
            override val storageBytes = 0
            override fun mayMatchInput(input: String) = true
            override fun matches(input: String, path: List<Node>) = path.size == 1
        })
        val engine = GrammarConversion(table, ConnectionMatrix(6, ShortArray(36)), rules) { graph }
        val options = GrammarSearchOptions(listOf(GrammarConstraint.Span(1, 2, GrammarRole.ADJECTIVAL_ATTRIBUTIVE)))
        val result = engine.convert("あな", 64, options)
        val valid = result.candidates.single()
        assertEquals("Bな", valid.value)
        assertEquals(112L, valid.totalCost)
        assertFalse(valid.ranking.promoted)
        assertFalse(engine.containsCandidate("あな", "Aな", options))
        assertTrue(engine.containsCandidate("あな", "Bな", options))
        assertTrue(result.rejections.any { it.rejection.reason == RejectionReason.CROSSES_SPAN })
        assertTrue(result.rejections.any { it.rejection.reason == RejectionReason.PREVIOUS_CONTEXT_MISMATCH })
    }

    @Test
    fun laterLegalStandaloneMatchPromotesTheFirstLegalPathForTheSameSurface() {
        val graph = graph(3, listOf(
            node("時代", 0, 3, 0, 1, 1),
            node("し", 0, 1, 10, 1, 1), node("たい", 1, 3, 10, 1, 1),
            node("したい", 0, 3, 100, 1, 1),
        ))
        val rules = FindPath(standaloneUnigramDictionary = object : StandaloneUnigramDictionary {
            override val ruleCount = 1
            override val storageBytes = 0
            override fun mayMatchInput(input: String) = input == "したい"
            override fun matches(input: String, path: List<Node>) = path.singleOrNull()?.tango == input
        })
        val engine = GrammarConversion(table, ConnectionMatrix(6, ShortArray(36)), rules) { graph }
        val result = engine.convert("したい", 1, GrammarSearchOptions(listOf(GrammarConstraint.Boundary(0))))
        val candidate = result.candidates.single()
        assertEquals("したい", candidate.value)
        assertEquals(20L, candidate.totalCost)
        assertEquals(2, candidate.path.bestPath.size)
        assertTrue(candidate.ranking.standaloneUnigram)
        assertEquals("時代", result.minimumCostPath?.value)
    }

    @Test
    fun offsetsAreUtf16AndUnsatisfiableRequestsHaveNoFallback() {
        val graph = graph(2, listOf(node("字", 0, 2, 0, 1, 1)))
        val engine = GrammarConversion(table, ConnectionMatrix(6, ShortArray(36)), FindPath()) { graph }
        assertFailsWith<IllegalArgumentException> {
            engine.convert("𠮷", 10, GrammarSearchOptions(listOf(GrammarConstraint.Boundary(1))))
        }
        val impossible = engine.convert("ああ", 10, GrammarSearchOptions(listOf(GrammarConstraint.Boundary(1))))
        assertEquals(GrammarFailure.NO_PATH_WITH_CONSTRAINTS, impossible.failure)
        assertEquals(emptyList(), impossible.candidates)
        assertNull(impossible.minimumCostPath)
        assertEquals(RejectionReason.CROSSES_BOUNDARY, impossible.rejections.single().rejection.reason)
    }

    private fun paths(length: Int, words: List<Node>): List<List<Node>> {
        fun suffix(start: Int): List<List<Node>> = if (start == length) listOf(emptyList()) else
            words.filter { it.sPos == start }.flatMap { word ->
                suffix(start + word.len).map { listOf(word) + it }
            }
        return suffix(0)
    }

    private fun cost(path: List<Node>, matrix: ConnectionMatrix, penalty: Int): Long {
        var right: Short = 0
        var price = 0L
        for (word in path) {
            price += matrix.getCost(right, word.l) + word.wcost
            if (word.l.toInt() == 3 && right.toInt() != 2) price += penalty
            right = word.r
        }
        return price + matrix.getCost(right, 0)
    }

    private fun graph(length: Int, words: List<Node>) = List(length + 2) { mutableListOf<MutableList<Node>>() }.also {
        it[0].add(mutableListOf(node("BOS", 0, 0, 0, 0, 0)))
        it[length + 1].add(mutableListOf(node("EOS", length, length, 0, 0, 0)))
        words.forEach { word -> it[word.sPos + word.len].add(mutableListOf(word)) }
    }

    private fun node(value: String, start: Int, end: Int, cost: Int, left: Int, right: Int) =
        Node(left.toShort(), right.toShort(), cost, 0, tango = value, len = (end - start).toShort(),
            sPos = start, key = value, wcost = cost)
}
