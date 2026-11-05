package conversion

import grammar.PhraseEvidence
import grammar.PhraseGrammar

internal enum class SegmentKind { EXACT, COMPLETION, LITERAL }

internal data class Segment(
    val start: Int,
    val end: Int,
    val surface: String,
    val kind: SegmentKind,
    val reading: String? = null,
    val cost: Int = 0,
    val inferredSpace: Boolean = false,
    val unknown: Boolean = false,
)

internal data class PhraseCandidate(
    val text: String,
    val segments: List<Segment>,
    val dictionaryCost: Int,
    val grammar: PhraseEvidence,
)

internal class PhraseConverter(private val dictionary: ReviewedDictionary) {
    private data class Path(
        val text: String = "",
        val segments: List<Segment> = emptyList(),
        val cost: Int = 0,
        val evidence: PhraseEvidence = PhraseEvidence(),
        val splits: Int = 0,
        val unknownChars: Int = 0,
        val addedChars: Int = 0,
    )

    fun convert(text: String, prefixMode: Boolean, limit: Int): List<PhraseCandidate> {
        require(text.isNotBlank() && text.length <= MAX_INPUT) {
            "--text must contain between 1 and $MAX_INPUT UTF-16 code units and cannot be blank"
        }
        require(limit in 1..MAX_RESULTS) { "--limit must be in 1..$MAX_RESULTS" }

        val grammar = PhraseGrammar(dictionary.lexicon)
        val edges = lattice(text, prefixMode)
        val paths = Array(text.length + 1) { mutableListOf<Path>() }
        paths[0].add(Path())
        for (offset in text.indices) {
            val current = paths[offset]
            if (current.isEmpty()) continue
            for (segment in edges[offset]) {
                val next = paths[segment.end]
                for (path in current) {
                    val segments = path.segments + segment
                    next += Path(
                        path.text + (if (segment.inferredSpace) " " else "") + segment.surface,
                        segments,
                        path.cost + segment.cost,
                        grammar.score(segments.map { it.surface }),
                        path.splits + if (segment.inferredSpace) 1 else 0,
                        path.unknownChars + if (segment.unknown) segment.end - segment.start else 0,
                        path.addedChars + if (segment.kind == SegmentKind.COMPLETION)
                            segment.reading!!.length - (segment.end - segment.start) else 0,
                    )
                }
                if (next.size > BEAM_WIDTH) {
                    next.sortWith(pathOrder)
                    next.subList(BEAM_WIDTH, next.size).clear()
                }
            }
        }
        return paths.last().sortedWith(pathOrder).distinctBy { it.text }.take(limit).map {
            PhraseCandidate(it.text, it.segments, it.cost, it.evidence)
        }
    }

    private fun lattice(text: String, prefixMode: Boolean): Array<MutableList<Segment>> {
        val edges = Array(text.length) { mutableListOf<Segment>() }
        val spans = inputWords.findAll(text).toList()
        val wordEnds = spans.map { it.range.last + 1 }.toSet()
        val exact = mutableMapOf<String, List<DictionaryCandidate>>()
        fun lookup(reading: String) = exact.getOrPut(reading) { dictionary.exact(reading) }
        var previousEnd = 0
        for (span in spans) {
            val start = span.range.first
            val end = span.range.last + 1
            if (previousEnd < start) edges[previousEnd] += literal(text, previousEnd, start)
            previousEnd = end

            val raw = span.value
            val reading = raw.lowercase().replace('’', '\'')
            val plain = latinWord.matches(reading)
            val complete = prefixMode && end == text.length && plain
            edges[start] += literal(text, start, end, unknown = true)

            if (!plain) {
                val candidates = lookup(reading)
                val normalized = reading.filterNot { it in keyboardPunctuation }
                val restored = if (normalized == reading || normalized.isEmpty()) emptyList() else
                    lookup(normalized).filter { it.surface.lowercase().replace('’', '\'') == reading }
                edges[start] += (candidates + restored).distinct().map { it.segment(start, end, start) }
            } else {
                val whole = lookup(reading)
                // Explicit word boundaries take precedence when the word is registered.
                if (spans.size > 1 && whole.isNotEmpty()) {
                    edges[start] += whole.map { it.segment(start, end, start) }
                    if (complete) edges[start] += completions(reading, start, end, start)
                } else {
                    for (offset in start until end) {
                        val remaining = reading.substring(offset - start)
                        for (prefix in dictionary.prefixes(remaining)) {
                            val stop = offset + prefix.length
                            if ((offset != start || stop != end) && !canSplit(prefix)) continue
                            edges[offset] += lookup(prefix).map { it.segment(offset, stop, start) }
                        }
                        if (complete) edges[offset] += completions(remaining, offset, end, start)
                    }
                }
            }

            val suffix = text.substring(start)
            for (phrase in dictionary.prefixes(suffix.lowercase())) {
                val stop = start + phrase.length
                if (' ' in phrase && stop in wordEnds && text.substring(start, stop).lowercase() == phrase) {
                    edges[start] += lookup(phrase).map { it.segment(start, stop, start) }
                }
            }
        }
        if (previousEnd < text.length) edges[previousEnd] += literal(text, previousEnd, text.length)
        return edges
    }

    private fun completions(reading: String, start: Int, end: Int, wordStart: Int): List<Segment> {
        if (reading.length < MIN_COMPLETION_PREFIX) return emptyList()
        return dictionary.complete(reading).filter { latinWord.matches(it.reading) }
            .map { it.segment(start, end, wordStart, SegmentKind.COMPLETION) }
    }

    private fun canSplit(reading: String) = reading.length >= 2 || reading == "a" || reading == "i"

    private fun literal(text: String, start: Int, end: Int, unknown: Boolean = false) =
        Segment(start, end, text.substring(start, end), SegmentKind.LITERAL, unknown = unknown)

    private fun DictionaryCandidate.segment(start: Int, end: Int, wordStart: Int, kind: SegmentKind = SegmentKind.EXACT) =
        Segment(start, end, surface, kind, reading, cost, inferredSpace = start != wordStart)

    companion object {
        private const val MAX_INPUT = 256
        private const val MAX_RESULTS = 50
        private const val BEAM_WIDTH = 96
        private const val MIN_COMPLETION_PREFIX = 2
        private const val keyboardPunctuation = "'-./"
        private val latinWord = Regex("[a-z]+")
        private val inputWords = Regex("""[\p{L}\p{N}][\p{L}\p{N}\p{M}]*(?:['’./_-][\p{L}\p{N}][\p{L}\p{N}\p{M}]*)*""")
        private val pathOrder = compareBy<Path> { it.unknownChars }
            .thenByDescending { it.evidence.clauses }
            .thenBy { if (it.evidence.clauses == 0) it.splits else 0 }
            .thenByDescending { it.evidence.score }
            .thenBy { it.splits }
            .thenBy { it.addedChars }
            .thenBy { it.cost }
            .thenBy { it.text }
    }
}
