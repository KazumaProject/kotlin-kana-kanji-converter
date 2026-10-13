package engine

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.ngram.SystemUnigramDictionary
import com.kazumaproject.viterbi.FindPath
import kotlin.test.Test
import kotlin.test.assertEquals

class FindPathUnigramScopeTest {
    @Test
    fun unigramPromotesACompleteOneNodeCandidate() {
        val graph = graph(
            length = 2,
            node("奈良", start = 0, length = 2, cost = 0),
            node("なら", start = 0, length = 2, cost = 100),
        )

        assertEquals(listOf("なら", "奈良"), candidates(graph, length = 2, word = "なら", n = 2))
    }

    @Test
    fun unigramPromotesAMatchingNodeInsideAMultiNodeCandidateLikeJapaneseKeyboard() {
        val graph = graph(
            length = 3,
            node("仕事", start = 0, length = 3, cost = 0),
            node("し", start = 0, length = 1, cost = 0),
            node("ごと", start = 1, length = 2, cost = 100),
        )

        assertEquals(listOf("しごと", "仕事"), candidates(graph, length = 3, word = "ごと", n = 2))
    }

    @Test
    fun aCompoundRegisteredAsOneNodeCanMatchItsOwnUnigramRule() {
        val graph = graph(
            length = 4,
            node("別候補", start = 0, length = 4, cost = 0),
            node("奈良県", start = 0, length = 4, cost = 100),
        )

        assertEquals(listOf("奈良県", "別候補"), candidates(graph, length = 4, word = "奈良県", n = 2))
    }

    @Test
    fun firstDistinctSurfacePathDeterminesItsUnigramMatchLikeJapaneseKeyboard() {
        val graph = graph(
            length = 3,
            node("時代", start = 0, length = 3, cost = 0),
            node("し", start = 0, length = 1, cost = 0),
            node("たい", start = 1, length = 2, cost = 10),
            node("したい", start = 0, length = 3, cost = 100),
        )

        assertEquals(listOf("時代"), candidates(graph, length = 3, word = "したい", n = 1))
    }

    @Test
    fun shiroRulePromotesShiroPlusMedicalKanjiDespiteCheaperShiroiCandidate() {
        val graph = graph(
            length = 3,
            node("白い", start = 0, length = 3, cost = 100),
            node("しろ", start = 0, length = 2, cost = 200),
            node("医", start = 2, length = 1, cost = 300),
        )
        assertEquals(listOf("しろ医", "白い"), candidates(graph, length = 3, word = "しろ", n = 2))
    }

    @Test
    fun removingShiroRuleRestoresWhiteAdjectiveAndRetainsOtherCandidates() {
        val graph = graph(
            length = 3,
            node("白い", start = 0, length = 3, cost = 100),
            node("しろ", start = 0, length = 2, cost = 200),
            node("医", start = 2, length = 1, cost = 300),
        )
        assertEquals(listOf("白い", "しろ医"), candidates(graph, length = 3, word = "なのか", n = 2))
    }

    @Test
    fun gotoUnigramAlsoPromotesAWholeInputOmissionCandidateForKoto() {
        val graph = graph(
            length = 2,
            node("こと", start = 0, length = 2, cost = 100),
            node("ごと", start = 0, length = 2, cost = 2000),
        )
        assertEquals(listOf("ごと", "こと"), candidates(graph, length = 2, word = "ごと", n = 2))
    }

    @Test
    fun removingGotoUnigramPreservesTheOmissionPenaltyForKoto() {
        val graph = graph(
            length = 2,
            node("こと", start = 0, length = 2, cost = 100),
            node("ごと", start = 0, length = 2, cost = 2000),
        )
        assertEquals(listOf("こと", "ごと"), candidates(graph, length = 2, word = "なのか", n = 2))
    }

    @Test
    fun emptyCandidateIsNotAUnigramMatch() {
        assertEquals(listOf(""), candidates(graph(length = 0), length = 0, word = "", n = 1))
    }

    private fun candidates(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        word: String,
        n: Int,
    ): List<String> = FindPath(
        systemUnigramDictionary = object : SystemUnigramDictionary {
            override val ruleCount = 1
            override val storageBytes = 0
            override fun matches(node: Node): Boolean = node.tango == word
        },
    ).backwardAStar(graph, length, ConnectionMatrix(size = 1, costs = shortArrayOf(0)), n)

    private fun graph(length: Int, vararg nodes: Node): List<MutableList<MutableList<Node>>> =
        List(length + 2) { mutableListOf<MutableList<Node>>() }.also { graph ->
            graph[0].add(mutableListOf(node("BOS", start = 0, length = 0, cost = 0)))
            graph[length + 1].add(mutableListOf(node("EOS", start = length, length = 0, cost = 0)))
            nodes.forEach { graph[it.sPos + it.len].add(mutableListOf(it)) }
        }

    private fun node(value: String, start: Int, length: Int, cost: Int): Node = Node(
        l = 0,
        r = 0,
        score = cost,
        f = cost,
        tango = value,
        len = length.toShort(),
        sPos = start,
        wcost = cost,
    )
}
