package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.nio.file.Path
import java.util.Locale

/** Shared input and selection for compilation, validation, and audit reports. */
class EnglishDictionarySource(
    val upstream: List<Dictionary>,
    val supplement: List<EnglishSupplementEntry>,
    val review: EnglishCandidateReview = EnglishCandidateReview.parseResource(),
) {
    val allowedCompounds: Set<Pair<String, String>> = supplement.map { it.dictionary.yomi to it.dictionary.tango }.toSet()
    val entries: List<Dictionary> = upstream + supplement.map { it.dictionary }
    val canonicalCompounds = allowedCompounds.map { (reading, surface) ->
        reading to (review.decisions[reading to surface]?.outputSurface ?: surface)
    }.toSet()
    val lexicalAssessments = EnglishDictionaryQuality.assessAll(entries, allowedCompounds)
    val assessments = lexicalAssessments.map { review.assess(it, canonicalCompounds) }
    val baselineRuntime = EnglishDictionaryQuality.runtimeEntriesFromAssessments(
        EnglishDictionaryQuality.assessAll(upstream), caseSensitive = false)
    val legacyRuntime = EnglishDictionaryQuality.runtimeEntriesFromAssessments(lexicalAssessments, caseSensitive = false)
    // After editorial case selection, upstream wins equal-cost overlaps of the same exact output.
    val runtimeEntries: List<Dictionary> = EnglishDictionaryQuality.runtimeEntriesFromAssessments(assessments)
        .sortedWith(compareBy({ it.yomi.length }, { it.yomi }, { it.cost }, { it.tango }))
    val addedEntries: List<Dictionary> = run {
        val baselinePairs = baselineRuntime.map(::pairKey).toSet()
        runtimeEntries.filter { pairKey(it) !in baselinePairs }
    }
    val changedExistingEntries: List<Dictionary> = run {
        val baseline = baselineRuntime.associateBy(::pairKey)
        runtimeEntries.filter { entry -> baseline[pairKey(entry)]?.let { it != entry } == true }
    }
    val newEnglishSurfaces: Int = run {
        val existing = baselineRuntime.map { it.tango.lowercase(Locale.ROOT) }.toSet()
        addedEntries.map { it.tango.lowercase(Locale.ROOT) }.toSet().count { it !in existing }
    }
    val addedReadingsForExistingSurfaces: Int = run {
        val existing = baselineRuntime.map { it.tango.lowercase(Locale.ROOT) }.toSet()
        addedEntries.count { it.tango.lowercase(Locale.ROOT) in existing }
    }

    init {
        require(runtimeEntries.map { it.yomi }.toSet().size <= Short.MAX_VALUE) {
            "English reading dictionary exceeds the consumer's signed Short term-ID limit"
        }
    }

    companion object {
        fun load(input: Path, supplement: Path, contextId: Int, review: Path = Path.of("src/main/english/candidate-review.tsv")): EnglishDictionarySource = EnglishDictionarySource(
            EnglishDictionaryBuilder().parse(input, contextId), EnglishReadingSupplement.parse(supplement, contextId),
            EnglishCandidateReview.parse(review),
        )

        fun loadResources(contextId: Int, upstreamRequired: Boolean = true): EnglishDictionarySource = EnglishDictionarySource(
            EnglishDictionaryBuilder().parseResource("/english-dictionary.txt", upstreamRequired, contextId),
            EnglishReadingSupplement.parseResource(contextId),
        )

        private fun pairKey(entry: Dictionary) = entry.yomi to entry.tango
    }
}
