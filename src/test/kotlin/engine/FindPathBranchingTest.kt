package engine

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.viterbi.FindPath
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class FindPathBranchingTest {
    @Test
    fun returnsFiftyDistinctCompletePathsInCostOrderAcrossSharedPrefixes() {
        val length = 24
        fun node(value: String, start: Int, size: Int, cost: Int) = Node(
            l = 0, r = 0, tango = value, key = value, sPos = start,
            len = size.toShort(), wcost = cost, score = 0, f = 0,
        )
        val graph = mutableListOf(mutableListOf(mutableListOf(node("BOS", 0, 0, 0))))
        for (position in 0 until length) {
            val letter = 'a' + position
            graph += mutableListOf(mutableListOf(
                node(letter.toString(), position, 1, 1000),
                node(letter.uppercaseChar().toString(), position, 1, 1001),
            ))
        }
        graph += mutableListOf(mutableListOf(node("EOS", length, 0, 0)))

        val candidates = FindPath().backwardAStar(graph, length, ConnectionMatrix(1, shortArrayOf(0)), 50)

        assertEquals(50, candidates.size)
        assertEquals(50, candidates.toSet().size)
        assertEquals("abcdefghijklmnopqrstuvwx", candidates.first())
        candidates.forEach { value ->
            assertEquals(length, value.length)
            value.forEachIndexed { index, letter -> assertEquals('a' + index, letter.lowercaseChar()) }
        }
        val costs = candidates.map { value -> value.count(Char::isUpperCase) }
        assertEquals(costs.sorted(), costs)
        assertTrue(costs.all { it <= 2 })
    }

    @Test
    fun includesNegativeEosConnectionInCandidatePriority() {
        fun node(value: String, right: Short, cost: Int) = Node(
            l = 0, r = right, tango = value, key = value, sPos = 0,
            len = 1, wcost = cost, score = 0, f = 0,
        )
        val bos = Node(l = 0, r = 0, tango = "BOS", sPos = 0, len = 0, score = 0, f = 0)
        val eos = Node(l = 2, r = 0, tango = "EOS", sPos = 1, len = 0, score = 0, f = 0)
        val graph = listOf(
            mutableListOf(mutableListOf(bos)),
            mutableListOf(mutableListOf(node("A", 1, 10), node("B", 0, 0))),
            mutableListOf(mutableListOf(eos)),
        )
        val matrix = ConnectionMatrix(3, ShortArray(9).also { it[1 * 3 + 2] = -100 })

        assertEquals(listOf("A", "B"), FindPath().backwardAStar(graph, 1, matrix, 2))
    }
}
