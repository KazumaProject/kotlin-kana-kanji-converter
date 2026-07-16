package com.kazumaproject.engine

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.viterbi.FindPath
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.io.ObjectInputStream

class KanaKanjiEngine {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var yomiTrie: LOUDSWithTermId
    private lateinit var tangoTrie: LOUDS
    private lateinit var connectionMatrix: ConnectionMatrix
    private lateinit var findPath: FindPath
    private lateinit var tokenArray: TokenArray

    fun buildEngine(){
        buildEngineFromResourceDirectory("src/main/resources", mode = 1)
    }

    fun buildEngineForTest(){
        val testResources = "src/test/resources"
        val hasTestResources = listOf(
            "yomi.dat",
            "tango.dat",
            "token.dat",
            "connectionId.dat",
            "pos_table.dat",
        ).all { File("$testResources/$it").isFile }
        if (hasTestResources) {
            buildEngineFromResourceDirectory(testResources, mode = 0)
        } else {
            buildEngine()
        }
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
        val result = findPath.backwardAStar(graph,input.length, connectionMatrix,n)
        return result
    }

    fun convert(
        input: String
    ): ConversionResult {
        val graph = graphBuilder.constructGraph(
            input,
            yomiTrie,
            tangoTrie,
            tokenArray,
        )
        val bestPath = findPath.findBestPath(graph, input.length, connectionMatrix)
        return ConversionResult(
            input = input,
            bestPath = bestPath.map { it.toConversionPathNode() },
        )
    }

    fun viterbiAlgorithm(
        input: String
    ): String{
        return convert(input).value
    }

    private fun buildEngineFromResourceDirectory(
        resourceDirectory: String,
        mode: Int,
    ) {
        val objectInputYomi = ObjectInputStream(BufferedInputStream(FileInputStream("$resourceDirectory/yomi.dat")))
        val objectInputTango = ObjectInputStream(BufferedInputStream(FileInputStream("$resourceDirectory/tango.dat")))
        val objectInputTokenArray =
            ObjectInputStream(BufferedInputStream(FileInputStream("$resourceDirectory/token.dat")))
        val objectInputConnectionId = BufferedInputStream(FileInputStream("$resourceDirectory/connectionId.dat"))

        yomiTrie = LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
        tangoTrie = LOUDS().readExternalNotCompress(objectInputTango)
        graphBuilder = GraphBuilder()
        tokenArray = TokenArray()
        tokenArray.readExternalNotCompress(objectInputTokenArray)
        tokenArray.readPOSTable(mode)
        connectionMatrix = ConnectionIdBuilder().readMatrix(objectInputConnectionId, "$resourceDirectory/connectionId.dat")
        findPath = FindPath()
    }

}
