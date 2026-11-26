package com.kazumaproject.grammar

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import java.util.BitSet
import java.util.IdentityHashMap
import java.util.PriorityQueue

internal class GrammarSearch(
    graph: List<MutableList<MutableList<Node>>>,
    length: Int,
    private val matrix: ConnectionMatrix,
    private val grammar: CompiledGrammar,
    private val penalty: Int,
    trace: Boolean,
) {
    class State(val id: Int, val node: Node, val interpretations: BitSet?) {
        val edges = mutableListOf<Edge>()
        var suffixCost: Long? = null
        var bestEdge: Edge? = null
    }

    data class Edge(val target: State, val connection: Int, val penalty: Int) {
        val cost: Long get() = connection.toLong() + penalty + target.node.wcost
    }

    data class Path(val words: List<Edge>, val eos: Edge, val cost: Long)

    private class PathState(val state: State, val parent: PathState?, val edge: Edge?, val cost: Long) {
        fun path(): Path {
            val words = ArrayList<Edge>()
            var previous = parent
            while (previous?.edge != null) {
                words.add(checkNotNull(previous.edge))
                previous = previous.parent
            }
            words.reverse()
            return Path(words, checkNotNull(edge), cost)
        }
    }

    private val outgoing = List(length + 1) { mutableListOf<Node>() }
    private val statesByEnd = List(length + 2) { mutableListOf<State>() }
    private var nextStateId = 0
    private val ordinaryStates = IdentityHashMap<Node, State>()
    private val statesByNode = IdentityHashMap<Node, MutableMap<BitSet?, State>>()
    private val originalNodes = graph.flatMap { it.flatten() }
    private val traceIds = if (trace) IdentityHashMap<Node, Int>().apply {
        originalNodes.forEachIndexed { index, node -> put(node, index) }
    } else null
    private val traceEdges = if (trace) mutableListOf<LatticeEdge>() else null
    private val nodeRejections = IdentityHashMap<Node, GrammarRejection>()
    private val reasons = mutableMapOf<GrammarRejection, Int>()
    private var createdPathStates = 0L
    private var queueMaximum = 0
    private var completedPaths = 0L
    private var expandedPathStates = 0L
    private var allowedEdges = 0L
    private val bos: State
    private val eosNode = graph[length + 1].single().single()

    init {
        val bosNode = graph[0].single().single()
        require(bosNode.len.toInt() == 0 && eosNode.len.toInt() == 0 && eosNode.sPos == length)
        bos = stateFor(bosNode, null, 0)
        for (end in 1..length) {
            graph[end].forEach { group ->
                group.forEach { node ->
                    require(node.len > 0 && node.sPos >= 0 && node.sPos + node.len == end)
                    val rejection = grammar.nodeRejection(node)
                    if (rejection == null) {
                        outgoing[node.sPos] += node
                    } else {
                        nodeRejections[node] = rejection
                        countRejection(rejection)
                    }
                }
            }
        }
        outgoing[length] += eosNode

        // The state records only interpretations still possible after the incoming edge.
        // All paths with the same node and remaining interpretations can share suffix costs.
        for (position in 0..length) {
            for (state in statesByEnd[position]) {
                for (next in outgoing[position]) {
                    val interpretations = grammar.interpretations(next, state.node)
                    val rejection = grammar.followingRejection(state.node, next, state.interpretations)
                        ?: grammar.previousRejection(next, interpretations)
                    if (rejection != null) {
                        countRejection(rejection)
                        traceEdges?.add(traceEdge(state, next, null, rejection))
                        continue
                    }
                    val end = if (next === eosNode) length + 1 else next.sPos + next.len
                    val target = stateFor(next, interpretations, end)
                    val edge = Edge(target, matrix.getCost(state.node.r, next.l), grammar.penalty(state.node, next, penalty))
                    state.edges += edge
                    traceEdges?.add(traceEdge(state, next, edge, null))
                    allowedEdges++
                }
            }
        }

        statesByEnd[length + 1].forEach { it.suffixCost = 0L }
        for (position in length downTo 0) {
            for (state in statesByEnd[position]) {
                for (edge in state.edges) {
                    val suffix = edge.target.suffixCost ?: continue
                    val total = edge.cost + suffix
                    val current = state.suffixCost
                    if (current == null || total < current) {
                        state.suffixCost = total
                        state.bestEdge = edge
                    }
                }
            }
        }
    }

    private fun stateFor(node: Node, interpretations: BitSet?, end: Int): State {
        fun create() = State(nextStateId++, node, interpretations).also { statesByEnd[end] += it }
        return if (interpretations == null) ordinaryStates.getOrPut(node, ::create)
        else statesByNode.getOrPut(node) { HashMap() }.getOrPut(interpretations, ::create)
    }

    private fun traceEdge(state: State, next: Node, edge: Edge?, rejection: GrammarRejection?): LatticeEdge {
        val ids = checkNotNull(traceIds)
        return LatticeEdge(ids.getValue(state.node), ids.getValue(next), state.id, edge?.target?.id,
            edge?.connection ?: matrix.getCost(state.node.r, next.l),
            edge?.penalty ?: grammar.penalty(state.node, next, penalty), rejection)
    }

    private fun countRejection(rejection: GrammarRejection) {
        reasons.merge(rejection, 1, Int::plus)
    }

    /** Reverse Viterbi over the same state DAG used by A*. */
    fun bestPath(): Path? {
        val total = bos.suffixCost ?: return null
        val words = mutableListOf<Edge>()
        var edge = checkNotNull(bos.bestEdge)
        while (edge.target.node !== eosNode) {
            words += edge
            edge = checkNotNull(edge.target.bestEdge)
        }
        return Path(words, edge, total)
    }

    fun enumerate(visit: (Path) -> Boolean) {
        if (bos.suffixCost == null) return
        val queue = PriorityQueue<PathState> { left, right ->
            (left.cost + checkNotNull(left.state.suffixCost)).compareTo(
                right.cost + checkNotNull(right.state.suffixCost),
            )
        }
        queue.add(PathState(bos, null, null, 0))
        createdPathStates++
        queueMaximum = 1
        while (queue.isNotEmpty()) {
            val current = queue.remove()
            expandedPathStates++
            if (current.state.node === eosNode) {
                completedPaths++
                if (!visit(current.path())) break
                continue
            }
            for (edge in current.state.edges) {
                if (edge.target.suffixCost == null) continue
                queue.add(PathState(edge.target, current, edge, current.cost + edge.cost))
                createdPathStates++
            }
            queueMaximum = maxOf(queueMaximum, queue.size)
        }
    }

    fun containsSurface(surface: String): Boolean {
        if (bos.suffixCost == null) return false
        val offsets = IdentityHashMap<State, MutableSet<Int>>().apply { put(bos, mutableSetOf(0)) }
        for (states in statesByEnd) {
            for (state in states) {
                val starts = offsets.remove(state) ?: continue
                if (state.node === eosNode) return surface.length in starts
                for (edge in state.edges) {
                    if (edge.target.suffixCost == null) continue
                    val text = if (edge.target.node === eosNode) "" else edge.target.node.tango
                    for (start in starts) {
                        if (surface.startsWith(text, start)) {
                            offsets.getOrPut(edge.target) { mutableSetOf() }.add(start + text.length)
                        }
                    }
                }
            }
        }
        return false
    }

    fun matches(path: Path, constraints: List<GrammarConstraint>): List<ConstraintMatch> {
        val result = constraints.mapIndexedNotNull { index, constraint ->
            if (constraint is GrammarConstraint.Boundary) ConstraintMatch(index, emptyList()) else null
        }.toMutableList()
        path.words.forEachIndexed { index, edge ->
            val state = edge.target
            state.interpretations?.let { interpretations ->
                val next = path.words.getOrNull(index + 1)?.target ?: path.eos.target
                result += grammar.satisfiedSpan(state.node, next.node, interpretations)
            }
        }
        return result.sortedBy { it.constraintIndex }
    }

    fun statistics(): SearchStatistics = SearchStatistics(
        originalNodes.size - 2, statesByEnd.sumOf { it.size }, allowedEdges,
        createdPathStates, expandedPathStates, queueMaximum, completedPaths,
    )

    fun rejections(): List<RejectionCount> = reasons.map { (reason, count) -> RejectionCount(reason, count) }

    fun trace(table: GrammarTable): LatticeTrace? = traceEdges?.let { edges ->
        LatticeTrace(originalNodes.mapIndexed { index, node ->
            LatticeNode(index, node.key, node.tango, node.sPos, node.sPos + node.len, node.wcost,
                table.word(node.l, node.r), nodeRejections[node])
        }, edges)
    }
}
