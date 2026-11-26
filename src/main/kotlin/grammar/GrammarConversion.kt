package com.kazumaproject.grammar

import com.kazumaproject.engine.ConversionPathNode
import com.kazumaproject.engine.ConversionResult
import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.viterbi.FindPath

data class GrammarSearchOptions(
    val constraints: List<GrammarConstraint> = emptyList(),
    val attributiveMismatchPenalty: Int = 0,
    val includeLattice: Boolean = false,
) {
    init {
        require(attributiveMismatchPenalty >= 0) { "Attributive penalty must be nonnegative" }
    }
}

data class RankingEvidence(
    val ngram: Boolean,
    val unigram: Boolean,
    // The standalone rule can be established on a different valid path for the same surface.
    val standaloneUnigram: Boolean,
) {
    val promoted: Boolean get() = ngram || unigram || standaloneUnigram
}

data class GrammarPathNode(
    val grammar: WordGrammar,
    val incomingConnectionCost: Int,
    val incomingGrammarPenalty: Int,
    val cumulativeCost: Long,
)

data class ConstraintMatch(val constraintIndex: Int, val alternativeIndices: List<Int>)

data class GrammarCandidate(
    val rank: Int,
    val path: ConversionResult,
    val annotations: List<GrammarPathNode>,
    val totalCost: Long,
    val eosConnectionCost: Int,
    val ranking: RankingEvidence,
    val constraintMatches: List<ConstraintMatch>,
) {
    val value: String get() = path.value
}

data class LatticeNode(
    val id: Int, val reading: String, val value: String, val start: Int, val end: Int,
    val wordCost: Int, val grammar: WordGrammar, val rejection: GrammarRejection?,
)

data class LatticeEdge(
    val from: Int, val to: Int, val fromState: Int, val toState: Int?,
    val connectionCost: Int, val grammarPenalty: Int,
    val rejection: GrammarRejection?,
)

data class LatticeTrace(val nodes: List<LatticeNode>, val edges: List<LatticeEdge>)

data class SearchStatistics(
    val lexicalNodes: Int,
    val latticeStates: Int,
    val allowedEdges: Long,
    val createdPathStates: Long,
    val expandedPathStates: Long,
    val maximumQueueSize: Int,
    val completedPaths: Long,
)

enum class GrammarFailure { NO_COMPLETE_PATH, NO_PATH_WITH_CONSTRAINTS }

data class RejectionCount(val rejection: GrammarRejection, val count: Int)

data class GrammarConversionResult(
    val input: String,
    val candidates: List<GrammarCandidate>,
    val minimumCostPath: GrammarCandidate?,
    val constraints: List<GrammarConstraint>,
    val failure: GrammarFailure?,
    val rejections: List<RejectionCount>,
    val statistics: SearchStatistics,
    val lattice: LatticeTrace?,
)

class GrammarConversion internal constructor(
    private val table: GrammarTable,
    private val matrix: ConnectionMatrix,
    private val findPath: FindPath,
    private val graph: (String) -> List<MutableList<MutableList<Node>>>,
) {
    fun context(id: Short): ContextGrammar = table.get(id)

    fun containsCandidate(input: String, value: String, options: GrammarSearchOptions = GrammarSearchOptions()): Boolean =
        GrammarSearch(graph(input), input.length, matrix, CompiledGrammar(input, options.constraints, table),
            options.attributiveMismatchPenalty, false).containsSurface(value)

    /** Uses whole-input basic-form dictionary tokens and preserves distinct attested classes. */
    fun inflect(reading: String, form: InflectionForm, surface: String? = null): List<InflectedWord> =
        wholeTokens(reading).filter { surface == null || it.tango == surface }.flatMap { token ->
            listOfNotNull(JapaneseInflection.classOf(table.get(token.l)), JapaneseInflection.classOf(table.get(token.r)))
                .distinct().mapNotNull { type ->
                    val lexeme = InflectionLexeme(reading, token.tango, type)
                    try {
                        JapaneseInflection.generate(lexeme, form)
                    } catch (_: IllegalArgumentException) {
                        // The context labels can describe a broader class than the literal surface supports.
                        null
                    }
                }
        }.distinct()

    /**
     * Evaluates dictionary particles/auxiliaries for the requested readings and the caller's context.
     * Following context contributes a connection cost. It supplies no semantic evidence.
     */
    fun particleConnections(
        readings: Iterable<String>, previousRightId: Short, followingLeftId: Short? = null,
    ): List<ParticleConnection> {
        val previous = table.get(previousRightId)
        return readings.distinct().flatMap { reading ->
            wholeTokens(reading).mapNotNull { node ->
                val word = table.word(node.l, node.r)
                if (word.left.partOfSpeech !in setOf("助詞", "助動詞")) return@mapNotNull null
                val (decision, reason, forms) = word.left.connectionFrom(previous)
                ParticleConnection(reading, node.tango, word, matrix.getCost(previousRightId, node.l),
                    followingLeftId?.let { matrix.getCost(node.r, it) }, forms, decision, reason)
            }
        }.distinct().sortedWith(compareBy<ParticleConnection> { it.decision != ConnectionDecision.SUPPORTED }
            .thenBy { it.previousConnectionCost + (it.followingConnectionCost ?: 0) })
    }

    private fun wholeTokens(reading: String): List<Node> =
        if (reading.isEmpty()) emptyList() else graph(reading)[reading.length].flatten().filter { it.sPos == 0 }

    fun convert(input: String, count: Int, options: GrammarSearchOptions = GrammarSearchOptions()): GrammarConversionResult {
        require(count > 0) { "Candidate count must be positive" }
        val constraints = options.constraints
        val grammar = CompiledGrammar(input, constraints, table)
        val search = GrammarSearch(graph(input), input.length, matrix, grammar,
            options.attributiveMismatchPenalty, options.includeLattice)
        val standalone = findPath.canMatchStandalone(input)
        val limit = findPath.rankingCandidateLimit(count, standalone)
        fun evidence(words: List<Node>, standaloneMatch: Boolean) = RankingEvidence(
            findPath.pathMatchesSystemNgram(words), findPath.pathMatchesSystemUnigram(words), standaloneMatch,
        )
        val minimum = search.bestPath()?.let { path ->
            val words = path.words.map { it.target.node }
            candidate(input, path, 1, evidence(words, standalone && findPath.matchesStandalone(input, words)),
                search.matches(path, constraints))
        }
        val best = LinkedHashMap<String, RankedPath>()
        var promoted = false
        search.enumerate { path ->
            val words = path.words.map { it.target.node }
            val value = words.joinToString("") { it.tango }
            val standaloneMatch = standalone && findPath.matchesStandalone(input, words)
            val existing = best[value]
            if (existing == null) {
                val ranking = evidence(words, standaloneMatch)
                best[value] = RankedPath(path, ranking)
                promoted = promoted || ranking.promoted
            } else if (standaloneMatch) {
                existing.ranking = existing.ranking.copy(standaloneUnigram = true)
                promoted = true
            }
            best.size < limit && !(best.size >= count && promoted)
        }
        val ranked = best.values.sortedWith(compareByDescending<RankedPath> { it.ranking.promoted }
            .thenBy { it.path.cost }).take(count).mapIndexed { index, result ->
            candidate(input, result.path, index + 1, result.ranking, search.matches(result.path, constraints))
        }
        val failure = if (minimum != null) null else if (constraints.isEmpty()) {
            GrammarFailure.NO_COMPLETE_PATH
        } else {
            GrammarFailure.NO_PATH_WITH_CONSTRAINTS
        }
        return GrammarConversionResult(input, ranked, minimum, constraints, failure,
            search.rejections(), search.statistics(), search.trace(table))
    }

    private class RankedPath(val path: GrammarSearch.Path, var ranking: RankingEvidence)

    private fun candidate(
        input: String, path: GrammarSearch.Path, rank: Int, evidence: RankingEvidence, matches: List<ConstraintMatch>,
    ): GrammarCandidate {
        var cost = 0L
        val words = ArrayList<ConversionPathNode>(path.words.size)
        val annotations = path.words.map { edge ->
            val node = edge.target.node
            cost += edge.cost
            words += ConversionPathNode(node.key, node.tango, node.l.toInt(), node.r.toInt(), node.wcost,
                cost.coerceIn(Int.MIN_VALUE.toLong(), Int.MAX_VALUE.toLong()).toInt(),
                node.sPos, node.sPos + node.len)
            GrammarPathNode(table.word(node.l, node.r), edge.connection, edge.penalty, cost)
        }
        return GrammarCandidate(rank, ConversionResult(input, words), annotations, path.cost, path.eos.connection, evidence, matches)
    }
}
