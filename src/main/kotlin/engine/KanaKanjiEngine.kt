package com.kazumaproject.engine

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.grammar.GrammarConversion
import com.kazumaproject.grammar.GrammarMetadata
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.ngram.EmptyStandaloneUnigramDictionary
import com.kazumaproject.ngram.StandaloneUnigramDictionary
import com.kazumaproject.ngram.EmptySystemNgramDictionary
import com.kazumaproject.ngram.EmptySystemUnigramDictionary
import com.kazumaproject.ngram.SystemNgramDictionary
import com.kazumaproject.ngram.SystemUnigramDictionary
import com.kazumaproject.viterbi.FindPath
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.io.ObjectInputStream

class KanaKanjiEngine(
    private val systemNgramDictionary: SystemNgramDictionary = EmptySystemNgramDictionary,
    private val systemUnigramDictionary: SystemUnigramDictionary = EmptySystemUnigramDictionary,
    private val standaloneUnigramDictionary: StandaloneUnigramDictionary = EmptyStandaloneUnigramDictionary,
) {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var yomiTrie: LOUDSWithTermId
    private lateinit var tangoTrie: LOUDS
    private lateinit var connectionMatrix: ConnectionMatrix
    private lateinit var findPath: FindPath
    private lateinit var tokenArray: TokenArray
    private data class LoadedDictionary(val yomi: LOUDSWithTermId, val tango: LOUDS, val tokens: TokenArray)
    private var additionalDictionaries: List<LoadedDictionary> = emptyList()

    private fun constructGraph(input: String) =
        appendDictionaries(input, graphBuilder, graphBuilder.constructGraph(input, yomiTrie, tangoTrie, tokenArray),
            additionalDictionaries)

    private fun appendDictionaries(
        input: String, builder: GraphBuilder,
        graph: List<MutableList<MutableList<Node>>>,
        additional: List<LoadedDictionary>,
    ) = graph.also {
        additional.forEach { dictionary ->
            val extra = builder.constructGraph(input, dictionary.yomi, dictionary.tango, dictionary.tokens)
            // Share BOS/EOS and the connection matrix across all dictionary nodes.
            for (position in 1..input.length) graph[position].addAll(extra[position])
        }
    }

    /** Opens a grammar session over the currently loaded dictionaries. */
    fun grammar(metadata: File): GrammarConversion {
        val matrix = connectionMatrix
        val table = GrammarMetadata.read(metadata, matrix, tokenArray)
        val builder = graphBuilder
        val primary = LoadedDictionary(yomiTrie, tangoTrie, tokenArray)
        val additional = additionalDictionaries
        return GrammarConversion(table, matrix, findPath) { input ->
            appendDictionaries(input, builder, builder.constructGraph(input, primary.yomi, primary.tango, primary.tokens),
                additional)
        }
    }

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
        val graph = constructGraph(input)
        val result = findPath.backwardAStar(graph, input.length, connectionMatrix, n, input)
        return result
    }

    fun convert(
        input: String
    ): ConversionResult {
        val graph = constructGraph(input)
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

    fun buildEngineFromResourceDirectory(
        resourceDirectory: String,
        mode: Int,
        additionalResourceDirectories: List<String> = emptyList(),
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
        tokenArray.readPOSTable(mode, "$resourceDirectory/pos_table.dat")
        connectionMatrix = ConnectionIdBuilder().readMatrix(objectInputConnectionId, "$resourceDirectory/connectionId.dat")
        findPath = FindPath(systemNgramDictionary, systemUnigramDictionary, standaloneUnigramDictionary)
        additionalDictionaries = additionalResourceDirectories.map { directory ->
            val yomi = ObjectInputStream(BufferedInputStream(FileInputStream("$directory/yomi.dat"))).use {
                LOUDSWithTermId().readExternalNotCompress(it)
            }
            val tango = ObjectInputStream(BufferedInputStream(FileInputStream("$directory/tango.dat"))).use {
                LOUDS().readExternalNotCompress(it)
            }
            val tokens = TokenArray().apply {
                ObjectInputStream(BufferedInputStream(FileInputStream("$directory/token.dat"))).use {
                    readExternalNotCompress(it)
                }
                readPOSTable(mode, "$resourceDirectory/pos_table.dat")
            }
            LoadedDictionary(yomi, tango, tokens)
        }
    }

}
