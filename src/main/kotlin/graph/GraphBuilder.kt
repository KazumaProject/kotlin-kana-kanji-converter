package com.kazumaproject.graph

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.Other.BOS
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.hiraToKata

data class GraphDictionary(
    val yomiTrie: LOUDSWithTermId,
    val tangoTrie: LOUDS,
    val tokenArray: TokenArray,
)

class GraphBuilder {

    private fun addOrUpdateNode(
        nodesByEndIndex: MutableMap<Int, MutableList<Node>>,
        endIndex: Int,
        newNode: Node,
    ) {
        val nodes = nodesByEndIndex.getOrPut(endIndex) { mutableListOf() }
        val existingNodeIndex = nodes.indexOfFirst {
            it.tango == newNode.tango && it.l == newNode.l && it.r == newNode.r
        }

        if (existingNodeIndex == -1) {
            nodes.add(newNode)
            return
        }

        if (newNode.score < nodes[existingNodeIndex].score) {
            nodes[existingNodeIndex] = newNode
        }
    }

    fun constructGraph(
        str: String,
        dictionaries: List<GraphDictionary>,
    ): List<MutableList<MutableList<Node>>> {
        val graph = MutableList(str.length + 2) { mutableListOf<MutableList<Node>>() }
        val nodesByEndIndex = mutableMapOf<Int, MutableList<Node>>()
        for (i in 0 .. str.length + 1){
            when(i){
                0 -> graph[i] = mutableListOf(mutableListOf(BOS))
                str.length + 1 -> graph[i] = mutableListOf(
                    mutableListOf(
                        Node(
                        l = 0,
                        r = 0,
                        score = 0,
                        f = 0,
                        g = 0,
                        tango = "EOS",
                        len = 0,
                        sPos = str.length + 1
                    ))
                )
            }
        }

        for (i in str.indices){
            val subStr = str.substring(i, str.length)
            dictionaries.forEach { dictionary ->
                val commonPrefixSearch = dictionary.yomiTrie.commonPrefixSearch(subStr)
                commonPrefixSearch.forEach { yomiStr ->
                    val termId = dictionary.yomiTrie.getTermId(dictionary.yomiTrie.getNodeIndex(yomiStr))
                    val listToken = dictionary.tokenArray.getListDictionaryByYomiTermId(termId)
                    listToken.forEach {
                        addOrUpdateNode(
                            nodesByEndIndex = nodesByEndIndex,
                            endIndex = i + yomiStr.length,
                            newNode = Node(
                                l = dictionary.tokenArray.leftIds[it.posTableIndex.toInt()],
                                r = dictionary.tokenArray.rightIds[it.posTableIndex.toInt()],
                                score = it.wordCost.toInt(),
                                f = it.wordCost.toInt(),
                                g = it.wordCost.toInt(),
                                tango = when (it.nodeId) {
                                    -2 -> yomiStr
                                    -1 -> yomiStr.hiraToKata()
                                    else -> dictionary.tangoTrie.getLetter(it.nodeId)
                                },
                                len = yomiStr.length.toShort(),
                                sPos = i
                            ),
                        )
                    }
                }
            }
        }

        nodesByEndIndex.forEach { (endIndex, nodes) ->
            graph[endIndex] = mutableListOf(nodes.toMutableList())
        }

        return graph.toList()
    }

}
