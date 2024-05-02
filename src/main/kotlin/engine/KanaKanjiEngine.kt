package com.kazumaproject.engine

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.viterbi.FindPath
import java.io.FileInputStream
import java.io.ObjectInputStream

class KanaKanjiEngine {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var yomiTrie: LOUDSWithTermId
    private lateinit var tangoTrie: LOUDS
    private lateinit var connectionIds: List<Short>
    private lateinit var findPath: FindPath
    private lateinit var tokenArray: TokenArray

    fun buildEngine(){
        val objectInputYomi = ObjectInputStream(FileInputStream("src/main/resources/yomi.dat"))
        val objectInputTango = ObjectInputStream(FileInputStream("src/main/resources/tango.dat"))
        val objectInputTokenArray = ObjectInputStream(FileInputStream("src/main/resources/token.dat"))
        val objectInputConnectionId = ObjectInputStream(FileInputStream("src/main/resources/connectionIds.dat"))

        yomiTrie = LOUDSWithTermId().readExternal(objectInputYomi)
        tangoTrie = LOUDS().readExternal(objectInputTango)
        graphBuilder = GraphBuilder()
        tokenArray = TokenArray()
        tokenArray.readExternal(objectInputTokenArray)
        tokenArray.readPOSTable(1)
        connectionIds = ConnectionIdBuilder().read(objectInputConnectionId)
        findPath = FindPath()
    }

    fun buildEngineForTest(){
        val objectInputYomi = ObjectInputStream(FileInputStream("src/test/resources/yomi.dat"))
        val objectInputTango = ObjectInputStream(FileInputStream("src/test/resources/tango.dat"))
        val objectInputTokenArray = ObjectInputStream(FileInputStream("src/test/resources/token.dat"))
        val objectInputConnectionId = ObjectInputStream(FileInputStream("src/test/resources/connectionIds.dat"))
        yomiTrie = LOUDSWithTermId().readExternal(objectInputYomi)
        tangoTrie = LOUDS().readExternal(objectInputTango)
        graphBuilder = GraphBuilder()
        tokenArray = TokenArray()
        tokenArray.readExternal(objectInputTokenArray)
        tokenArray.readPOSTable(0)
        connectionIds = ConnectionIdBuilder().read(objectInputConnectionId)
        findPath = FindPath()
    }

    fun nBestPath(
        input: String,
        n: Int
    ): List<String>{
        val graph = graphBuilder.constructGraph(
            input,
            yomiTrie,
            tangoTrie,
            tokenArray,
        )
        val result = findPath.backwardAStar(graph,input.length, connectionIds,n)
        return result
    }

    fun viterbiAlgorithm(
        input: String
    ): String{
        val graph = graphBuilder.constructGraph(
            input,
            yomiTrie,
            tangoTrie,
            tokenArray,
        )
        val result = findPath.viterbi(graph,input.length, connectionIds)
        return result
    }

}