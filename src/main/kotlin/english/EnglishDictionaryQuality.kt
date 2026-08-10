package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary

/**
 * How suitable a JMdict English gloss is for a normal conversion candidate.
 *
 * PRIMARY is a lexical word or phrase that can be shown directly. REVIEW is
 * still a valid dictionary translation, but it is usually an explanation,
 * disambiguation, or a long definition. EXCLUDED is a source artifact that
 * should not become an English output token.
 */
enum class EnglishCandidateStatus {
    PRIMARY,
    REVIEW,
    EXCLUDED,
}

enum class EnglishQualityFlag(val code: String) {
    NORMALIZED_READING("reading-normalized"),
    SPECIAL_READING("special-reading"),
    SINGLE_CHARACTER_READING("single-character-reading"),
    PUNCTUATION_ONLY("punctuation-only"),
    BOUND_MORPHEME("bound-morpheme"),
    INCOMPLETE_PLACEHOLDER("incomplete-placeholder"),
    EXPLANATORY_GLOSS("explanatory-gloss"),
    LONG_DEFINITION("long-definition"),
    PARENTHETICAL("parenthetical"),
}

data class EnglishCandidateAssessment(
    val source: Dictionary,
    val normalizedReading: String,
    val status: EnglishCandidateStatus,
    val score: Int,
    val flags: List<EnglishQualityFlag>,
) {
    /** Cost used by the clean runtime dictionary, or null when the row is not selected. */
    val runtimeCost: Int?
        get() = when (status) {
            EnglishCandidateStatus.PRIMARY -> source.cost.toInt()
            EnglishCandidateStatus.REVIEW, EnglishCandidateStatus.EXCLUDED -> null
        }

    fun toRuntimeEntry(): Dictionary? = runtimeCost?.let { cost ->
        source.copy(
            yomi = normalizedReading,
            cost = cost.toShort(),
        )
    }
}

data class EnglishDictionaryQualitySummary(
    val rawEntries: Int,
    val primaryEntries: Int,
    val reviewEntries: Int,
    val excludedEntries: Int,
    val runtimeEntries: Int,
    val rawReadings: Int,
    val runtimeReadings: Int,
    val flagCounts: Map<EnglishQualityFlag, Int>,
)

object EnglishDictionaryQuality {
    private val reviewFlags = setOf(
        EnglishQualityFlag.EXPLANATORY_GLOSS,
        EnglishQualityFlag.LONG_DEFINITION,
        EnglishQualityFlag.PARENTHETICAL,
    )

    /*
     * These are dictionary-definition constructions, not English words in
     * themselves. They remain in the audit report, but are not emitted into
     * the clean runtime dictionary.
     */
    private val explanatoryGlossPattern = Regex(
        """(?:^\s*(?:used\s+(?:to|after|with|for|as)|indicates?\b|counter\s+(?:for|used)\b|softens?\b|regardless\s+of\b|whether\b|no\s+matter\b|followed\s+by\b|preceded\s+by\b|person\s+(?:who|with|of)\b|people\s+(?:who|with)\b|someone\s+who\b|something\s+(?:that|which)\b|thing\s+(?:or|that|which)\b|device\s+used\b|method\s+(?:of|used)\b|sound\s+(?:of|used)\b|one's\b|to\s+be\b|in\s+(?:a|the)\b|with\s+(?:a|the)\b|for\s+(?:a|the)\b|by\s+(?:a|the)\b|any\b|(?:type|kind|form|group|member|species|variety|family|genus)\s+of\b)|\b(?:used\s+(?:to|for|as|with)|person\s+(?:who|with|of)|people\s+(?:who|with))\b)""",
        RegexOption.IGNORE_CASE,
    )

    private val ellipsisCharacters = setOf('…')
    private val iterationMarks = setOf('ゝ', 'ゞ')
    private val hyphenCharacters = setOf('-', '‐', '‑', '‒', '–', '—')

    fun assess(entry: Dictionary): EnglishCandidateAssessment {
        val normalizedReading = normalizeReading(entry.yomi)
        val flags = buildList {
            if (normalizedReading != entry.yomi) add(EnglishQualityFlag.NORMALIZED_READING)
            if (entry.yomi.any(iterationMarks::contains) || entry.yomi == "ー") {
                add(EnglishQualityFlag.SPECIAL_READING)
            }
            if (normalizedReading.length == 1) add(EnglishQualityFlag.SINGLE_CHARACTER_READING)
            if (isPunctuationOnly(entry.tango)) add(EnglishQualityFlag.PUNCTUATION_ONLY)
            if (entry.tango.firstOrNull()?.let(hyphenCharacters::contains) == true ||
                entry.tango.lastOrNull()?.let(hyphenCharacters::contains) == true
            ) {
                add(EnglishQualityFlag.BOUND_MORPHEME)
            }
            if (entry.tango.contains("...") || entry.tango.any(ellipsisCharacters::contains)) {
                add(EnglishQualityFlag.INCOMPLETE_PLACEHOLDER)
            }
            if (explanatoryGlossPattern.containsMatchIn(entry.tango)) {
                add(EnglishQualityFlag.EXPLANATORY_GLOSS)
            }
            val startsWithLowercase = entry.tango.firstOrNull()?.isLowerCase() == true
            if (entry.tango.count { it == ' ' } + 1 >= 8 ||
                entry.tango.length >= 64 ||
                (entry.tango.length >= 45 && startsWithLowercase)
            ) {
                add(EnglishQualityFlag.LONG_DEFINITION)
            }
            if ('(' in entry.tango || ')' in entry.tango) {
                add(EnglishQualityFlag.PARENTHETICAL)
            }
        }

        val status = classifyStatus(entry, normalizedReading)
        val reviewFlagCount = flags.count(reviewFlags::contains)
        val score = when (status) {
            EnglishCandidateStatus.PRIMARY -> 100
            EnglishCandidateStatus.REVIEW -> (100 - reviewFlagCount * 20).coerceAtLeast(40)
            EnglishCandidateStatus.EXCLUDED -> 0
        }

        return EnglishCandidateAssessment(
            source = entry,
            normalizedReading = normalizedReading,
            status = status,
            score = score,
            flags = flags,
        )
    }

    fun assessAll(entries: List<Dictionary>): List<EnglishCandidateAssessment> = entries.map(::assess)

    /**
     * Produces the noise-removed runtime dictionary.
     *
     * Only PRIMARY rows are emitted. REVIEW and EXCLUDED rows remain available
     * in the audit reports so the filtering decision is inspectable, but they
     * cannot become conversion output. Normalizing the small hiragana ka/ke
     * and de-duplicating the resulting pairs makes the runtime dictionary
     * stable across corpus updates.
     */
    fun runtimeEntries(entries: List<Dictionary>): List<Dictionary> {
        val selected = linkedMapOf<Pair<String, String>, RuntimeSelection>()
        entries.forEach { entry ->
            val normalizedReading = normalizeReading(entry.yomi)
            val status = classifyStatus(entry, normalizedReading)
            if (status != EnglishCandidateStatus.PRIMARY) return@forEach

            val runtimeCost = entry.cost.toInt()
            val runtimeEntry = entry.copy(
                yomi = normalizedReading,
                cost = runtimeCost.toShort(),
            )
            val key = runtimeEntry.yomi to runtimeEntry.tango
            val candidate = RuntimeSelection(runtimeEntry, runtimeCost)
            val current = selected[key]
            if (current == null || candidate.isPreferredTo(current)) {
                selected[key] = candidate
            }
        }
        return selected.values.map(RuntimeSelection::entry)
    }

    fun runtimeEntriesFromAssessments(assessments: List<EnglishCandidateAssessment>): List<Dictionary> {
        val selected = linkedMapOf<Pair<String, String>, EnglishCandidateAssessment>()
        assessments.forEach { assessment ->
            val runtimeEntry = assessment.toRuntimeEntry() ?: return@forEach
            val key = runtimeEntry.yomi to runtimeEntry.tango
            val current = selected[key]
            if (current == null || compareForRuntime(assessment, current) < 0) {
                selected[key] = assessment
            }
        }
        return selected.values.mapNotNull(EnglishCandidateAssessment::toRuntimeEntry)
    }

    fun summarize(entries: List<Dictionary>): EnglishDictionaryQualitySummary {
        val assessments = assessAll(entries)
        val runtime = runtimeEntriesFromAssessments(assessments)
        val flagCounts = EnglishQualityFlag.entries
            .mapNotNull { flag ->
                val count = assessments.count { flag in it.flags }
                count.takeIf { it > 0 }?.let { flag to it }
            }
            .toMap()
        return EnglishDictionaryQualitySummary(
            rawEntries = entries.size,
            primaryEntries = assessments.count { it.status == EnglishCandidateStatus.PRIMARY },
            reviewEntries = assessments.count { it.status == EnglishCandidateStatus.REVIEW },
            excludedEntries = assessments.count { it.status == EnglishCandidateStatus.EXCLUDED },
            runtimeEntries = runtime.size,
            rawReadings = entries.map(Dictionary::yomi).toSet().size,
            runtimeReadings = runtime.map(Dictionary::yomi).toSet().size,
            flagCounts = flagCounts,
        )
    }

    /** Maps NFKC's small hiragana ka/ke result to the normal input spelling. */
    fun normalizeReading(reading: String): String = reading
        .replace('ゕ', 'か')
        .replace('ゖ', 'け')

    private fun classifyStatus(entry: Dictionary, normalizedReading: String): EnglishCandidateStatus {
        if (isHardExcluded(entry, normalizedReading)) return EnglishCandidateStatus.EXCLUDED
        if (isReviewCandidate(entry.tango)) return EnglishCandidateStatus.REVIEW
        return EnglishCandidateStatus.PRIMARY
    }

    private fun isHardExcluded(entry: Dictionary, normalizedReading: String): Boolean {
        val surface = entry.tango
        return entry.yomi.indexOfAny(charArrayOf('ゝ', 'ゞ')) >= 0 ||
                entry.yomi == "ー" ||
                normalizedReading.length == 1 ||
                isPunctuationOnly(surface) ||
                surface.firstOrNull()?.let(hyphenCharacters::contains) == true ||
                surface.lastOrNull()?.let(hyphenCharacters::contains) == true ||
                surface.contains("...") ||
                surface.any(ellipsisCharacters::contains)
    }

    private fun isReviewCandidate(surface: String): Boolean {
        val startsWithLowercase = surface.firstOrNull()?.isLowerCase() == true
        return explanatoryGlossPattern.containsMatchIn(surface) ||
                surface.count { it == ' ' } + 1 >= 8 ||
                surface.length >= 64 ||
                (surface.length >= 45 && startsWithLowercase) ||
                '(' in surface ||
                ')' in surface
    }

    private data class RuntimeSelection(
        val entry: Dictionary,
        val runtimeCost: Int,
    ) {
        fun isPreferredTo(other: RuntimeSelection): Boolean {
            return runtimeCost < other.runtimeCost
        }
    }

    private fun compareForRuntime(
        left: EnglishCandidateAssessment,
        right: EnglishCandidateAssessment,
    ): Int {
        val statusComparison = statusRank(left.status).compareTo(statusRank(right.status))
        if (statusComparison != 0) return statusComparison
        return (left.runtimeCost ?: Int.MAX_VALUE).compareTo(right.runtimeCost ?: Int.MAX_VALUE)
    }

    private fun statusRank(status: EnglishCandidateStatus): Int = when (status) {
        EnglishCandidateStatus.PRIMARY -> 0
        EnglishCandidateStatus.REVIEW -> 1
        EnglishCandidateStatus.EXCLUDED -> 2
    }

    private fun isPunctuationOnly(surface: String): Boolean =
        surface.isNotEmpty() && surface.all { !it.isLetterOrDigit() && !it.isWhitespace() }
}
