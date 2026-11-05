package grammar

data class CandidateEvaluation(
    val candidate: String,
    val score: Int,
    val reasons: List<String>,
    val interpretations: List<Form>,
)

internal enum class Agreement { FIRST_SINGULAR, THIRD_SINGULAR, OTHER }
private data class Expectation(val reason: String, val allowed: Set<String>, val competing: Set<String>)

class ContextEvaluator(private val lexicon: Lexicon) {
    fun evaluate(text: String, candidates: List<String>): List<CandidateEvaluation> {
        val parts = text.split("<candidate>")
        require(parts.size == 2) { "Text must contain exactly one <candidate> marker" }
        require(candidates.isNotEmpty() && candidates.none { it.isBlank() }) { "Supply nonblank candidates" }
        val before = tokens(parts[0]).takeLastWhile { it !in clauseEnd }.map(::dictionaries)
        val after = tokens(parts[1]).takeWhile { it !in clauseEnd }.map(::dictionaries)
        val expectation = expectation(before, after)
        return candidates.map { candidate ->
            val forms = lexicon.lookup(candidate)
            val syntacticForms = forms.filterNot { form -> form.dictionaries.all {
                it.startsWith("domain_") || it.startsWith("register_") || it.startsWith("identifier_")
            } }
            val supporting = forms.filter { form -> expectation?.allowed?.any { it in form.dictionaries } == true }
            when {
                forms.isEmpty() -> CandidateEvaluation(candidate, 0, listOf("UNKNOWN_CANDIDATE"), emptyList())
                expectation == null -> CandidateEvaluation(candidate, 0, listOf("INSUFFICIENT_CONTEXT"), forms)
                supporting.isNotEmpty() -> CandidateEvaluation(candidate, 1, listOf(expectation.reason), supporting)
                syntacticForms.isNotEmpty() && syntacticForms.all { form -> expectation.competing.any { it in form.dictionaries } } ->
                    CandidateEvaluation(candidate, -1, listOf("EXPECTED_${expectation.reason}"), forms)
                else -> CandidateEvaluation(candidate, 0, listOf("UNRESOLVED_INTERPRETATION"), forms)
            }
        }.sortedByDescending { it.score }
    }

    private fun expectation(before: List<Set<String>>, after: List<Set<String>>): Expectation? {
        if (before.isEmpty() && after.isNotEmpty()) {
            val subject = subject(after.takeWhile { categories -> categories.none { it in verbForms } })
            if (subject != null && after.any { categories -> categories.any { it in verbForms } }) {
                return finite(subject).let { Expectation("QUESTION_AUXILIARY", it.allowed intersect auxiliaries, auxiliaries) }
            }
        }

        val words = before.dropLastWhile { categories -> categories.any { it.startsWith("adverb_") || it == "negation" } }
        val last = words.lastOrNull() ?: return null
        val lastAsDeterminer = when {
            "det_count_singular" in last -> Expectation("SINGULAR_COUNT_NOUN", singularNouns, nominalForms + verbForms)
            "det_count_plural" in last -> Expectation("PLURAL_COUNT_NOUN", pluralNouns, nominalForms + verbForms)
            "det_uncountable" in last -> Expectation("MASS_NOUN", setOf("noun_uncountable"), nominalForms + verbForms)
            else -> null
        }
        if (lastAsDeterminer != null && ("pronoun_demonstrative" !in last || words.size > 1)) return lastAsDeterminer

        val inverted = words.size >= 2 && words.first().any { it in auxiliaries } && subject(words.drop(1)) != null
        val auxiliary = if (inverted) words.first() else last
        if (inverted || subject(words.dropLast(1)) != null || words.dropLast(1).any { "aux_modal" in it }) {
            when {
                auxiliary.any { it == "aux_modal" || it.startsWith("aux_do_") } ->
                    return Expectation("BARE_AFTER_MODAL_OR_DO", setOf("verb_base", "aux_be_base"), verbForms)
                auxiliary.any { it.startsWith("aux_have_") } ->
                    return Expectation("PERFECT_PARTICIPLE", setOf("verb_past_participle", "aux_be_participle"), verbForms)
                auxiliary.any { it.startsWith("aux_be_") } ->
                    return Expectation("BE_COMPLEMENT", beComplement, verbForms)
            }
        }
        return subject(words)?.let(::finite)
    }

    private fun subject(words: List<Set<String>>): Agreement? {
        if (words.isEmpty() || words.any { it.isEmpty() || "conjunction_subordinating" in it }) return null
        val coordinator = words.indexOfFirst { "conjunction_coordinating" in it }
        if (coordinator >= 0) {
            if (words[coordinator] != dictionaries("and")) return null
            return if (subject(words.take(coordinator)) != null && subject(words.drop(coordinator + 1)) != null) {
                Agreement.OTHER
            } else null
        }
        val preposition = words.withIndex().firstOrNull { (index, roles) ->
            index > 0 && "preposition" in roles
        }?.index ?: -1
        if (preposition > 0) {
            if (subject(words.drop(preposition + 1)) == null) return null
            return subject(words.take(preposition))
        }
        if (words.size == 1) {
            val roles = words.single()
            if ("pronoun_subject_1sg" in roles) return Agreement.FIRST_SINGULAR
            if ("pronoun_subject_2nd" in roles || "pronoun_subject_plural" in roles ||
                "pronoun_indefinite_plural" in roles) return Agreement.OTHER
            if ("pronoun_subject_3sg" in roles || "pronoun_indefinite_singular" in roles) return Agreement.THIRD_SINGULAR
            if ("det_demonstrative_singular" in roles && "pronoun_demonstrative" in roles) return Agreement.THIRD_SINGULAR
            if ("det_demonstrative_plural" in roles && "pronoun_demonstrative" in roles) return Agreement.OTHER
        }
        val head = words.last()
        if (words.size == 1 && ("noun_collective" in head ||
                head.any { it in verbForms } && head.none { it in pluralNouns || it == "noun_uncountable" })) return null
        if (words.dropLast(1).any { roles -> roles.none { it.startsWith("det_") || it.startsWith("adjective_") } }) return null
        val singular = head.any { it in singularNouns || it == "noun_uncountable" }
        val plural = head.any { it in pluralNouns }
        return when {
            singular && !plural -> Agreement.THIRD_SINGULAR
            plural && !singular -> Agreement.OTHER
            else -> null
        }
    }

    private fun finite(subject: Agreement) =
        Expectation("FINITE_$subject", finiteCategories(subject), verbForms)

    private fun dictionaries(token: String): Set<String> =
        lexicon.lookup(token).flatMap { it.dictionaries }.toSet()

    companion object {
        private val clauseEnd = setOf(".", "!", "?", ";", ":", ",")
        private val tokenPattern = Regex("[\\p{L}\\p{N}]+(?:['’-][\\p{L}\\p{N}]+)*|[.!?;:,]")
        private fun tokens(text: String) = tokenPattern.findAll(text).map { it.value }.toList()

        private val singularNouns = setOf("noun_count_singular")
        private val pluralNouns = setOf("noun_count_plural", "noun_plural_only")
        private val nominalForms = singularNouns + pluralNouns + "noun_uncountable"
        private val auxiliaries = setOf(
            "aux_modal", "aux_do_3sg", "aux_do_base", "aux_do_past", "aux_have_3sg", "aux_have_base", "aux_have_past",
            "aux_be_present_1sg", "aux_be_present_3sg", "aux_be_present_other", "aux_be_past_1sg_3sg", "aux_be_past_other",
        )
        private val verbForms = auxiliaries + setOf(
            "verb_base", "verb_present_non3sg", "verb_present_3sg", "verb_past", "verb_past_participle", "verb_ing",
            "aux_be_base", "aux_be_participle", "aux_be_ing",
        )
        private val beComplement = setOf(
            "verb_ing", "verb_past_participle", "aux_be_ing", "aux_be_participle", "adjective_predicative",
        ) + pluralNouns + setOf("noun_uncountable", "noun_proper")
    }
}

internal fun finiteCategories(subject: Agreement): Set<String> {
    val present = when (subject) {
        Agreement.FIRST_SINGULAR -> setOf("aux_be_present_1sg", "verb_present_non3sg", "aux_have_base", "aux_do_base")
        Agreement.THIRD_SINGULAR -> setOf("aux_be_present_3sg", "verb_present_3sg", "aux_have_3sg", "aux_do_3sg")
        Agreement.OTHER -> setOf("aux_be_present_other", "verb_present_non3sg", "aux_have_base", "aux_do_base")
    }
    val pastBe = if (subject == Agreement.OTHER) "aux_be_past_other" else "aux_be_past_1sg_3sg"
    return present + setOf(pastBe, "verb_past", "aux_have_past", "aux_do_past", "aux_modal")
}
