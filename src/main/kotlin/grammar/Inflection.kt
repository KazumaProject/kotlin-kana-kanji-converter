package com.kazumaproject.grammar

enum class InflectionForm { NEGATIVE, PAST, TE, POLITE, CONDITIONAL }
enum class InflectionClass {
    GODAN, GODAN_K_GEMINATE, GODAN_W_U_ONBIN, GODAN_R_HONORIFIC,
    ICHIDAN, KURU, SURU, ARU, I_ADJECTIVE, I_ADJECTIVE_ALTERNATING,
}

data class InflectionLexeme(val reading: String, val surface: String, val inflectionClass: InflectionClass)
data class InflectedWord(val reading: String, val surface: String, val lexeme: InflectionLexeme, val form: InflectionForm)

/** Productive modern inflection for an explicitly identified basic form. */
object JapaneseInflection {
    private data class GodanRow(val irrealis: String, val continuative: String, val conditional: String,
        val past: String, val te: String)

    private val godan = mapOf(
        'う' to GodanRow("わ", "い", "え", "った", "って"),
        'く' to GodanRow("か", "き", "け", "いた", "いて"),
        'ぐ' to GodanRow("が", "ぎ", "げ", "いだ", "いで"),
        'す' to GodanRow("さ", "し", "せ", "した", "して"),
        'つ' to GodanRow("た", "ち", "て", "った", "って"),
        'ぬ' to GodanRow("な", "に", "ね", "んだ", "んで"),
        'ぶ' to GodanRow("ば", "び", "べ", "んだ", "んで"),
        'む' to GodanRow("ま", "み", "め", "んだ", "んで"),
        'る' to GodanRow("ら", "り", "れ", "った", "って"),
    )

    fun generate(lexeme: InflectionLexeme, form: InflectionForm): InflectedWord {
        val type = lexeme.inflectionClass
        val reading = if (type == InflectionClass.I_ADJECTIVE && lexeme.reading.endsWith("いい") &&
            lexeme.surface.endsWith("良い")) {
            inflect(lexeme.reading, InflectionClass.I_ADJECTIVE_ALTERNATING, form)
        } else inflect(lexeme.reading, type, form)
        val surface = if (lexeme.inflectionClass == InflectionClass.KURU && lexeme.surface.endsWith("来る")) {
            // The kanji represents the alternation く／こ／き.
            lexeme.surface.dropLast(1) + select(form, "ない", "た", "て", "ます", "れば")
        } else if (lexeme.inflectionClass == InflectionClass.ARU && lexeme.surface.lastOrNull() == 'る') {
            if (form == InflectionForm.NEGATIVE) "ない" else inflect(lexeme.surface, InflectionClass.GODAN, form)
        } else {
            inflect(lexeme.surface, lexeme.inflectionClass, form)
        }
        return InflectedWord(reading, surface, lexeme, form)
    }

    internal fun classOf(context: ContextGrammar): InflectionClass? {
        if (context.conjugationForm != "基本形") return null
        if (context.partOfSpeech == "形容詞" && context.conjugationType?.startsWith("形容詞・") == true) {
            return if (context.conjugationType == "形容詞・イイ") InflectionClass.I_ADJECTIVE_ALTERNATING
            else InflectionClass.I_ADJECTIVE
        }
        if (context.partOfSpeech != "動詞") return null
        val type = context.conjugationType ?: return null
        return when {
            type.startsWith("一段") -> InflectionClass.ICHIDAN
            type.startsWith("カ変・") -> InflectionClass.KURU
            type.startsWith("サ変") -> InflectionClass.SURU
            type.startsWith("五段・カ行促音便") -> InflectionClass.GODAN_K_GEMINATE
            type == "五段・ワ行ウ音便" -> InflectionClass.GODAN_W_U_ONBIN
            type == "五段・ラ行特殊" -> InflectionClass.GODAN_R_HONORIFIC
            type == "五段・ラ行" && context.contextLabel == "ある" -> InflectionClass.ARU
            type.startsWith("五段") -> InflectionClass.GODAN
            else -> null
        }
    }

    private fun inflect(text: String, type: InflectionClass, form: InflectionForm): String = when (type) {
        InflectionClass.ICHIDAN -> replaceEnding(text, "る", select(form, "ない", "た", "て", "ます", "れば"))
        InflectionClass.KURU -> replaceEnding(text, "くる", select(form, "こない", "きた", "きて", "きます", "くれば"))
        InflectionClass.SURU -> if (text.endsWith("ずる")) {
            replaceEnding(text, "ずる", select(form, "じない", "じた", "じて", "じます", "ずれば"))
        } else {
            replaceEnding(text, "する", select(form, "しない", "した", "して", "します", "すれば"))
        }
        InflectionClass.ARU -> {
            require(text == "ある") { "ARU expects the basic reading ある" }
            if (form == InflectionForm.NEGATIVE) "ない" else inflect(text, InflectionClass.GODAN, form)
        }
        InflectionClass.I_ADJECTIVE_ALTERNATING -> {
            require(text.endsWith("いい")) { "Alternating adjective must end in いい" }
            if (form == InflectionForm.POLITE) text + "です"
            else inflect(text.dropLast(2) + "よい", InflectionClass.I_ADJECTIVE, form)
        }
        InflectionClass.I_ADJECTIVE ->
            replaceEnding(text, "い", select(form, "くない", "かった", "くて", "いです", "ければ"))
        else -> {
            val ending = text.lastOrNull()
            val row = requireNotNull(godan[ending]) { "Unsupported godan ending: $text" }
            val variant = when (type) {
                InflectionClass.GODAN_K_GEMINATE -> {
                    require(ending == 'く')
                    row.copy(past = "った", te = "って")
                }
                InflectionClass.GODAN_W_U_ONBIN -> {
                    require(ending == 'う')
                    row.copy(past = "うた", te = "うて")
                }
                InflectionClass.GODAN_R_HONORIFIC -> {
                    require(ending == 'る')
                    row.copy(continuative = "い")
                }
                else -> row
            }
            text.dropLast(1) + select(form, variant.irrealis + "ない", variant.past,
                variant.te, variant.continuative + "ます", variant.conditional + "ば")
        }
    }

    private fun replaceEnding(text: String, ending: String, suffix: String): String {
        require(text.endsWith(ending)) { "$text must end in $ending" }
        return text.dropLast(ending.length) + suffix
    }

    private fun select(form: InflectionForm, negative: String, past: String, te: String, polite: String,
        conditional: String): String = when (form) {
        InflectionForm.NEGATIVE -> negative
        InflectionForm.PAST -> past
        InflectionForm.TE -> te
        InflectionForm.POLITE -> polite
        InflectionForm.CONDITIONAL -> conditional
    }
}
