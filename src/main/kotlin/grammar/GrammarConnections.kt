package com.kazumaproject.grammar

enum class ConnectionDecision { SUPPORTED, INCOMPATIBLE, UNCLASSIFIED }

enum class ConnectionReason {
    ADJECTIVAL_STEM, NOMINAL_CASE, FINAL_PROHIBITIVE, VERB_IRREALIS, VERB_CONTINUATIVE,
    VERB_PAST_STEM, VERB_TE_STEM, VERB_CONDITIONAL, NO_RULE,
}

data class ParticleConnection(
    val reading: String,
    val surface: String,
    val grammar: WordGrammar,
    val previousConnectionCost: Int,
    val followingConnectionCost: Int?,
    val requiredPreviousForms: Set<String>,
    val decision: ConnectionDecision,
    val reason: ConnectionReason,
)

internal fun ContextGrammar.connectionFrom(previous: ContextGrammar): Triple<ConnectionDecision, ConnectionReason, Set<String>> {
    val previousIsVerb = previous.partOfSpeech == "動詞"
    return when {
        partOfSpeech == "助動詞" && conjugationType == "特殊・ダ" && conjugationForm == "体言接続" ->
            connection("形容動詞語幹" in previous.subdivisions, ConnectionReason.ADJECTIVAL_STEM)
        partOfSpeech == "助詞" && subdivisions[0] == "格助詞" && subdivisions[1] == "一般" ->
            // Nominalized clauses can also be followed by case particles. Detect clear nominal evidence only.
            if (previous.partOfSpeech == "名詞" || previous.partOfSpeech == "代名詞") {
                connection(true, ConnectionReason.NOMINAL_CASE)
            } else connection(null, ConnectionReason.NOMINAL_CASE)
        partOfSpeech == "助詞" && subdivisions[0] == "終助詞" && contextLabel == "な" ->
            connection(previousIsVerb && previous.conjugationForm == "基本形", ConnectionReason.FINAL_PROHIBITIVE, "基本形")
        partOfSpeech == "助動詞" && conjugationType == "特殊・ナイ" ->
            if (previousIsVerb) connection(previous.conjugationForm == "未然形", ConnectionReason.VERB_IRREALIS, "未然形")
            else connection(null, ConnectionReason.VERB_IRREALIS, "未然形")
        partOfSpeech == "助動詞" && conjugationType == "特殊・マス" ->
            connection(previousIsVerb && previous.conjugationForm == "連用形", ConnectionReason.VERB_CONTINUATIVE, "連用形")
        partOfSpeech == "助動詞" && conjugationType == "特殊・タ" -> {
            val forms = arrayOf("連用形", "連用タ接続")
            if (previousIsVerb) connection(previous.conjugationForm in forms, ConnectionReason.VERB_PAST_STEM, *forms)
            else connection(null, ConnectionReason.VERB_PAST_STEM, *forms)
        }
        partOfSpeech == "助詞" && subdivisions[0] == "接続助詞" && contextLabel in setOf("て", "で") -> {
            val forms = arrayOf("連用形", "連用タ接続", "連用テ接続", "連用デ接続")
            if (previousIsVerb) connection(previous.conjugationForm in forms, ConnectionReason.VERB_TE_STEM, *forms)
            else connection(null, ConnectionReason.VERB_TE_STEM, *forms)
        }
        partOfSpeech == "助詞" && subdivisions[0] == "接続助詞" && contextLabel == "ば" ->
            connection(previous.conjugationForm == "仮定形", ConnectionReason.VERB_CONDITIONAL, "仮定形")
        else -> connection(null, ConnectionReason.NO_RULE)
    }
}

private fun connection(matches: Boolean?, reason: ConnectionReason, vararg forms: String) = Triple(
    when (matches) {
        true -> ConnectionDecision.SUPPORTED
        false -> ConnectionDecision.INCOMPATIBLE
        null -> ConnectionDecision.UNCLASSIFIED
    },
    reason, forms.toSet(),
)
