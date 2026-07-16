package com.kazumaproject.viterbi

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import java.util.PriorityQueue
import kotlin.math.sqrt

class FindPath {

    private data class PathState(
        val node: Node,
        val path: List<Node>,
        val cost: Int,
        val endPosition: Int,
    )

    fun viterbi(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray
    ): String = viterbi(graph, length, inferConnectionMatrix(connectionIds))

    fun viterbi(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionMatrix: ConnectionMatrix
    ): String {
        return findBestPath(graph, length, connectionMatrix).joinToString(separator = "") { it.tango }
    }

    fun findBestPath(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray
    ): List<Node> = findBestPath(graph, length, inferConnectionMatrix(connectionIds))

    fun findBestPath(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionMatrix: ConnectionMatrix
    ): List<Node> {
        buildViterbi(graph, length, connectionMatrix)
        val result = mutableListOf<Node>()
        var node = graph[length + 1].flatten().firstOrNull { it.tango == "EOS" }?.prev
        while (node != null && node.tango != "BOS") {
            result.add(node)
            node = node.prev
        }
        return result.asReversed()
    }

    fun backwardAStar(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray,
        n: Int
    ): MutableList<String> = backwardAStar(graph, length, inferConnectionMatrix(connectionIds), n)

    fun backwardAStar(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionMatrix: ConnectionMatrix,
        n: Int
    ): MutableList<String> {
        val resultFinal: MutableList<String> = mutableListOf()
        if (n <= 0) return resultFinal
        val outgoing = buildOutgoingNodes(graph, length)
        val queue = PriorityQueue(compareBy<PathState> { it.cost })
        val bos = graph[0].flatten().firstOrNull { it.tango == "BOS" } ?: return resultFinal
        queue.add(PathState(node = bos, path = emptyList(), cost = 0, endPosition = 0))

        while (queue.isNotEmpty()) {
            val state = queue.poll()
            if (state.node.tango == "EOS") {
                val value = state.path.joinToString(separator = "") { it.tango }
                if (value !in resultFinal) {
                    resultFinal.add(value)
                }
                if (resultFinal.size >= n) return resultFinal
                continue
            }

            for (nextNode in outgoing.getOrElse(state.endPosition) { emptyList() }) {
                val edgeScore = getEdgeCost(
                    state.node.r.toInt(),
                    nextNode.l.toInt(),
                    connectionMatrix
                )
                val nextCost = addCosts(state.cost, edgeScore, nextNode.wcost)
                val nextPath = if (nextNode.tango == "EOS") state.path else state.path + nextNode
                val nextEnd = when (nextNode.tango) {
                    "EOS" -> length + 1
                    else -> nextNode.sPos + nextNode.len.toInt()
                }
                queue.add(
                    PathState(
                        node = nextNode,
                        path = nextPath,
                        cost = nextCost,
                        endPosition = nextEnd,
                    )
                )
            }
        }
        return resultFinal
    }

    private fun buildViterbi(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionMatrix: ConnectionMatrix
    ){
        resetScores(graph)
        for (i in 1 .. length + 1){
            val nodes = graph[i].flatten()
            for (node in nodes){
                var cost = Int.MAX_VALUE
                var shortestPrev: Node? = null
                val prevNodes = getPrevNodesForViterbi(
                    graph,
                    node,
                    i,
                ).flatten()
                for (prevNode in prevNodes){
                    if (prevNode.totalCost == Int.MAX_VALUE) continue
                    val edgeCost = getEdgeCost(
                        prevNode.r.toInt(),
                        node.l.toInt(),
                        connectionMatrix
                    )
                    val tempCost = addCosts(prevNode.totalCost, node.wcost, edgeCost)
                    if (tempCost < cost){
                        cost = tempCost
                        shortestPrev = prevNode
                    }
                }
                node.score = cost
                node.totalCost = cost
                node.prev = shortestPrev
            }
        }
    }

    private fun getPrevNodesForViterbi(
        graph: List<MutableList<MutableList<Node>>>,
        node: Node,
        startPosition: Int,
    ): MutableList<MutableList<Node>>{
        val index = if (node.tango == "EOS") startPosition - 1 else node.sPos
        if (index < 0 || index >= graph.size) return mutableListOf()
        return graph[index]
    }

    private fun getEdgeCost(
        leftId: Int,
        rightId: Int,
        connectionMatrix: ConnectionMatrix
    ):Int {
        return connectionMatrix.getCost(leftId, rightId)
    }

    private fun inferConnectionMatrix(connectionIds: ShortArray): ConnectionMatrix {
        val size = sqrt(connectionIds.size.toDouble()).toInt()
        require(size * size == connectionIds.size) {
            "Invalid connection ID array: short count=${connectionIds.size}, reason=short count must be a perfect square"
        }
        return ConnectionMatrix(size, connectionIds)
    }

    private fun resetScores(graph: List<MutableList<MutableList<Node>>>) {
        graph.forEach { groups ->
            groups.flatten().forEach { node ->
                node.prev = null
                node.next = null
                node.g = 0
                if (node.tango == "BOS") {
                    node.score = 0
                    node.f = 0
                    node.totalCost = 0
                } else {
                    node.score = node.wcost
                    node.f = Int.MAX_VALUE
                    node.totalCost = Int.MAX_VALUE
                }
            }
        }
    }

    private fun buildOutgoingNodes(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
    ): List<List<Node>> {
        val outgoing = MutableList(length + 1) { mutableListOf<Node>() }
        for (endPosition in 1..length) {
            graph[endPosition].flatten().forEach { node ->
                if (node.sPos in 0..length) {
                    outgoing[node.sPos].add(node)
                }
            }
        }
        graph[length + 1].flatten().forEach { eos ->
            outgoing[length].add(eos)
        }
        return outgoing
    }

    private fun addCosts(vararg costs: Int): Int {
        val total = costs.fold(0L) { acc, cost -> acc + cost.toLong() }
        return total.coerceIn(Int.MIN_VALUE.toLong(), Int.MAX_VALUE.toLong()).toInt()
    }

}
