package com.kazumaproject.graph

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.Other.BOS
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.hiraToKata
import com.kazumaproject.dictionary.LoadedDictionary

class GraphBuilder {

    fun constructGraph(
        str: String,
        yomiTrie: LOUDSWithTermId,
        tangoTrie: LOUDS,
        tokenArray: TokenArray
    ): List<MutableList<MutableList<Node>>> {
        return constructGraph(str, listOf(LoadedDictionary("system", yomiTrie, tangoTrie, tokenArray)))
    }

    fun constructGraph(str: String, dictionaries: List<LoadedDictionary>): List<MutableList<MutableList<Node>>> {
        val graph: MutableList<MutableList<MutableList<Node>>> =
            MutableList(str.length + 2) { mutableListOf() }
        graph[0].add(
            mutableListOf(
                BOS.copy(
                    score = 0,
                    f = 0,
                    g = 0,
                    totalCost = 0,
                    prev = null,
                    next = null,
                )
            )
        )
        graph[str.length + 1].add(
            mutableListOf(
                Node(
                    l = 0,
                    r = 0,
                    score = 0,
                    f = 0,
                    g = 0,
                    tango = "EOS",
                    len = 0,
                    sPos = str.length,
                    key = "EOS",
                    wcost = 0,
                    totalCost = Int.MAX_VALUE,
                )
            )
        )

        val seen = hashSetOf<List<Any>>()
        for (i in str.indices) {
            val subStr = str.substring(i, str.length)
            dictionaries.forEach { dictionary ->
                val yomiTrie = dictionary.yomiTrie
                val tangoTrie = dictionary.tangoTrie
                val tokenArray = dictionary.tokenArray
                val commonPrefixSearch = yomiTrie.commonPrefixSearch(subStr)
                commonPrefixSearch.forEach { yomiStr ->
                    val termId = yomiTrie.getTermId(yomiTrie.getNodeIndex(yomiStr))
                    val listToken = tokenArray.getListDictionaryByYomiTermId(termId)
                    val tangoList = listToken.mapNotNull {
                        val node = Node(
                            l = tokenArray.leftIds[it.posTableIndex.toInt()],
                            r = tokenArray.rightIds[it.posTableIndex.toInt()],
                            score = it.wordCost.toInt(),
                            f = it.wordCost.toInt(),
                            g = it.wordCost.toInt(),
                            tango = when (it.nodeId) {
                                -2 -> yomiStr
                                -1 -> yomiStr.hiraToKata()
                                else -> tangoTrie.getLetter(it.nodeId)
                            },
                            len = yomiStr.length.toShort(),
                            sPos = i,
                            key = yomiStr,
                            wcost = it.wordCost.toInt(),
                            totalCost = Int.MAX_VALUE,
                            dictionaryId = dictionary.id,
                        )
                        node.takeIf { seen.add(listOf(i, node.key, node.tango, node.l, node.r, node.wcost)) }
                    }
                    graph[i + yomiStr.length].add(tangoList.toMutableList())
                }
            }
        }
        return graph
    }

}
