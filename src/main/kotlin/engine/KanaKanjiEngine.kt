package com.kazumaproject.engine

import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.LoadedDictionary
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.ngram.EmptySystemNgramDictionary
import com.kazumaproject.ngram.EmptySystemUnigramDictionary
import com.kazumaproject.ngram.SystemNgramDictionary
import com.kazumaproject.ngram.SystemUnigramDictionary
import com.kazumaproject.viterbi.FindPath
import java.io.File

class KanaKanjiEngine(
    private val systemNgramDictionary: SystemNgramDictionary = EmptySystemNgramDictionary,
    private val systemUnigramDictionary: SystemUnigramDictionary = EmptySystemUnigramDictionary,
) {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var connectionMatrix: ConnectionMatrix
    private lateinit var findPath: FindPath
    private var dictionaries: List<LoadedDictionary> = emptyList()

    fun buildEngine(){
        buildEngineFromResourceDirectory("src/main/resources")
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
            buildEngineFromResourceDirectory(testResources)
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
            dictionaries,
        )
        val result = findPath.backwardAStar(graph,input.length, connectionMatrix,n)
        return result
    }

    fun convert(
        input: String
    ): ConversionResult {
        val graph = graphBuilder.constructGraph(
            input,
            dictionaries,
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

    fun loadDictionaries(loaded: List<LoadedDictionary>, matrixFile: File) {
        require(loaded.isNotEmpty()) { "At least one dictionary is required" }
        dictionaries = loaded
        graphBuilder = GraphBuilder()
        connectionMatrix = matrixFile.inputStream().buffered().use {
            ConnectionIdBuilder().readMatrix(it, matrixFile.path)
        }
        require(loaded.all { dictionary -> (dictionary.tokenArray.leftIds + dictionary.tokenArray.rightIds).all { it.toInt() in 0 until connectionMatrix.size } }) {
            "Dictionary context IDs do not match the connection matrix"
        }
        findPath = FindPath(systemNgramDictionary, systemUnigramDictionary)
    }

    fun convertDetailed(input: String): DetailedConversionResult {
        val graph = graphBuilder.constructGraph(input, dictionaries)
        val path = findPath.findBestPath(graph, input.length, connectionMatrix)
        return DetailedConversionResult(ConversionResult(input, path.map { it.toConversionPathNode() }), path.map { it.dictionaryId })
    }

    private fun buildEngineFromResourceDirectory(resourceDirectory: String) {
        val directory = File(resourceDirectory)
        loadDictionaries(listOf(LoadedDictionary.load("system", directory)), File(directory, "connectionId.dat"))
    }
}
