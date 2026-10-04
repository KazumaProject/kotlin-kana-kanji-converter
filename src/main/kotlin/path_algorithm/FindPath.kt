package com.kazumaproject.viterbi

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.ngram.EmptySystemNgramDictionary
import com.kazumaproject.ngram.EmptySystemUnigramDictionary
import com.kazumaproject.ngram.SystemNgramDictionary
import com.kazumaproject.ngram.SystemUnigramDictionary
import java.util.PriorityQueue
import kotlin.math.sqrt

class FindPath(
    private val systemNgramDictionary: SystemNgramDictionary = EmptySystemNgramDictionary,
    private val systemUnigramDictionary: SystemUnigramDictionary = EmptySystemUnigramDictionary,
) {

    private data class PathState(
        val node: Node,
        val path: List<Node>,
        val cost: Int,
        val endPosition: Int,
        val value: String = "",
    )

    private data class CandidatePath(
        val value: String,
        val cost: Int,
        val matchedBySystemDictionary: Boolean,
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
        if (n <= 0) return mutableListOf()
        val outgoing = buildOutgoingNodes(graph, length)
        // Exact minimum remaining cost on this acyclic lattice. Uniform-cost
        // enumeration without this potential explodes on ordinary sentences
        // and is not valid when dictionary/connection costs are negative.
        val remaining = java.util.IdentityHashMap<Node, Int>()
        graph[length + 1].flatten().forEach { remaining[it] = 0 }
        for (start in length downTo 0) {
            outgoing[start].filter { it.tango != "EOS" }.forEach { node ->
                val end = node.sPos + node.len.toInt()
                remaining[node] = outgoing.getOrElse(end) { emptyList() }.mapNotNull { next ->
                    remaining[next]?.takeIf { it != Int.MAX_VALUE }?.let { addCosts(getEdgeCost(node.r.toInt(),next.l.toInt(),connectionMatrix),next.wcost,it) }
                }.minOrNull() ?: Int.MAX_VALUE
            }
        }
        val queue = PriorityQueue(compareBy<PathState> { it.cost.toLong() + (remaining[it.node] ?: 0).toLong() })
        val bos = graph[0].flatten().firstOrNull { it.tango == "BOS" } ?: return mutableListOf()
        remaining[bos] = outgoing[0].mapNotNull { next -> remaining[next]?.takeIf { it != Int.MAX_VALUE }?.let { addCosts(getEdgeCost(bos.r.toInt(),next.l.toInt(),connectionMatrix),next.wcost,it) } }.minOrNull() ?: Int.MAX_VALUE
        if (remaining[bos] == Int.MAX_VALUE) return mutableListOf()
        queue.add(PathState(node = bos, path = emptyList(), cost = 0, endPosition = 0))

        val hasSystemRules =
            systemNgramDictionary.ruleCount > 0 || systemUnigramDictionary.ruleCount > 0
        val internalCandidateCount = if (hasSystemRules) {
            maxOf(n, n.saturatingMultiply(4).coerceAtMost(64), 32)
        } else {
            n
        }
        val resultFinal = mutableListOf<CandidatePath>()
        val foundStrings = HashSet<String>()
        data class PrefixKey(val end: Int, val right: Short, val value: String)
        val bestPrefixes = hashMapOf<PrefixKey, Int>()

        while (queue.isNotEmpty()) {
            val state = queue.poll()
            if (state.node.tango == "EOS") {
                val value = state.value
                if (foundStrings.add(value)) {
                    resultFinal += CandidatePath(
                        value = value,
                        cost = state.cost,
                        matchedBySystemDictionary =
                            pathMatchesSystemNgram(state.path) || pathMatchesSystemUnigram(state.path),
                    )
                }
                if (
                    resultFinal.size >= internalCandidateCount ||
                    (resultFinal.size >= n && resultFinal.any { it.matchedBySystemDictionary })
                ) break
                continue
            }

            if (!hasSystemRules && bestPrefixes[PrefixKey(state.endPosition,state.node.r,state.value)]?.let { it < state.cost } == true) continue
            for (nextNode in outgoing.getOrElse(state.endPosition) { emptyList() }) {
                if (remaining[nextNode] == Int.MAX_VALUE) continue
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
                val nextValue = if(nextNode.tango=="EOS") state.value else state.value+nextNode.tango
                if (!hasSystemRules) {
                    val key=PrefixKey(nextEnd,nextNode.r,nextValue)
                    val old=bestPrefixes[key]
                    if(old!=null && old<=nextCost) continue
                    bestPrefixes[key]=nextCost
                }
                queue.add(
                    PathState(
                        node = nextNode,
                        path = nextPath,
                        cost = nextCost,
                        endPosition = nextEnd,
                        value = nextValue,
                    )
                )
            }
        }
        return resultFinal
            .sortedWith(
                compareByDescending<CandidatePath> { it.matchedBySystemDictionary }
                    .thenBy { it.cost },
            )
            .take(n)
            .mapTo(mutableListOf()) { it.value }
    }

    private fun pathMatchesSystemNgram(path: List<Node>): Boolean {
        if (systemNgramDictionary.ruleCount == 0) return false
        for (start in path.indices) {
            val secondIndex = start + 1
            if (secondIndex >= path.size) break
            if (
                systemNgramDictionary.matches(
                    node0 = path[start],
                    node1 = path[secondIndex],
                    node2 = path.getOrNull(start + 2),
                    node3 = path.getOrNull(start + 3),
                    node4 = path.getOrNull(start + 4),
                )
            ) return true
        }
        return false
    }

    private fun pathMatchesSystemUnigram(path: List<Node>): Boolean =
        systemUnigramDictionary.ruleCount > 0 && path.any(systemUnigramDictionary::matches)

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

    private fun Int.saturatingMultiply(multiplier: Int): Int =
        if (this > Int.MAX_VALUE / multiplier) Int.MAX_VALUE else this * multiplier

}
