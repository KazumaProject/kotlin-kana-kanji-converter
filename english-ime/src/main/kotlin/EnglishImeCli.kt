import conversion.PhraseConverter
import conversion.ReviewedDictionary
import grammar.ContextEvaluator
import grammar.Lexicon
import kotlinx.serialization.json.*
import java.io.File

fun main(args: Array<String>) {
    val options = CliOptions(args.drop(1))
    when (args.firstOrNull()) {
        "build-legacy" -> {
            options.allow("--source", "--out")
            buildLegacyDictionary(
                File(options.optional("--source") ?: DEFAULT_SOURCE),
                File(options.required("--out")),
            )
        }
        "convert" -> convert(options)
        "evaluate" -> {
            options.allow("--text", "--candidate", "--format", "--lexicon")
            val lexicon = Lexicon.load(File(options.optional("--lexicon") ?: "data/grammar"))
            val results = ContextEvaluator(lexicon).evaluate(options.required("--text"), options.all("--candidate"))
            when (options.optional("--format") ?: "text") {
                "text" -> results.forEach {
                    println("${it.candidate}\t${it.score}\t${it.reasons.joinToString(",")}\t" +
                        it.interpretations.joinToString(",") { form -> "${form.key.lexemeId}=${form.lemma}" })
                }
                "json" -> println(buildJsonObject {
                    put("schemaVersion", 1)
                    putJsonArray("candidates") {
                        for (result in results) addJsonObject {
                            put("candidate", result.candidate)
                            put("score", result.score)
                            putJsonArray("reasons") { result.reasons.forEach { add(it) } }
                            putJsonArray("interpretations") {
                                for (form in result.interpretations) addJsonObject {
                                    put("lexemeId", form.key.lexemeId)
                                    put("lemma", form.lemma)
                                    put("surface", form.key.surface)
                                    putJsonArray("dictionaries") { form.dictionaries.sorted().forEach { add(it) } }
                                }
                            }
                        }
                    }
                })
                else -> error("--format must be text or json")
            }
        }
        "export-inventory" -> {
            options.allow("--source", "--out")
            exportInventory(File(options.optional("--source") ?: DEFAULT_SOURCE), File(options.required("--out")))
        }
        "build-reviewed" -> {
            options.allow("--source", "--decisions", "--lexicon", "--relations", "--out", "--corrections", "--notices", "--supplement")
            buildReviewedDictionary(
                File(options.optional("--source") ?: DEFAULT_SOURCE),
                File(options.required("--decisions")),
                File(options.required("--lexicon")),
                File(options.required("--relations")),
                File(options.required("--out")),
                options.optional("--corrections")?.let(::File),
                options.optional("--notices")?.let(::File),
                options.optional("--supplement")?.let(::File),
            )
        }
        else -> error("Usage: export-inventory | build-reviewed | build-legacy [--source ZIP] --out DIR | evaluate --text TEXT --candidate WORD [--format text|json]" +
            " | convert --assets DIR --text TEXT [--mode exact|prefix] [--limit N] [--format text|json]")
    }
}

private fun convert(options: CliOptions) {
    options.allow("--assets", "--text", "--mode", "--limit", "--format")
    val text = options.required("--text")
    val mode = options.optional("--mode") ?: "exact"
    require(mode in setOf("exact", "prefix")) { "--mode must be exact or prefix" }
    val format = options.optional("--format") ?: "text"
    require(format in setOf("text", "json")) { "--format must be text or json" }
    val limit = options.optional("--limit")?.let {
        requireNotNull(it.toIntOrNull()) { "--limit must be an integer" }
    } ?: 10
    val dictionary = ReviewedDictionary.load(File(options.required("--assets")))
    val candidates = PhraseConverter(dictionary).convert(text, prefixMode = mode == "prefix", limit)
    if (format == "text") {
        for ((index, candidate) in candidates.withIndex()) {
            val textField = candidate.text.replace("\\", "\\\\").replace("\t", "\\t")
                .replace("\r", "\\r").replace("\n", "\\n")
            println("${index + 1}\t${textField}\t${candidate.dictionaryCost}\t" +
                candidate.grammar.reasons.distinct().joinToString(","))
        }
        return
    }
    println(buildJsonObject {
        put("schemaVersion", 1)
        put("input", text)
        putJsonArray("candidates") {
            for ((index, candidate) in candidates.withIndex()) addJsonObject {
                put("rank", index + 1)
                put("text", candidate.text)
                put("dictionaryCost", candidate.dictionaryCost)
                put("grammarScore", candidate.grammar.score)
                putJsonArray("reasons") { candidate.grammar.reasons.distinct().forEach { add(it) } }
                putJsonArray("segments") {
                    for (segment in candidate.segments) addJsonObject {
                        put("start", segment.start)
                        put("end", segment.end)
                        put("surface", segment.surface)
                        put("kind", segment.kind.name.lowercase())
                        put("inferredSpace", segment.inferredSpace)
                        segment.reading?.let { put("reading", it) }
                    }
                }
            }
        }
    })
}

internal class CliOptions(arguments: List<String>) {
    private val values: Map<String, List<String>>

    init {
        require(arguments.size % 2 == 0) { "Options must have a value" }
        values = arguments.chunked(2).groupBy({ it[0] }, { it[1] })
    }

    fun allow(vararg flags: String) {
        require(values.keys.all { it in flags }) { "Unknown options: ${values.keys - flags.toSet()}" }
    }

    fun all(flag: String): List<String> = values[flag].orEmpty()

    fun optional(flag: String): String? {
        val supplied = all(flag)
        require(supplied.size <= 1) { "Repeated option: $flag" }
        return supplied.firstOrNull()
    }

    fun required(flag: String): String = requireNotNull(optional(flag)) { "Required option: $flag" }
}

private const val DEFAULT_SOURCE = "data/1-grams_score_cost_pos_combined_with_ner.zip"
