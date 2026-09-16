package com.kazumaproject.quantity

import java.io.File

/** Semantic classes are derived from rule membership; inflections require actual Mozc POS forms. */
object QuantityContextSource {
    data class Pattern(val features: List<QuantityScoringModel.Feature>, val family: Int, val unitFamily: Int? = null)
    data class Schema(val quantities: Map<String, Long>, val words: Map<String, Long>, val patterns: List<Pattern>)
    const val SUFFIX_JOIN = 3
    const val SELECTION = 4
    const val AGREEMENT = 5
    const val WEAK = 6
    const val POSSESSIVE_VEHICLE = 7
    const val REQUEST = 8
    const val PRESENCE = 9
    const val DURATION = 10
    const val LIMIT = 11
    const val COORDINATION = 12
    const val WEAK_UNIT_START = 13
    const val FEATURE_COUNT = WEAK_UNIT_START + 63

    fun schema(dictionary: QuantityDictionary, modelSource: File): Schema {
        val quantity = Regex("quantity\\(\"([^\"]+)\"\\)")
        val word = Regex("\"([^\"]+)\"")
        val extra = File(modelSource, "context.ngram").readLines().filter { it.isNotBlank() && !it.startsWith("#") }.map { line ->
            line.split(Regex("\\s+\\+\\s+")).map { feature ->
                quantity.matchEntire(feature)?.let { QuantityDictionary.Feature.Quantity(it.groupValues[1]) }
                    ?: word.matchEntire(feature)?.let { QuantityDictionary.Feature.Word(it.groupValues[1]) }
                    ?: error("Invalid model context feature: $feature")
            }.also { require(it.size in 2..5 && it.any { feature -> feature is QuantityDictionary.Feature.Quantity }) }
        }
        val temporal = listOf("分", "時", "時間", "日", "週間", "週", "月", "か月", "年")
        val modifiedDurations = temporal.flatMap { unit -> listOf("だけ", "ぐらい", "くらい", "程度").flatMap { modifier ->
            listOf("待つ", "かかる", "経つ", "続く").map { predicate -> listOf(QuantityDictionary.Feature.Quantity(unit),
                QuantityDictionary.Feature.Word(modifier), QuantityDictionary.Feature.Word(predicate)) }
        } }
        val coordination = dictionary.units.map { unit -> listOf(QuantityDictionary.Feature.Quantity(unit),
            QuantityDictionary.Feature.Word("と"), QuantityDictionary.Feature.Quantity(unit)) }
        val originals = dictionary.rules + extra + modifiedDurations + coordination + dictionary.units.map { listOf(QuantityDictionary.Feature.Quantity(it), QuantityDictionary.Feature.Word("ずつ")) }
        fun descendants(unit: String, visited: Set<String> = emptySet()): Set<String> {
            if (unit in visited) return emptySet()
            return setOf(unit) + dictionary.suffixes.filter { it.base == unit }.flatMap {
                descendants(unit + it.output, visited + unit)
            }
        }
        val rules = originals.flatMap { rule ->
            rule.fold(listOf(emptyList<QuantityDictionary.Feature>())) { prefixes, feature ->
                val variants = if (feature is QuantityDictionary.Feature.Quantity) descendants(feature.unit).map {
                    QuantityDictionary.Feature.Quantity(it)
                } else listOf(feature)
                prefixes.flatMap { prefix -> variants.map { prefix + it } }
            }
        }.distinct()
        val units = rules.flatten().filterIsInstance<QuantityDictionary.Feature.Quantity>().map { it.unit }.distinct().sorted()
        require(units.size <= 63)
        val quantities = units.mapIndexed { index, unit -> unit to (1L shl index) }.toMap()
        val membership = HashMap<String, MutableSet<String>>()
        for (rule in rules) for ((index, feature) in rule.withIndex()) {
            if (feature !is QuantityDictionary.Feature.Word) continue
            val signature = rule.mapIndexed { at, other -> if (at == index) "*" else when (other) {
                is QuantityDictionary.Feature.Word -> "w:${other.text}"
                is QuantityDictionary.Feature.Quantity -> "q:${other.unit}"
            } }.joinToString("+")
            membership.getOrPut(feature.text) { sortedSetOf() }.add(signature)
        }
        val groups = membership.entries.groupBy { it.value.toList() }.values.sortedBy { entries -> entries.minOf { it.key } }
        require(groups.size <= 63) { "Too many semantic word classes: ${groups.size}" }
        val words = groups.flatMapIndexed { index, group -> group.map { it.key to (1L shl index) } }.toMap()
        fun baseUnit(unit: String): String {
            val suffix = dictionary.suffixes.firstOrNull { it.base + it.output == unit } ?: return unit
            return baseUnit(suffix.base)
        }
        val patterns = rules.map { rule ->
            val first = rule.first()
            val family = if (first is QuantityDictionary.Feature.Quantity && rule.last() is QuantityDictionary.Feature.Quantity) COORDINATION
            else if (first is QuantityDictionary.Feature.Quantity) {
                when (rule.last()) {
                    in listOf("いる", "居る", "ある").map { QuantityDictionary.Feature.Word(it) } -> PRESENCE
                    in listOf("待つ", "経つ", "かかる", "続く").map { QuantityDictionary.Feature.Word(it) } -> DURATION
                    in listOf("まで", "以上", "以下", "未満").map { QuantityDictionary.Feature.Word(it) } -> LIMIT
                    in listOf("だけ", "ずつ", "ぐらい", "くらい", "程度").map { QuantityDictionary.Feature.Word(it) } -> WEAK
                    in listOf("ください", "欲しい", "必要", "足りる").map { QuantityDictionary.Feature.Word(it) } -> REQUEST
                    else -> SELECTION
                }
            } else if (rule.any { it == QuantityDictionary.Feature.Word("の") } && rule.last() == QuantityDictionary.Feature.Quantity("台"))
                POSSESSIVE_VEHICLE else AGREEMENT
            Pattern(rule.map { when (it) {
                is QuantityDictionary.Feature.Quantity -> QuantityScoringModel.Feature(QuantityScoringModel.FeatureKind.QUANTITY, quantities.getValue(it.unit))
                is QuantityDictionary.Feature.Word -> QuantityScoringModel.Feature(QuantityScoringModel.FeatureKind.LEXICAL, words.getValue(it.text))
            } }, family, if (family in setOf(WEAK, LIMIT) && first is QuantityDictionary.Feature.Quantity)
                WEAK_UNIT_START + units.indexOf(baseUnit(first.unit)).also { require(it >= 0) } else null)
        }.distinct()
        return Schema(quantities, words, patterns)
    }

    data class Form(val text: String, val family: String, val conjugation: String, val classes: Long)
    fun inflections(lemma: String, pos: String, classes: Long): List<Form> {
        val fields = pos.split(',')
        if (fields.size < 6 || fields[5] != "基本形") return emptyList()
        val family = fields.take(5).joinToString(",")
        val endings: Map<String, List<String>> = when {
            fields[0] == "形容詞" && lemma.endsWith("い") -> mapOf("い" to listOf("基本形"), "く" to listOf("連用テ接続", "連用ゴザイ接続"),
                "かっ" to listOf("連用タ接続"), "けれ" to listOf("仮定形"))
            fields[0] != "動詞" -> return emptyList()
            fields[4].startsWith("サ変") && lemma == "する" -> return listOf(
                "する" to "基本形", "し" to "未然形", "し" to "連用形", "せ" to "未然レル接続",
                "せ" to "未然ヌ接続", "すれ" to "仮定形", "しろ" to "命令ｒｏ", "せよ" to "命令ｙｏ")
                .map { Form(it.first, family, it.second, classes) }
            fields[4].startsWith("カ変") && lemma == "来る" -> return listOf(
                "来る" to "基本形", "来" to "未然形", "来" to "連用形", "来れ" to "仮定形",
                "来い" to "命令ｉ", "来よ" to "命令ｙｏ", "来" to "未然ウ接続")
                .map { Form(it.first, family, it.second, classes) }
            fields[4].startsWith("一段") && lemma.endsWith("る") -> mapOf("る" to listOf("基本形"), "" to listOf("未然形", "連用形"),
                "れ" to listOf("仮定形"), "ろ" to listOf("命令ｒｏ"), "よ" to listOf("命令ｙｏ", "未然ウ接続"))
            fields[4].startsWith("五段") -> {
                val row = when (lemma.last()) {
                    'う' -> listOf("わ", "い", "っ", "う", "え", "お")
                    'く' -> listOf("か", "き", if (fields[4].contains("促音便")) "っ" else "い", "く", "け", "こ")
                    'ぐ' -> listOf("が", "ぎ", "い", "ぐ", "げ", "ご")
                    'す' -> listOf("さ", "し", "し", "す", "せ", "そ")
                    'つ' -> listOf("た", "ち", "っ", "つ", "て", "と")
                    'ぬ' -> listOf("な", "に", "ん", "ぬ", "ね", "の")
                    'ぶ' -> listOf("ば", "び", "ん", "ぶ", "べ", "ぼ")
                    'む' -> listOf("ま", "み", "ん", "む", "め", "も")
                    'る' -> listOf("ら", "り", "っ", "る", "れ", "ろ")
                    else -> return emptyList()
                }
                val names = listOf("未然形", "連用形", "連用タ接続", "基本形", "仮定形", "未然ウ接続")
                (row.zip(names) + (row[4] to "命令ｅ")).groupBy({ it.first }, { it.second })
            }
            else -> return emptyList()
        }
        return endings.flatMap { (ending, forms) -> forms.map { Form(lemma.dropLast(1) + ending, family, it, classes) } }
    }
}
