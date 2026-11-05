package conversion

import grammar.Lexicon
import louds.LOUDS
import louds.louds_with_term_id.LOUDSWithTermId
import succinctBitVector.SuccinctBitVector
import tokenArray.TokenArray
import java.io.File
import java.io.IOException
import java.io.ObjectInputFilter
import java.io.ObjectInputStream
import java.util.BitSet
import java.util.Properties

internal data class DictionaryCandidate(val reading: String, val surface: String, val cost: Int)

internal class ReviewedDictionary private constructor(
    private val reading: LOUDSWithTermId,
    private val words: LOUDS,
    private val tokens: TokenArray,
    val lexicon: Lexicon,
) {
    private val readingIndex = SuccinctBitVector(reading.LBS)
    private val leafIndex = SuccinctBitVector(reading.isLeaf)
    private val wordIndex = SuccinctBitVector(words.LBS)
    private val tokenIndex = SuccinctBitVector(tokens.bitvector)

    fun prefixes(text: String): List<String> = reading.commonPrefixSearch(text, readingIndex)

    fun exact(text: String): List<DictionaryCandidate> {
        val node = reading.getNodeIndex(text, readingIndex)
        if (node < 0 || !reading.isLeaf[node]) return emptyList()
        val term = reading.getTermId(node, leafIndex)
        return tokens.getListDictionaryByYomiTermId(term, tokenIndex).map { entry ->
            val surface = if (entry.nodeId == -1) text else words.getLetter(entry.nodeId, wordIndex)
            DictionaryCandidate(text, surface, entry.wordCost.toInt())
        }
    }

    fun complete(prefix: String): List<DictionaryCandidate> =
        reading.predictiveSearch(prefix, readingIndex, MAX_COMPLETION_READINGS)
            .filter { it != prefix }
            .flatMap(::exact)

    companion object {
        private const val MAX_COMPLETION_READINGS = 128

        fun load(directory: File): ReviewedDictionary {
            val grammar = directory.resolve("grammar")
            val metadata = Properties().apply { grammar.resolve("bundle.properties").inputStream().use(::load) }
            require(metadata.getProperty("schemaVersion") == "1" && metadata.getProperty("reviewComplete") == "true") {
                "Expected a completed reviewed dictionary in $directory"
            }
            val reading = directory.resolve("reading.dat").readPayload { input ->
                val bits = input.readObject() as BitSet
                val leaves = input.readObject() as BitSet
                val labels = input.readObject() as CharArray
                val termIds = input.readObject() as IntArray
                require(labels.size == bits.cardinality() + 1 && termIds.size == leaves.cardinality() &&
                    termIds.isNotEmpty() && termIds.all { it in 1..termIds.size })
                LOUDSWithTermId(bits, labels, leaves, termIds)
            }
            val words = directory.resolve("word.dat").readPayload { input ->
                val bits = input.readObject() as BitSet
                val leaves = input.readObject() as BitSet
                val labels = input.readObject() as CharArray
                require(labels.size == bits.cardinality() + 1)
                LOUDS(bits, labels, leaves)
            }
            val tokens = directory.resolve("token.dat").readPayload { input ->
                val costs = input.readObject() as ShortArray
                val nodes = input.readObject() as IntArray
                val bits = input.readObject() as BitSet
                require(costs.size == nodes.size && costs.size == bits.cardinality() &&
                    bits.length() - costs.size >= reading.termIdsSaved.size &&
                    nodes.all { it == -1 || (it > 0 && words.isLeaf[it]) })
                TokenArray().apply {
                    wordCostList = costs
                    nodeIdList = nodes
                    bitvector = bits
                }
            }
            return ReviewedDictionary(reading, words, tokens, Lexicon.load(grammar))
        }
    }
}

private val payloadTypes = setOf(BitSet::class.java, LongArray::class.java, IntArray::class.java,
    ShortArray::class.java, CharArray::class.java)

private fun <T> File.readPayload(read: (ObjectInputStream) -> T): T {
    try {
        return ObjectInputStream(inputStream().buffered()).use { input ->
            input.setObjectInputFilter { info ->
                when {
                    info.arrayLength() > 4_000_000 || info.depth() > 4 -> ObjectInputFilter.Status.REJECTED
                    info.serialClass() == null -> ObjectInputFilter.Status.UNDECIDED
                    info.serialClass() in payloadTypes -> ObjectInputFilter.Status.ALLOWED
                    else -> ObjectInputFilter.Status.REJECTED
                }
            }
            read(input)
        }
    } catch (failure: IOException) {
        throw IllegalArgumentException("Cannot read reviewed dictionary payload $this", failure)
    } catch (failure: IllegalArgumentException) {
        throw IllegalArgumentException("Invalid reviewed dictionary payload $this", failure)
    } catch (failure: ClassCastException) {
        throw IllegalArgumentException("Invalid reviewed dictionary payload $this", failure)
    }
}
