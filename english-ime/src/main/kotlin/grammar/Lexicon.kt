package grammar

import java.io.File

data class Category(val name: String, val definition: String, val examples: String)
data class FormKey(val lexemeId: String, val surface: String)
data class Form(val key: FormKey, val lemma: String, val evidence: String, val dictionaries: Set<String>)

class Lexicon private constructor(val categories: List<Category>, val forms: List<Form>) {
    private val index = forms.groupBy { lookupKey(it.key.surface) }

    fun lookup(surface: String): List<Form> {
        val matches = index[lookupKey(surface)].orEmpty()
        val exact = matches.filter { it.key.surface == surface }
        // A newly attested name such as `He` must not hide the sentence-initial
        // pronoun `he`. Keep identities separate and exact interpretations first.
        return exact + matches.filter { it.key.surface != surface && it.key.surface == it.key.surface.lowercase() }
    }

    companion object {
        fun load(directory: File): Lexicon {
            val definitions = directory.resolve("categories.tsv").readTsv("category", "definition", "examples")
                .map { (name, definition, examples) -> Category(name, definition, examples) }
            val names = definitions.map { it.name }.toSet()
            require(names.size == definitions.size && names.all { it.matches(Regex("[a-z][a-z0-9_]*")) }) {
                "Category names must be unique identifiers"
            }

            val rows = directory.resolve("forms.tsv").readTsv("lexeme_id", "lemma", "surface", "evidence")
            val byForm = rows.associateBy { FormKey(it[0], it[2]) }
            require(byForm.size == rows.size) { "Duplicate lexeme and surface pair" }
            require(rows.groupBy { it[0] }.values.all { group ->
                group.map { it[1] }.distinct().size == 1 && group.any { it[1] == it[2] }
            }) { "Each lexeme needs one consistent lemma and its base surface" }

            val membershipRows = directory.resolve("memberships.tsv").readTsv("category", "lexeme_id", "surface")
            require(membershipRows.toSet().size == membershipRows.size) { "Duplicate dictionary membership" }
            val memberships = membershipRows.groupBy({ FormKey(it[1], it[2]) }, { it[0] })
            require(memberships.keys == byForm.keys && membershipRows.map { it[0] }.toSet() == names) {
                "Every form and category must have a valid membership"
            }
            return Lexicon(definitions, byForm.map { (key, row) ->
                require(row[3].startsWith("https://")) { "Missing evidence URL for $key" }
                val categories = memberships.getValue(key).toSet()
                val lemma = row[1]
                require(categories.none { it in baseOnly } || key.surface == lemma) {
                    "Invalid base membership for $key with lemma $lemma"
                }
                Form(key, lemma, row[3], categories)
            })
        }

        private val baseOnly = setOf("verb_base", "aux_be_base", "aux_have_base", "aux_do_base", "adjective_base")
    }
}

internal fun lookupKey(surface: String): String = surface.replace('’', '\'').lowercase()

internal fun File.readTsv(vararg header: String): List<List<String>> = useLines { lines ->
    val iterator = lines.iterator()
    require(iterator.hasNext() && iterator.next().split('\t') == header.toList()) { "Invalid header in $this" }
    iterator.asSequence().mapIndexed { index, line ->
        line.split('\t').also { row ->
            require(row.size == header.size && row.none { it.isBlank() }) {
                "Invalid TSV row in $this at line ${index + 2}"
            }
        }
    }.toList()
}
