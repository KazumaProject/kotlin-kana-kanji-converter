package com.kazumaproject.quality

import com.kazumaproject.dictionary.models.Dictionary

/** Source-scoped cleanup: never delete parentheses or repeated text indiscriminately. */
class CandidateNormalizer(
    private val readings: Map<String, Set<String>>,
    private val overrides: ManualOverrides = ManualOverrides(),
    private val lexical: LexicalEvidence = LexicalEvidence.load(),
    private val canonical: (String, String) -> Boolean = { surface, reading -> lexical.has(reading, surface, "facility") },
) {
    data class Result(val entries: List<Dictionary>, val reason: String, val state: String = if (entries.isEmpty()) "held" else "accepted")

    fun normalize(row: SourceRow): Result {
        overrides.normalization(row)?.let { return it }
        val word = row.word
        if (word.yomi.isBlank() || word.tango.isBlank() || word.yomi.any { it.isWhitespace() || it.isISOControl() } || word.tango.any { it.isISOControl() })
            return Result(emptyList(), "invalid-text", "excluded")
        if (row.source != "place") return Result(listOf(word), "unchanged")
        if (PostalLexicon.instruction(word.tango)) return Result(emptyList(), "postal-instruction", "excluded")
        val parsed = parsePlace(word.tango) ?: return Result(emptyList(), "malformed-parentheses", "excluded")
        val (head, groups) = parsed
        if (groups.isEmpty() || groups.all { isAnnotation(it) }) {
            val candidates = linkedSetOf<Pair<String, String>>()
            // Canonical facility names are suffixes of a town+facility postal
            // concatenation. The removed prefix must have an evidenced reading.
            if (hasRepeatedSpan(head) && buildingLike(head)) {
                for (split in 2 until head.length - 2) {
                    val prefix = head.substring(0, split)
                    val target = head.substring(split)
                    readings[prefix].orEmpty().forEach { prefixReading ->
                        if (word.yomi.startsWith(prefixReading)) {
                            val remainder = word.yomi.removePrefix(prefixReading)
                            val possible = if (groups.isEmpty()) setOf(remainder) else readings[target].orEmpty() + lexical.readings[target].orEmpty()
                            possible.forEach { targetReading ->
                                if (targetReading.isNotBlank() && remainder.startsWith(targetReading) && (groups.isNotEmpty() || remainder == targetReading) && canonical(target, targetReading)) candidates.add(targetReading to target)
                            }
                        }
                    }
                }
                // A verified existing full facility name is never shortened.
                val attestedHead = if (groups.isEmpty()) canonical(head, word.yomi) else
                    (readings[head].orEmpty() + lexical.readings[head].orEmpty()).any { word.yomi.startsWith(it) && canonical(head, it) }
                if (!attestedHead) {
                    if (candidates.size == 1) {
                        val (reading, surface) = candidates.single()
                        return Result(listOf(word.copy(yomi = reading, tango = surface)), "canonical-building:attested-town-and-facility")
                    }
                    return Result(emptyList(), "unresolved-facility-concatenation")
                }
            }
        }
        if (groups.isEmpty()) return Result(listOf(word), "unchanged")
        val headReadings = (readings[head].orEmpty() + lexical.readings[head].orEmpty()).filter { word.yomi.startsWith(it) }
        if (headReadings.size != 1) return Result(emptyList(), "ambiguous-head-reading")
        val headReading = headReadings.single()
        val result = mutableListOf(word.copy(yomi = headReading, tango = head))
        var remaining = word.yomi.removePrefix(headReading)
        var unresolved = false
        groups.forEachIndexed { index, group ->
            if (isAnnotation(group)) {
                // Once a verified head is found, annotations need no inferred reading.
                // Mixed alias/annotation groups must still have an evidenced boundary.
                if (index < groups.lastIndex && groups.drop(index + 1).any { !isAnnotation(it) }) unresolved = true
                remaining = ""
            } else if (!unresolved) {
                val known = (readings[group].orEmpty() + lexical.readings[group].orEmpty()).filter { remaining.startsWith(it) }
                val reading = when {
                    // The final component must consume the complete remainder.
                    // A shorter known variant (たかばた) is not a competing split
                    // of the single remaining component (たかばたけ).
                    index == groups.lastIndex && remaining in known -> remaining
                    known.size == 1 -> known.single()
                    else -> null
                }
                if (reading == null) unresolved = true
                else {
                    result.add(word.copy(yomi = reading, tango = group))
                    remaining = remaining.removePrefix(reading)
                }
            }
        }
        return Result(result, if (unresolved || remaining.isNotEmpty()) "split-with-unresolved-alias" else "split-or-remove-annotation")
    }

    private fun parsePlace(surface: String): Pair<String, List<String>>? {
        val first = surface.indexOfFirst { it in "()（）" }
        if (first < 0) return surface to emptyList()
        if (surface[first] !in "(（" || first == 0) return null
        val groups = mutableListOf<String>()
        var index = first
        while (index < surface.length) {
            val open = surface[index]
            if (open !in "(（") return null
            val close = if (open == '(') ')' else '）'
            val end = surface.indexOf(close, index + 1)
            if (end < 0) return null
            val group = surface.substring(index + 1, end)
            if (group.isBlank() || group.any { it in "()（）" }) return null
            groups.add(group)
            index = end + 1
        }
        return surface.substring(0, first) to groups
    }

    private fun isAnnotation(value: String): Boolean = PostalLexicon.annotation(value)

    companion object {
        fun buildingLike(value: String) = Regex("(?:タワー|ビル|スクエア|ハイツ|ヒルズ)$").containsMatchIn(value)
        fun hasRepeatedSpan(value: String): Boolean = (2..minOf(24, value.length / 2)).any { size ->
            (0..value.length - size * 2).any { start -> value.regionMatches(start, value, start + size, size) }
        }
        fun proposedSurfaces(surface: String): Set<String> {
            val head = surface.substringBefore('(').substringBefore('（')
            if (!buildingLike(head) || !hasRepeatedSpan(head)) return emptySet()
            return (2 until head.length - 2).map { head.substring(it) }.toSet()
        }
    }
}
