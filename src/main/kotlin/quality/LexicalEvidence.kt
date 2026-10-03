package com.kazumaproject.quality

import java.io.File
import java.sql.DriverManager
import java.text.Normalizer
import java.util.zip.ZipFile

data class LexicalFact(val reading: String, val surface: String, val categories: Set<String>, val evidence: String)

class LexicalEvidence(facts: Iterable<LexicalFact> = emptyList()) {
    private val pairs = facts.groupBy { key(it.reading, it.surface) }
    val readings: Map<String, Set<String>> = facts.groupBy { it.surface }.mapValues { (_, rows) -> rows.map { it.reading }.toSet() }
    fun facts(reading: String, surface: String): List<LexicalFact> = pairs[key(reading, surface)].orEmpty()
    fun has(reading: String, surface: String, category: String) = facts(reading, surface).any { category in it.categories }
    fun all(): Sequence<LexicalFact> = pairs.values.asSequence().flatten()
    companion object {
        private fun key(reading: String, surface: String) = SemanticClassifier.normalizeReading(reading) to Normalizer.normalize(surface, Normalizer.Form.NFKC)
        fun load(snapshot: File? = null, confirmed: File? = File("src/main/dictionary-quality/confirmed.tsv").takeIf { it.isFile }): LexicalEvidence {
            val facts = mutableListOf<LexicalFact>()
            if (snapshot != null) DriverManager.getConnection("jdbc:sqlite:${snapshot.toURI()}?mode=ro").use { connection ->
                connection.createStatement().use { statement ->
                    statement.executeQuery("SELECT reading,surface,categories,evidence FROM lexical ORDER BY surface,reading").use { r ->
                        while (r.next()) facts.add(LexicalFact(r.getString(1), r.getString(2), r.getString(3).split(',').toSet(), r.getString(4)))
                    }
                }
            }
            if (confirmed != null) confirmed.forEachLine { line ->
                if (line.isNotBlank() && !line.startsWith("#") && !line.startsWith("reading\t")) {
                    val f = line.split('\t')
                    require(f.size == 4 && f[0].isNotBlank() && f[1].isNotBlank() && f[2].split(',').all { it in dictionaryCategories && it != "unclassified" } && f[3].startsWith("https://")) { "Invalid confirmed lexical fact: $line" }
                    facts.add(LexicalFact(f[0], f[1], f[2].split(',').toSet(), f[3]))
                }
            }
            return LexicalEvidence(facts)
        }
    }
}

object PostalLexicon {
    const val evidence = "https://www.post.japanpost.jp/service/search/zipcode/download/utf-zip.html"
    // These are complete postal instructions, not substring tests on place names.
    fun instruction(surface: String) = surface.contains("の次に番地がくる場合") || surface.contains("以下に掲載がない場合") || surface == "その他" || surface.endsWith("全域")
    fun annotation(surface: String): Boolean = surface in setOf("区", "丁目", "番地", "大字", "その他", "一部", "地階", "地下", "地階・階層不明", "階層不明", "高層棟", "低層棟", "以下に掲載がない場合") ||
        Regex("(?:地下|地上|第)?[０-９0-9一二三四五六七八九十百]+(?:階|丁目|番地)(?:以上|以下)?").matches(surface) ||
        surface.endsWith("空港内") || surface.contains("除く") || surface.contains("番地") || surface.contains("階層") || surface.contains("丁目")

    fun read(zip: File, visit: (LexicalFact) -> Unit) = ZipFile(zip).use { archive ->
        val entries = archive.entries().asSequence().filter { !it.isDirectory && it.name.endsWith(".csv", true) }.toList()
        require(entries.size == 1) { "Postal ZIP must contain one CSV" }
        archive.getInputStream(entries.single()).bufferedReader(Charsets.UTF_8).useLines { lines ->
            lines.forEachIndexed { index, line ->
                val f = csv(line.removePrefix("\uFEFF"))
                require(f.size == 15) { "Postal CSV:${index + 1}: expected 15 fields" }
                fun surface(v: String) = Normalizer.normalize(v, Normalizer.Form.NFKC)
                fun reading(v: String) = SemanticClassifier.normalizeReading(v)
                val pref = surface(f[6]); val city = surface(f[7]); val town = surface(f[8])
                val pr = reading(f[3]); val cr = reading(f[4]); val tr = reading(f[5])
                fun add(name: String, yomi: String) {
                    if (name.isNotBlank() && yomi.isNotBlank() && !instruction(name) && name.none { it in "()（）" } && yomi.all { it in 'ぁ'..'ゖ' || it == 'ー' }) visit(LexicalFact(yomi, name, setOf("place"), evidence))
                }
                add(pref, pr); add(city, cr); add(pref + city, pr + cr)
                if (instruction(town)) return@forEachIndexed
                val nameParts = Regex("^([^()]*)\\(([^()]*)\\)$").matchEntire(town)
                val readParts = Regex("^([^()]*)\\(([^()]*)\\)$").matchEntire(tr)
                if (nameParts == null && !town.contains('(')) {
                    add(town, tr); add(city + town, cr + tr); add(pref + city + town, pr + cr + tr)
                } else if (nameParts != null && readParts != null) {
                    val head = nameParts.groupValues[1]; val hr = readParts.groupValues[1]
                    val alias = nameParts.groupValues[2]; val ar = readParts.groupValues[2]
                    // Floor-specific postal heads may themselves concatenate a
                    // town and building. They are not canonical-name evidence.
                    if (!alias.contains("階")) { add(head, hr); add(city + head, cr + hr); add(pref + city + head, pr + cr + hr) }
                    if (!annotation(alias) && !alias.contains(Regex("[、,～~・]"))) add(alias, ar)
                }
            }
        }
    }
    fun csv(line: String): List<String> {
        val result = mutableListOf<String>(); val value = StringBuilder(); var quoted = false; var index = 0
        while (index < line.length) {
            val c = line[index++]
            when {
                c == '"' && quoted && line.getOrNull(index) == '"' -> { value.append('"'); index++ }
                c == '"' -> quoted = !quoted
                c == ',' && !quoted -> { result.add(value.toString()); value.setLength(0) }
                else -> value.append(c)
            }
        }
        require(!quoted) { "Unclosed CSV quotation" }; result.add(value.toString()); return result
    }
}

data class QualityDecision(val state: String, val evidence: String)
class QualityEvaluator(private val catalog: MetadataCatalog, private val readings: Map<String, Set<String>>, private val lexical: LexicalEvidence) {
    fun evaluate(row: SourceRow): QualityDecision {
        val word = row.word
        lexical.facts(word.yomi, word.tango).takeIf { it.isNotEmpty() }?.let { return QualityDecision("accepted", it.joinToString(";") { f -> f.evidence }) }
        val entities = catalog.matched(word.tango, word.yomi)
        if (entities.any { entity -> entity.readings.any { SemanticClassifier.normalizeReading(it) == SemanticClassifier.normalizeReading(word.yomi) } })
            return QualityDecision("accepted", entities.filter { it.readings.isNotEmpty() }.joinToString(";") { "https://www.wikidata.org/wiki/${it.id}#P1814" })
        if (entities.isEmpty() && catalog.forSurface(word.tango).any { it.readings.isNotEmpty() }) return QualityDecision("held", "reading-unconfirmed-or-mismatch")
        if (word.yomi in readings[word.tango].orEmpty()) return QualityDecision("accepted", "mozc-exact-reading-surface")
        return QualityDecision("held", if (catalog.forSurface(word.tango).any { it.readings.isNotEmpty() }) "reading-unconfirmed-or-mismatch" else "no-independent-reading-evidence")
    }
}
