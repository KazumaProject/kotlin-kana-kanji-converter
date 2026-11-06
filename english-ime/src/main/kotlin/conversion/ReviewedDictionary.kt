package conversion

import grammar.CompactGrammarRoles
import grammar.GrammarRoles
import grammar.Lexicon
import grammar.lookupKey
import louds.LOUDS
import louds.louds_with_term_id.LOUDSWithTermId
import succinctBitVector.SuccinctBitVector
import tokenArray.TokenArray
import java.io.File
import java.io.IOException
import java.io.ObjectInputFilter
import java.io.ObjectInputStream
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.util.BitSet
import java.util.PriorityQueue
import java.util.Properties

internal data class DictionaryCandidate(val reading: String, val surface: String, val cost: Int)

internal class ReviewedDictionary private constructor(
    private val reading: LOUDSWithTermId,
    private val words: LOUDS,
    private val tokens: TokenArray,
    val grammarRoles: GrammarRoles,
) {
    private val readingIndex = SuccinctBitVector(reading.LBS)
    private val leafIndex = SuccinctBitVector(reading.isLeaf)
    private val wordIndex = SuccinctBitVector(words.LBS)
    private val tokenIndex = SuccinctBitVector(tokens.bitvector)

    fun prefixes(text: String): List<String> = reading.commonPrefixSearch(text, readingIndex)

    internal fun allCandidates(): Sequence<DictionaryCandidate> =
        reading.predictiveSearch("", readingIndex).asSequence().flatMap { exact(it).asSequence() }

    fun exact(text: String): List<DictionaryCandidate> {
        val node = reading.getNodeIndex(text, readingIndex)
        if (node < 0 || !reading.isLeaf[node]) return emptyList()
        val term = reading.getTermId(node, leafIndex)
        return tokens.getListDictionaryByYomiTermId(term, tokenIndex).map { entry ->
            val surface = if (entry.nodeId == -1) text else words.getLetter(entry.nodeId, wordIndex)
            DictionaryCandidate(text, surface, entry.wordCost.toInt())
        }
    }

    fun complete(prefix: String, surfacePrefix: String? = null): List<DictionaryCandidate> {
        val best = PriorityQueue(completionOrder.reversed())
        for (key in reading.predictiveSearch(prefix, readingIndex)) {
            if (key == prefix || !completionKey.matches(key)) continue
            for (candidate in exact(key)) {
                if (surfacePrefix != null && !lookupKey(candidate.surface).startsWith(surfacePrefix)) continue
                if (best.size < MAX_COMPLETIONS) {
                    best.add(candidate)
                } else if (completionOrder.compare(candidate, best.element()) < 0) {
                    best.remove()
                    best.add(candidate)
                }
            }
        }
        return best.sortedWith(completionOrder)
    }

    companion object {
        private const val MAX_COMPLETIONS = 128
        private val completionKey = Regex("[a-z0-9]+")
        private val completionOrder = compareBy<DictionaryCandidate> { it.cost }
            .thenBy { it.reading.length }.thenBy { it.reading }.thenBy { it.surface }

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
            val compact = grammar.resolve("categories.ecat").toPath()
            val roles = if (Files.notExists(compact, NOFOLLOW_LINKS)) {
                val lexicon = Lexicon.load(grammar)
                GrammarRoles { surface, _ -> lexicon.lookup(surface).flatMap { it.dictionaries }.toSet() }
            } else {
                CompactGrammarRoles.load(compact, metadata.getProperty("categories.ecat.sha256"))
            }
            return ReviewedDictionary(reading, words, tokens, roles)
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
