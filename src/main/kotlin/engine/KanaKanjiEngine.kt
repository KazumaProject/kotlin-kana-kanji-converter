package com.kazumaproject.engine

import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.ngram.EmptyStandaloneUnigramDictionary
import com.kazumaproject.ngram.StandaloneUnigramDictionary
import com.kazumaproject.ngram.EmptySystemNgramDictionary
import com.kazumaproject.ngram.EmptySystemUnigramDictionary
import com.kazumaproject.ngram.SystemNgramDictionary
import com.kazumaproject.ngram.SystemUnigramDictionary
import com.kazumaproject.viterbi.FindPath
import java.io.File
import java.io.ObjectInputStream

class KanaKanjiEngine(
    private val systemNgramDictionary: SystemNgramDictionary = EmptySystemNgramDictionary,
    private val systemUnigramDictionary: SystemUnigramDictionary = EmptySystemUnigramDictionary,
    private val standaloneUnigramDictionary: StandaloneUnigramDictionary = EmptyStandaloneUnigramDictionary,
) {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var systemDictionary: LoadedDictionary
    private var categoryDictionaries: List<LoadedDictionary> = emptyList()
    private lateinit var connectionMatrix: ConnectionMatrix
    private lateinit var findPath: FindPath

    fun buildEngine(
        categories: Set<String> = emptySet(),
        resourceDirectory: File = File("src/main/resources"),
        archive: File? = null,
    ) {
        require(categories.all { it.matches(Regex("[a-z_]+")) }) { "Invalid category ID" }
        DictionaryAssetSource(resourceDirectory, archive).use { source ->
            systemDictionary = source.dictionary()
            categoryDictionaries = categories.map { source.dictionary(it) }
            val (leftIds, rightIds) = ObjectInputStream(source.open("pos_table.dat")).use {
                (it.readObject() as ShortArray).toList() to (it.readObject() as ShortArray).toList()
            }
            require(leftIds.size == rightIds.size) { "Invalid shared POS table" }
            (listOf(systemDictionary) + categoryDictionaries).forEach {
                it.tokens.leftIds = leftIds
                it.tokens.rightIds = rightIds
            }
            connectionMatrix = source.open("connectionId.dat", "connectionId.dat.zip").use {
                ConnectionIdBuilder().readMatrix(it)
            }
        }
        graphBuilder = GraphBuilder()
        findPath = FindPath(systemNgramDictionary, systemUnigramDictionary, standaloneUnigramDictionary)
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
            buildEngine(resourceDirectory = File(testResources))
        } else {
            buildEngine()
        }
    }

    fun nBestPath(
        input: String,
        n: Int
    ): List<String>{
        return candidates(input, n).map { it.text }
    }

    /** Conversion paths plus optional completions from the selected category assets. */
    fun candidates(input: String, n: Int, predict: Boolean = false): List<ConversionCandidate> {
        if (n <= 0) return emptyList()
        val converted = findPath.rankedPaths(graph(input), input.length, connectionMatrix, n, input).map {
            ConversionCandidate(it.value, it.cost, matchedBySystemDictionary = it.matchedBySystemDictionary)
        }
        if (!predict) return converted
        // Verified consumer defaults: input length 3..16, lookahead 3, standard
        // aggressiveness, 1500 per missing character, four candidates per category.
        val predicted = if (input.length in 3..16) categoryDictionaries.flatMap { dictionary ->
            dictionary.yomi.predictiveSearch(input, input.length + 3).asSequence()
                .filter { it.length > input.length }
                .flatMap { reading ->
                    val term = dictionary.yomi.getTermId(dictionary.yomi.getNodeIndex(reading))
                    dictionary.tokens.getListDictionaryByYomiTermId(term).asSequence().map { token ->
                        ConversionCandidate(
                            text = dictionary.surface(token.nodeId, reading),
                            score = token.wordCost.toInt() + (reading.length - input.length) * 1500,
                            kind = "prediction", reading = reading, category = dictionary.category,
                        )
                    }
                }.sortedBy { it.score }.take(4).toList()
        } else emptyList()
        return (converted + predicted).sortedWith(
            compareByDescending<ConversionCandidate> { it.matchedBySystemDictionary }
                .thenBy { it.score }.thenBy { it.text }
        ).distinctBy { it.text }.take(n)
    }

    private fun graph(input: String): List<MutableList<MutableList<com.kazumaproject.graph.Node>>> {
        val graph = graphBuilder.constructGraph(input, systemDictionary.yomi, systemDictionary.tango, systemDictionary.tokens)
        categoryDictionaries.forEach {
            graphBuilder.appendDictionary(input, graph, it.yomi, it.tango, it.tokens)
        }
        return graph
    }

    fun convert(
        input: String
    ): ConversionResult {
        val graph = graph(input)
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

}

/** The cost remains separate from scoreless system-dictionary promotion. */
data class ConversionCandidate(
    val text: String,
    val score: Int,
    val kind: String = "conversion",
    val reading: String? = null,
    val category: String? = null,
    val matchedBySystemDictionary: Boolean = false,
)
