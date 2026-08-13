package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.util.Locale

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
    VOCALIZATION_READING("vocalization-reading"),
    SINGLE_CHARACTER_READING("single-character-reading"),
    PUNCTUATION_ONLY("punctuation-only"),
    EXCLAMATORY_SURFACE("exclamatory-surface"),
    SINGLE_LETTER_SURFACE("single-letter-surface"),
    NUMERIC_SURFACE("numeric-surface"),
    FUNCTION_WORD_SURFACE("function-word-surface"),
    INTERJECTION_SURFACE("interjection-surface"),
    BOUND_MORPHEME("bound-morpheme"),
    INCOMPLETE_PLACEHOLDER("incomplete-placeholder"),
    EXPLANATORY_GLOSS("explanatory-gloss"),
    LONG_DEFINITION("long-definition"),
    DEFINITION_FRAGMENT("definition-fragment"),
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
        EnglishQualityFlag.DEFINITION_FRAGMENT,
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

    /*
     * A gloss is not useful as a conversion candidate when it is just a
     * number or a notation for a number.  These often enter this dictionary
     * through Chinese readings such as あー -> two and いー -> one.
     */
    private val numericSurfaceWords = setOf(
        "zero",
        "nought",
        "nil",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
        "billion",
        "trillion",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
        "thirteenth",
        "fourteenth",
        "fifteenth",
        "sixteenth",
        "seventeenth",
        "eighteenth",
        "nineteenth",
        "twentieth",
    )

    /*
     * Function words and pronouns have too little lexical information to be
     * safe standalone conversion candidates.  Upper-case abbreviations such
     * as US and IT are deliberately not matched by [isFunctionWordSurface].
     */
    private val functionWords = setOf(
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "is",
        "am",
        "are",
        "be",
        "was",
        "were",
        "been",
        "being",
        "do",
        "does",
        "did",
        "it",
        "this",
        "that",
        "these",
        "those",
        "here",
        "there",
        "who",
        "whom",
        "whose",
        "which",
        "what",
        "when",
        "where",
        "why",
        "how",
        "me",
        "my",
        "mine",
        "you",
        "your",
        "yours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "we",
        "us",
        "our",
        "ours",
        "they",
        "them",
        "their",
        "theirs",
        "some",
        "any",
        "no",
        "not",
        "nor",
    )

    /*
     * These are unambiguous sound effects or short response tokens.  Words
     * such as yes, right, okay, and gotcha are only rejected for a very short
     * reading; they remain useful when the reading is an actual loanword
     * (for example いぇす -> yes or おっけー -> okay).
     */
    private val nonLexicalInterjectionWords = setOf(
        "aah",
        "aaah",
        "ah",
        "alas",
        "argh",
        "blech",
        "bleh",
        "eek",
        "eew",
        "er",
        "erm",
        "gah",
        "hmm",
        "hmmm",
        "huh",
        "ick",
        "meh",
        "ooh",
        "ouch",
        "ow",
        "phew",
        "phooey",
        "pish",
        "pshaw",
        "sigh",
        "shh",
        "shush",
        "ugh",
        "ulp",
        "um",
        "ungh",
        "whoa",
        "wow",
        "yikes",
        "yahoo",
        "yay",
        "oops",
        "oops-a-daisy",
        "ha ha",
        "ha ha ha",
        "haha",
        "hahaha",
        "he he",
        "hehe",
        "hee hee",
        "hee hee hee",
        "hee-hee",
        "tee hee",
        "tee-hee",
        "hi hi hi",
        "uh huh",
        "uh-huh",
        "mm-hmm",
        "yeah yeah",
        "sure sure",
        "no no",
        "no-no",
    )
    private val shortResponseWords = setOf(
        "gotcha",
        "indeed",
        "right",
        "yes",
        "okay",
        "well",
        "sure",
        "understood",
        "oh",
        "yeah",
    )

    /*
     * JMdict glosses sometimes contain a compact definition without enough
     * words to trigger the long-definition rule.  Keep these in the audit
     * report, but do not expose them as conversion output.
     */
    private val definitionFragmentPattern = Regex(
        """(?ix)
            \A\s*(?:
                (?:the|a|an)\s+(?:act|action|process|state|condition|quality|property|
                    characteristic|kind|type|form|way|place|person|people|someone|something|
                    thing|device|method|sound|group|member|species|variety|family|genus|mark|
                    term|word|name|symbol|letter|part|piece|amount|degree|period|time|area|
                    region|side|edge|surface|material|substance|food|dish|drink|plant|animal|
                    bird|fish|insect|tree|flower|color|colour|language|country|city|river|mountain)
                |(?:person|people|someone|something|thing|device|method|sound|member|species|
                    variety|family|genus)\s+
                |(?:usually|generally|typically|specifically|especially|primarily|normally|often)\s+
            )
            |\b(?:the\s+act\s+of|the\s+state\s+of|the\s+process\s+of|the\s+quality\s+of|
                one's|someone's|something's)\b
            |\A(?:using|used)\s+.+\b(?:to|for|as|with)\b
            |\A(?:[a-z]+\s+){0,2}(?:that|which|who|where|while|when)\s+
        """.trimIndent(),
    )

    fun assess(entry: Dictionary): EnglishCandidateAssessment {
        val normalizedReading = normalizeReading(entry.yomi)
        val flags = buildList {
            if (normalizedReading != entry.yomi) add(EnglishQualityFlag.NORMALIZED_READING)
            if (entry.yomi.any(iterationMarks::contains) || entry.yomi == "ー") {
                add(EnglishQualityFlag.SPECIAL_READING)
            }
            if (isVocalizationReading(normalizedReading)) {
                add(EnglishQualityFlag.VOCALIZATION_READING)
            }
            if (normalizedReading.length == 1) add(EnglishQualityFlag.SINGLE_CHARACTER_READING)
            if (isPunctuationOnly(entry.tango)) add(EnglishQualityFlag.PUNCTUATION_ONLY)
            if (hasExclamatoryPunctuation(entry.tango)) {
                add(EnglishQualityFlag.EXCLAMATORY_SURFACE)
            }
            if (isSingleLetterSurface(entry.tango)) {
                add(EnglishQualityFlag.SINGLE_LETTER_SURFACE)
            }
            if (isNumericSurface(entry.tango)) {
                add(EnglishQualityFlag.NUMERIC_SURFACE)
            }
            if (isFunctionWordSurface(entry.tango)) {
                add(EnglishQualityFlag.FUNCTION_WORD_SURFACE)
            }
            if (isInterjectionSurface(entry.tango, normalizedReading)) {
                add(EnglishQualityFlag.INTERJECTION_SURFACE)
            }
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
            if (definitionFragmentPattern.containsMatchIn(entry.tango)) {
                add(EnglishQualityFlag.DEFINITION_FRAGMENT)
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
                isVocalizationReading(normalizedReading) ||
                normalizedReading.length == 1 ||
                isPunctuationOnly(surface) ||
                hasExclamatoryPunctuation(surface) ||
                isSingleLetterSurface(surface) ||
                isNumericSurface(surface) ||
                isFunctionWordSurface(surface) ||
                isInterjectionSurface(surface, normalizedReading) ||
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
                definitionFragmentPattern.containsMatchIn(surface) ||
                '(' in surface ||
                ')' in surface
    }

    private fun isVocalizationReading(reading: String): Boolean {
        val characters = reading.toList()
        if (characters.size < 2) return false
        val vowel = vowelBase(characters.first()) ?: return false
        return characters.drop(1).all { it == 'ー' || vowelBase(it) == vowel }
    }

    private fun vowelBase(character: Char): Char? = when (character) {
        'あ', 'ぁ' -> 'あ'
        'い', 'ぃ' -> 'い'
        'う', 'ぅ' -> 'う'
        'え', 'ぇ' -> 'え'
        'お', 'ぉ' -> 'お'
        else -> null
    }

    private fun hasExclamatoryPunctuation(surface: String): Boolean =
        surface.any { it == '!' || it == '?' || it == '！' || it == '？' }

    private fun isSingleLetterSurface(surface: String): Boolean =
        surface.length == 1 && surface.first().isLetter() && surface.first().code < 128

    private fun isNumericSurface(surface: String): Boolean {
        val normalized = surface.trim().lowercase(Locale.ROOT)
        if (normalized in numericSurfaceWords) return true
        if (normalized.matches(Regex("\\d+(?:st|nd|rd|th)?"))) return true
        return normalized.isNotEmpty() &&
                normalized.any(Char::isDigit) &&
                normalized.all { it.isDigit() || it in "^+-*/=." }
    }

    private fun isFunctionWordSurface(surface: String): Boolean {
        if (surface.isEmpty() || surface != surface.lowercase(Locale.ROOT)) return false
        return surface in functionWords
    }

    private fun isInterjectionSurface(surface: String, normalizedReading: String): Boolean {
        val normalizedSurface = surface.trim().lowercase(Locale.ROOT)
        if (normalizedSurface in nonLexicalInterjectionWords) return true
        return normalizedSurface in shortResponseWords &&
                (normalizedReading.length <= 2 || isVocalizationReading(normalizedReading))
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
