package engine

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.viterbi.FindPath
import kotlin.test.Test
import kotlin.test.assertEquals

class FindPathCostDirectionTest {
    @Test
    fun viterbiUsesPreviousRightIdAndCurrentLeftIdForConnectionCost() {
        val graph = listOf(
            mutableListOf(mutableListOf(bos())),
            mutableListOf(
                mutableListOf(
                    node(lid = 1, rid = 2, value = "A"),
                    node(lid = 2, rid = 1, value = "B"),
                )
            ),
            mutableListOf(mutableListOf(eos())),
        )
        val matrix = ConnectionMatrix(
            size = 3,
            costs = ShortArray(9).also { costs ->
                costs[0 * 3 + 1] = 1
                costs[0 * 3 + 2] = 100
            },
        )

        val bestPath = FindPath().findBestPath(graph, length = 1, connectionMatrix = matrix)

        assertEquals("A", bestPath.single().tango)
        assertEquals(1, bestPath.single().totalCost)
    }

    private fun bos(): Node =
        Node(
            l = 0,
            r = 0,
            score = 0,
            f = 0,
            tango = "BOS",
            len = 0,
            sPos = 0,
            key = "BOS",
            wcost = 0,
            totalCost = 0,
        )

    private fun eos(): Node =
        Node(
            l = 0,
            r = 0,
            score = 0,
            f = 0,
            tango = "EOS",
            len = 0,
            sPos = 1,
            key = "EOS",
            wcost = 0,
        )

    private fun node(
        lid: Int,
        rid: Int,
        value: String,
    ): Node =
        Node(
            l = lid.toShort(),
            r = rid.toShort(),
            score = 0,
            f = 0,
            tango = value,
            len = 1,
            sPos = 0,
            key = value,
            wcost = 0,
        )
}
