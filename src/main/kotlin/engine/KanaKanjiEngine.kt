package com.kazumaproject.engine

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.graph.GraphDictionary
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.viterbi.FindPath
import java.io.ByteArrayInputStream
import java.io.File
import java.io.BufferedInputStream
import java.io.FileInputStream
import java.io.ObjectInputStream

class KanaKanjiEngine {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var dictionaries: List<GraphDictionary>
    private lateinit var connectionIds: ShortArray
    private lateinit var findPath: FindPath

    fun buildEngine(){
        buildEngineFromResourceDirectory("src/main/resources")
    }

    fun buildEngineForTest(){
        buildEngineFromResourceDirectory("src/main/resources")
    }

    private fun buildEngineFromResourceDirectory(resourceDirectory: String) {
        val resourceDir = File(resourceDirectory)
        require(resourceDir.exists()) { "Resource directory does not exist: $resourceDirectory" }

        graphBuilder = GraphBuilder()
        findPath = FindPath()

        dictionaries = buildList {
            loadDictionary(resourceDir, "")?.let(::add)
            loadDictionary(resourceDir, "_singleKanji")?.let(::add)
            loadDictionary(resourceDir, "_kotowaza")?.let(::add)
        }

        require(dictionaries.isNotEmpty()) { "No dictionaries were loaded from $resourceDirectory" }

        connectionIds = BufferedInputStream(
            FileInputStream(File(resourceDir, "connectionId.dat"))
        ).use {
            ConnectionIdBuilder().read(it)
        }
    }

    private fun loadDictionary(resourceDir: File, suffix: String): GraphDictionary? {
        val yomiPath = File(resourceDir, "yomi$suffix.dat")
        val tangoPath = File(resourceDir, "tango$suffix.dat")
        val tokenPath = File(resourceDir, "token$suffix.dat")

        if (!yomiPath.exists() || !tangoPath.exists() || !tokenPath.exists()) {
            return null
        }

        val yomiTrie = readYomiTrie(yomiPath)
        val tangoTrie = readTangoTrie(tangoPath)
        val tokenArray = readTokenArray(tokenPath).also {
            it.readPOSTable(1)
        }

        return GraphDictionary(
            yomiTrie = yomiTrie,
            tangoTrie = tangoTrie,
            tokenArray = tokenArray,
        )
    }

    private fun readYomiTrie(file: File): LOUDSWithTermId {
        val bytes = file.readBytes()
        val notCompressed = ObjectInputStream(ByteArrayInputStream(bytes)).use {
            LOUDSWithTermId().readExternalNotCompress(it)
        }
        if (notCompressed.labels.size > 2 && (notCompressed.termIdsSave.isNotEmpty() || notCompressed.termIds.isNotEmpty())) {
            return notCompressed
        }

        return ObjectInputStream(ByteArrayInputStream(bytes)).use {
            LOUDSWithTermId().readExternal(it)
        }
    }

    private fun readTangoTrie(file: File): LOUDS {
        val bytes = file.readBytes()
        val notCompressed = ObjectInputStream(ByteArrayInputStream(bytes)).use {
            LOUDS().readExternalNotCompress(it)
        }
        if (notCompressed.labels.size > 2) {
            return notCompressed
        }

        return ObjectInputStream(ByteArrayInputStream(bytes)).use {
            LOUDS().readExternal(it)
        }
    }

    private fun readTokenArray(file: File): TokenArray {
        val bytes = file.readBytes()
        val notCompressed = ObjectInputStream(ByteArrayInputStream(bytes)).use {
            TokenArray().readExternalNotCompress(it)
        }
        if (notCompressed.isLoaded()) {
            return notCompressed
        }

        return ObjectInputStream(ByteArrayInputStream(bytes)).use {
            TokenArray().readExternal(it)
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
        val result = findPath.backwardAStar(graph,input.length, connectionIds,n)
        return result
    }

    fun viterbiAlgorithm(
        input: String
    ): String{
        val graph = graphBuilder.constructGraph(
            input,
            dictionaries,
        )
        val result = findPath.viterbi(graph,input.length, connectionIds)
        return result
    }

}
