package com.kazumaproject.grammar

import com.kazumaproject.graph.Node
import java.util.BitSet

/** The target selector checks both contexts. Neighbors check previous.rid and following.lid. */
data class GrammarInterpretation(
    val token: GrammarSelector = GrammarSelector(),
    val previous: GrammarSelector? = null,
    val following: GrammarSelector? = null,
)

sealed interface GrammarConstraint {
    /** UTF-16 boundary between lattice words. */
    data class Boundary(val position: Int) : GrammarConstraint

    /** Exactly one token covers [start, end). Alternatives apply to the entire interpretation. */
    data class Span(
        val start: Int,
        val end: Int,
        val alternatives: List<GrammarInterpretation>,
    ) : GrammarConstraint {
        constructor(start: Int, end: Int, role: GrammarRole) :
            this(start, end, listOf(GrammarInterpretation(GrammarSelector(role = role))))
    }
}

internal class CompiledGrammar(input: String, constraints: List<GrammarConstraint>, table: GrammarTable) {
    private data class Alternative(val word: BitSet, val previous: BitSet?, val following: BitSet?)
    private data class Span(val constraintIndex: Int, val end: Int, val alternatives: List<Alternative>)
    private val boundaries = IntArray(input.length + 1) { -1 }
    private val spans = arrayOfNulls<Span>(input.length)
    private val covering = IntArray(input.length) { -1 }
    private val stem = table.adjectivalStem
    private val attributive = table.adjectivalAttributive

    init {
        constraints.forEachIndexed { index, constraint ->
            when (constraint) {
                is GrammarConstraint.Boundary -> {
                    checkOffset(input, constraint.position)
                    boundaries[constraint.position] = index
                }
                is GrammarConstraint.Span -> {
                    checkOffset(input, constraint.start)
                    checkOffset(input, constraint.end)
                    require(constraint.start < constraint.end && constraint.alternatives.isNotEmpty()) {
                        "A span must have positive length and at least one interpretation"
                    }
                    require((constraint.start until constraint.end).all { covering[it] < 0 }) {
                        "Use alternatives for the same span. Grammar spans must be disjoint."
                    }
                    for (i in constraint.start until constraint.end) covering[i] = index
                    spans[constraint.start] = Span(index, constraint.end,
                        constraint.alternatives.map { interpretation ->
                            val role = interpretation.token.role
                            val previous = interpretation.previous?.let(table::matching)
                            if (role == GrammarRole.ADJECTIVAL_ATTRIBUTIVE && previous != null) previous.and(stem)
                            Alternative(table.matching(interpretation.token),
                                previous ?: stem.takeIf { role == GrammarRole.ADJECTIVAL_ATTRIBUTIVE },
                                interpretation.following?.let(table::matching))
                        })
                }
            }
        }
    }

    /** Each bit represents an entire interpretation. Locally compatible edges are insufficient
     * when a token has correlated left and right alternatives. */
    fun nodeRejection(node: Node): GrammarRejection? {
        val start = node.sPos
        val end = start + node.len
        for (position in start + 1 until end) {
            if (boundaries[position] >= 0) return GrammarRejection(boundaries[position], RejectionReason.CROSSES_BOUNDARY)
        }
        val span = spans[start]
        if (span != null && end == span.end) {
            if (span.alternatives.none { matchesWord(it, node) }) {
                return GrammarRejection(span.constraintIndex, RejectionReason.TOKEN_GRAMMAR_MISMATCH)
            }
            return null
        }
        for (position in start until end) {
            if (covering[position] >= 0) return GrammarRejection(covering[position], RejectionReason.CROSSES_SPAN)
        }
        return null
    }

    fun interpretations(node: Node, previous: Node): BitSet? {
        if (node.len.toInt() == 0) return null
        val span = spans[node.sPos] ?: return null
        return BitSet(span.alternatives.size).apply {
            span.alternatives.forEachIndexed { index, candidate ->
                if (matchesWord(candidate, node) && matches(candidate.previous, previous.r)) set(index)
            }
        }
    }

    fun previousRejection(node: Node, interpretations: BitSet?): GrammarRejection? =
        if (interpretations?.isEmpty == true) GrammarRejection(
            checkNotNull(spans[node.sPos]).constraintIndex, RejectionReason.PREVIOUS_CONTEXT_MISMATCH,
        ) else null

    fun followingRejection(node: Node, next: Node, interpretations: BitSet?): GrammarRejection? {
        if (interpretations == null) return null
        val span = checkNotNull(spans[node.sPos])
        var index = interpretations.nextSetBit(0)
        while (index >= 0) {
            if (matches(span.alternatives[index].following, next.l)) return null
            index = interpretations.nextSetBit(index + 1)
        }
        return GrammarRejection(span.constraintIndex, RejectionReason.FOLLOWING_CONTEXT_MISMATCH)
    }

    fun satisfiedSpan(node: Node, next: Node, interpretations: BitSet): ConstraintMatch {
        val span = checkNotNull(spans[node.sPos])
        val matches = span.alternatives.indices.filter { interpretations[it] && matches(span.alternatives[it].following, next.l) }
        return ConstraintMatch(span.constraintIndex, matches)
    }

    fun penalty(previous: Node, next: Node, mismatchCost: Int): Int =
        if (mismatchCost > 0 && attributive[next.l.toInt()] && !stem[previous.r.toInt()]) mismatchCost else 0

    private fun matchesWord(alternative: Alternative, node: Node): Boolean =
        alternative.word[node.l.toInt()] && alternative.word[node.r.toInt()]

    private fun matches(mask: BitSet?, id: Short): Boolean = mask == null || mask[id.toInt()]

    private fun checkOffset(input: String, offset: Int) {
        require(offset in 0..input.length &&
            !(offset > 0 && offset < input.length && input[offset - 1].isHighSurrogate() && input[offset].isLowSurrogate())) {
            "Invalid UTF-16 grammar boundary: $offset"
        }
    }
}

enum class RejectionReason {
    CROSSES_BOUNDARY, CROSSES_SPAN, TOKEN_GRAMMAR_MISMATCH, PREVIOUS_CONTEXT_MISMATCH, FOLLOWING_CONTEXT_MISMATCH,
}

data class GrammarRejection(val constraintIndex: Int, val reason: RejectionReason)
