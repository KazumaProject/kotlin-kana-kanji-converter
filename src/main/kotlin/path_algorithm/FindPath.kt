package com.kazumaproject.viterbi

import com.kazumaproject.Other.BOS
import com.kazumaproject.Other.NUM_OF_CONNECTION_ID
import com.kazumaproject.graph.Node
import java.util.*

class FindPath {

    fun viterbi(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray
    ): String {
        buildViterbi(graph, length, connectionIds)
        var node = graph[length + 1][0][0]
        val result: MutableList<String> = mutableListOf()
        while (node.tango != "BOS"){
            node.prev?.let {
                result.add(it.tango)
                node = it
            }
        }
        val final = result.reversed().drop(1).joinToString(separator = "") { it }
        return final
    }

    fun backwardAStar(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray,
        n: Int
    ): MutableList<String> {
        forwardDp(graph, length, connectionIds)
        val result: MutableList<Pair<Node,Int>> = mutableListOf()
        val resultFinal: MutableList<String> = mutableListOf()
        val pQueue: PriorityQueue<Pair<Node,Int>> = PriorityQueue (compareBy{
            it.second
        })
        val eos = Pair(graph[length + 1][0][0],0)
        pQueue.add(eos)
        while (pQueue.isNotEmpty()){
            val node: Pair<Node,Int> = pQueue.poll()
            if (node.first.tango == "BOS") {
                result.add(node)
                if (!resultFinal.contains(getStringFromNode(node.first))){
                    resultFinal.add(getStringFromNode(node.first))
                }
                pQueue.remove()
            } else {
                val prevNodes = getPrevNodes2(
                    graph,node.first,node.first.sPos
                ).flatten()
                for (prevNode in prevNodes){
                    val edgeScore = getEdgeCost(
                        prevNode.l.toInt(),
                        node.first.r.toInt(),
                        connectionIds
                    )
                    prevNode.g = node.first.g + edgeScore + node.first.score
                    prevNode.next = node.first
                    val result2 = Pair(prevNode,prevNode.g + prevNode.f)
                    pQueue.add(result2)
                }
            }
            if (resultFinal.size >= n) {
                return resultFinal
            }
        }
        return resultFinal
    }

    private fun buildViterbi(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray
    ){
        for (i in 1 .. length + 1){
            val nodes = graph[i].flatten()
            for (node in nodes){
                val nodeCost = node.score
                var cost = Int.MAX_VALUE
                var shortestPrev: Node? = null
                val prevNodes = getPrevNodesForViterbi(
                    graph,
                    node,
                    i,
                ).flatten()
                for (prevNode in prevNodes){
                    val edgeCost = getEdgeCost(
                        prevNode.l.toInt(),
                        node.r.toInt(),
                        connectionIds
                    )
                    val tempCost = prevNode.score + nodeCost + edgeCost
                    if (tempCost < cost){
                        cost = tempCost
                        shortestPrev = prevNode
                    }
                }
                node.score = cost
                node.prev = shortestPrev
            }
        }
    }

    private fun forwardDp(
        graph: List<MutableList<MutableList<Node>>>,
        length: Int,
        connectionIds: ShortArray
    ){
        for (i in 1 .. length + 1){
            val nodes = graph[i].flatten()
            for (node in nodes){
                val nodeScore = node.f
                var score = Int.MAX_VALUE
                var bestPrev: Node? = null
                val prevNodes = getPrevNodes(
                    graph,
                    node,
                    i,
                ).flatten()
                for (prev in prevNodes){
                    val edgeCost = getEdgeCost(
                        prev.l.toInt(),
                        node.r.toInt(),
                        connectionIds
                    )
                    val tempCost = prev.f + nodeScore + edgeCost
                    if (tempCost < score){
                        score = tempCost
                        bestPrev = prev
                    }
                }
                node.prev = bestPrev
                node.f = score
            }
        }
    }

    private fun getPrevNodes(
        graph: List<MutableList<MutableList<Node>>>,
        node: Node,
        startPosition: Int,
        ): MutableList<MutableList<Node>>{
        val index = if (node.tango == "EOS") graph.size - 2 else startPosition - node.len
        if ((startPosition - node.len) == 0) return mutableListOf(mutableListOf(BOS))
        if (index < 0) return mutableListOf()
        return graph[index]
    }

    private fun getPrevNodes2(
        graph: List<MutableList<MutableList<Node>>>,
        node: Node,
        startPosition: Int,
    ): MutableList<MutableList<Node>>{
        val index = if (node.tango == "EOS") graph.size - 2 else startPosition
        if (startPosition == 0) return mutableListOf(mutableListOf(BOS))
        if (index < 0) return mutableListOf()
        return graph[index]
    }

    private fun getPrevNodesForViterbi(
        graph: List<MutableList<MutableList<Node>>>,
        node: Node,
        startPosition: Int,
    ): MutableList<MutableList<Node>>{
        if ((startPosition - node.len) == 0)return mutableListOf(mutableListOf(BOS))
        val index = if (node.tango == "EOS") startPosition - 1 else startPosition - node.len.toInt()
        if (index < 0) return mutableListOf()
        return graph[index]
    }

    private fun getEdgeCost(
        leftId: Int,
        rightId: Int,
        connectionIds: ShortArray
    ):Int {
        return connectionIds[leftId * NUM_OF_CONNECTION_ID + rightId].toInt()
    }

    private fun getStringFromNode(node: Node): String{
        var tempNode = node
        val result: MutableList<String> = mutableListOf()
        while (tempNode.tango != "EOS"){
            tempNode.next?.let {
                result.add(it.tango)
                tempNode = it
            }
        }
        return result.dropLast(1).joinToString("")
    }

}