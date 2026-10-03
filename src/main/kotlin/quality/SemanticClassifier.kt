package com.kazumaproject.quality

import java.io.File
import java.text.Normalizer

val dictionaryCategories = listOf("person", "place", "facility", "station", "organization", "product", "work", "character", "event", "food", "technical", "general", "unclassified")

val publishedCategories = dictionaryCategories.filter { it != "unclassified" }

data class Classification(val categories: Set<String>, val evidence: String)

class SemanticClassifier(private val catalog: MetadataCatalog, private val base: Map<Pair<String, String>, Set<String>> = emptyMap()) {
    private val roots = mapOf(
        "person" to setOf("Q5", "Q101352", "Q202444", "Q12308941"),
        "place" to setOf("Q655311", "Q177380", "Q17334923", "Q2221906", "Q486972", "Q56061", "Q8502", "Q4022", "Q23442", "Q515", "Q3957"),
        "facility" to setOf("Q132510", "Q2128165", "Q41176", "Q811979", "Q11486677", "Q13226383", "Q16917", "Q1248784", "Q5393308", "Q845945", "Q1254933", "Q33506", "Q11315", "Q12280", "Q44377"),
        "station" to setOf("Q55488", "Q12819564", "Q548662", "Q2175765", "Q953806"),
        "organization" to setOf("Q43229", "Q3914", "Q3918", "Q4830453", "Q6881511"),
        "product" to setOf("Q2424752", "Q431289", "Q897716", "Q7397", "Q29048322", "Q9135", "Q20983788", "Q506883"),
        "work" to setOf("Q43099500", "Q11424", "Q5398426", "Q21198342", "Q8274", "Q63952888", "Q117467246", "Q1555508", "Q7889", "Q571", "Q8261", "Q7366", "Q482994", "Q1344", "Q7725634", "Q105543609", "Q134556", "Q25379", "Q2743", "Q41298", "Q1002697", "Q11032", "Q196600"),
        "character" to setOf("Q95074", "Q15720625", "Q178885", "Q60994492"),
        "event" to setOf("Q1656682", "Q132241", "Q13406554"),
        "food" to setOf("Q2095", "Q746549", "Q25699739", "Q40050", "Q25403900"),
        "technical" to setOf("Q11344", "Q11173", "Q12136", "Q12140", "Q17155032", "Q24034552", "Q246672", "Q33104303", "Q9143", "Q235557", "Q8366", "Q65943", "Q37756"),
        // "Concept" and "term" do not distinguish ordinary words from
        // specialist vocabulary. General words require reviewed lexical facts.
    )
    private val ancestryMemo = hashMapOf<String, Map<String, Int>>()

    private fun ancestors(id: String): Map<String, Int> = ancestryMemo.getOrPut(id) {
        val distances = linkedMapOf(id to 0)
        val queue = ArrayDeque<String>().apply { add(id) }
        while (queue.isNotEmpty()) {
            val current = queue.removeFirst()
            val depth = distances.getValue(current)
            if (depth < 3) catalog.entity(current)?.parents.orEmpty().take(32).forEach { parent ->
                if (parent !in distances) { distances[parent] = depth + 1; queue.add(parent) }
            }
        }
        distances
    }

    private fun categories(entity: MetadataEntity): Set<String> {
        if (entity.types.any { it in setOf("Q4167410", "Q4167836", "Q13406463") }) return emptySet()
        val matches = hashMapOf<String, Int>()
        entity.types.forEach { type ->
            val types = ancestors(type)
            roots.forEach { (category, classes) ->
                val limit = when (category) { "technical" -> 1; "general" -> 0; else -> 3 }
                val distance = classes.mapNotNull { root -> types[root]?.takeIf { it <= limit && (root != "Q2424752" || it == 0) } }.minOrNull()
                if (distance != null) matches[category] = minOf(matches[category] ?: Int.MAX_VALUE, distance)
            }
        }
        // A class such as compiler or alloy can be a concept even without a
        // concrete instance type. Never transfer this rule to named products.
        if (matches.keys.none { it in setOf("person", "place", "facility", "station", "organization", "product", "work", "character", "event") }) {
            val concepts = (entity.parents.flatMap { parent -> ancestors(parent).filterValues { it <= 1 }.keys } + entity.id).toSet()
            if ("Q7397" in concepts || roots.getValue("technical").any { it in concepts } || entity.id in setOf("Q21198", "Q395", "Q413", "Q2329", "Q420", "Q11190", "Q11023")) matches["technical"] = 0
            if (roots.getValue("food").any { it in concepts }) matches["food"] = 0
        }
        // Art/cultural movements and sumo ranks are not organizations/events.
        if (entity.types.any { it in setOf("Q968159", "Q2198855", "Q3326717") }) matches.remove("organization")
        if (entity.types.contains("Q1760692")) matches.remove("event")
        if (entity.types.contains("Q11632355")) { matches["organization"]=0; matches.remove("facility") }
        val nearest = matches.values.minOrNull() ?: return emptySet()
        val result = matches.filterValues { it == nearest }.keys.toMutableSet()
        if ("character" in result) result.remove("person")
        if ("station" in result) result.removeAll(setOf("facility", "place"))
        if ("facility" in result) result.remove("place")
        if (entity.types.any { it == "Q9143" || ancestors(it).get("Q9143") == 1 }) {
            result.add("technical"); result.remove("product")
        }
        if (entity.types.any { it in setOf("Q3914", "Q3918") }) { result.add("organization"); result.remove("facility") }
        if (result.size > 1) result.remove("general")
        if (entity.types.any { it in setOf("Q184759", "Q8928") } || "Q12769326" in entity.parents) {
            result.clear(); result.add("technical")
        }
        // Competing roles on one item do not prove multiple referents. Separate
        // exact-name entities can still supply multiple evidenced categories.
        return if (result.size == 1 || result == setOf("product", "organization")) result else emptySet()
    }

    fun classify(row: SourceRow, pairVerified: Boolean = false): Classification {
        val word = row.word
        if (row.source == "place" && word.tango == "赤坂トラストタワー" && word.yomi == "あかさかとらすとたわー")
            return Classification(setOf("facility"), "https://www.mori-trust.co.jp/news/2022/20220512/")
        val matches = catalog.matched(word.tango, word.yomi, pairVerified)
        val hasVerifiedReading = matches.any { it.readings.isNotEmpty() }
        val considered = matches.filter { it.readings.isNotEmpty() || !hasVerifiedReading || categories(it).all { category -> category in base[word.yomi to word.tango].orEmpty() } }
        val classifications = considered.map { it to categories(it) }.filter { it.second.isNotEmpty() }
        val labels = classifications.flatMap { it.second }.toSet()
        val strongBase = base[word.yomi to word.tango].orEmpty()
        // Each supported referent/role is evaluated independently. A matching
        // surname does not erase independently attested geographic usage.
        val extra = if (row.source == "place" && "place" in strongBase) setOf("place") else emptySet()
        if (labels.isNotEmpty()) return Classification(labels + extra, classifications.joinToString(",") { "https://www.wikidata.org/wiki/${it.first.id}" } + if (extra.isNotEmpty()) ";mozc-place-pair" else "")
        val evidence = base[word.yomi to word.tango].orEmpty()
        val category = when {
            row.source == "person" && evidence == setOf("person") && considered.none { it.types.any { type -> type != "Q5" && type !in roots.getValue("person") } } -> "person"
            row.source == "place" && "place" in evidence -> "place"
            else -> "unclassified"
        }
        return Classification(setOf(category), if (category == "unclassified") "no-semantic-evidence" else "source-and-mozc-pos")
    }

    fun confirmedCategories(row: SourceRow, pairVerified: Boolean = false): Classification {
        val contributions = catalog.matched(row.word.tango, row.word.yomi, pairVerified).filter { it.readings.isNotEmpty() || (pairVerified && catalog.attested(row.word.tango).any { e -> e.id == it.id }) }.map { it to categories(it) }.filter { it.second.isNotEmpty() }
        val roles = contributions.flatMap { it.second }.toSet()
        return Classification(roles.ifEmpty { setOf("unclassified") }, contributions.joinToString(";") { "https://www.wikidata.org/wiki/${it.first.id}#P31;reading:${if (it.first.readings.isNotEmpty()) "P1814-or-independent-pair" else "independent-pair"};categories:${it.second.sorted().joinToString(",")}" })
    }

    companion object {
        fun normalizeReading(value: String) = Normalizer.normalize(value, Normalizer.Form.NFKC).map {
            if (it in 'ァ'..'ヶ') (it.code - 0x60).toChar() else it
        }.joinToString("").replace(" ", "").replace("・", "")

        fun baseEvidence(directory: File, pairs: Set<Pair<String, String>>): Map<Pair<String, String>, Set<String>> {
            val names = com.kazumaproject.mozc.MozcIdDefParser.parse(File(directory, "id.def").toPath()).associate { it.id to it.name }
            val result = hashMapOf<Pair<String, String>, MutableSet<String>>()
            (0..9).map { File(directory, "dictionary%02d.txt".format(it)) }.forEach { file ->
                file.forEachLine { line ->
                    val fields = line.split('\t', limit = 5)
                    val pair = fields[0] to fields[4]
                    if (pair in pairs) {
                        val left = names[fields[1].toInt()].orEmpty()
                        val right = names[fields[2].toInt()].orEmpty()
                        val category = when {
                            left.startsWith("名詞,固有名詞,人名") && right.startsWith("名詞,固有名詞,人名") -> "person"
                            left.startsWith("名詞,固有名詞,地域") && right.startsWith("名詞,固有名詞,地域") -> "place"
                            left.startsWith("名詞,一般") && right.startsWith("名詞,一般") -> "general"
                            else -> null
                        }
                        category?.let { result.getOrPut(pair) { hashSetOf() }.add(it) }
                    }
                }
            }
            return result
        }
    }
}
