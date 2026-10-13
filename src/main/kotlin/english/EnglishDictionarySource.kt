package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.nio.file.Path
import java.util.Locale

/** Shared input and selection for compilation, validation, and audit reports. */
class EnglishDictionarySource(
    val upstream: List<Dictionary>,
    val supplement: List<EnglishSupplementEntry>,
) {
    val allowedCompounds: Set<Pair<String, String>> = supplement.map { it.dictionary.yomi to it.dictionary.tango }.toSet()
    val entries: List<Dictionary> = upstream + supplement.map { it.dictionary }
    val assessments = EnglishDictionaryQuality.assessAll(entries, allowedCompounds)
    val baselineRuntime = EnglishDictionaryQuality.runtimeEntries(upstream)
    // Upstream comes first, so an equal-cost overlap keeps its original surface.
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
        fun load(input: Path, supplement: Path, contextId: Int): EnglishDictionarySource = EnglishDictionarySource(
            EnglishDictionaryBuilder().parse(input, contextId), EnglishReadingSupplement.parse(supplement, contextId),
        )

        fun loadResources(contextId: Int, upstreamRequired: Boolean = true): EnglishDictionarySource = EnglishDictionarySource(
            EnglishDictionaryBuilder().parseResource("/english-dictionary.txt", upstreamRequired, contextId),
            EnglishReadingSupplement.parseResource(contextId),
        )

        private fun pairKey(entry: Dictionary) = entry.yomi to entry.tango.lowercase(Locale.ROOT)
    }
}
