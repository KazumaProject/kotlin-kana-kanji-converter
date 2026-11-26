import com.kazumaproject.grammar.*
import kotlinx.serialization.json.*
import java.io.File

private const val USAGE = """grammarCandidates commands
  legacy READING [--count N]
  convert READING [--count N] [--span START:END:ROLE] [--pos START:END:POS[:TYPE[:FORM]]]
                  [--boundary OFFSET] [--penalty COST] [--trace] [--compare]
                  [--expect SURFACE] [--exclude SURFACE]
  context ID
  inflect FORM READING [--surface SURFACE] [--class CLASS]
  particles PREVIOUS_RIGHT_ID READING... [--following LEFT_ID]
  benchmark READING [--iterations N] [--warmup N] [--legacy] [convert options]
Common options
  --resources DIRECTORY  --metadata FILE  --additional DIRECTORY (repeatable)
Spans and boundaries use UTF-16 offsets. Roles, classes and forms are enum names.
An underscore omits a field in --pos. --exclude checks the complete reachable lattice."""

fun main(args: Array<String>) {
    val cli = GrammarCliArguments(args)
    if (cli.command == null || cli.command == "--help") {
        println(USAGE)
        return
    }
    val resources = File(cli.one("resources") ?: "src/main/resources")
    val metadata = File(cli.one("metadata") ?: "build/grammar/metadata.dat")
    val additional = cli.many("additional")
    val count = cli.one("count")?.toInt() ?: 10
    require(count > 0) { "Count must be positive" }
    val benchmark = cli.command == "benchmark"
    val legacy = cli.command == "legacy" || (benchmark && cli.flag("legacy"))
    val command = cli.command
    if (command == "inflect" && cli.has("class")) {
        require(cli.positional.size == 2) { "Provide an inflection form and a basic reading" }
        val form = InflectionForm.valueOf(cli.positional[0])
        val reading = cli.positional[1]
        val surface = cli.one("surface") ?: reading
        val inflectionClass = InflectionClass.valueOf(checkNotNull(cli.one("class")))
        cli.finish(2)
        println(inflectedJson(JapaneseInflection.generate(InflectionLexeme(reading, surface, inflectionClass), form)))
        return
    }
    val start = System.nanoTime()
    val engine = createCandidateCliEngineFromResources(resources, additional)
    val grammar = if (legacy) null else engine.grammar(metadata)
    val initNanos = System.nanoTime() - start
    val input = cli.positional.firstOrNull() ?: error("Missing command argument")
    val output = when {
        benchmark -> {
            val options = if (legacy) GrammarSearchOptions() else cli.searchOptions()
            val iterations = cli.one("iterations")?.toInt() ?: 100
            val warmup = cli.one("warmup")?.toInt() ?: 50
            cli.finish(1)
            benchmarkGrammar(input, iterations, warmup, initNanos, resources, additional, if (legacy) null else metadata) {
                val conversion = grammar?.convert(input, count, options)
                if (conversion == null) engine.nBestPath(input, count)
                conversion?.statistics
            }
        }
        command == "legacy" -> {
            cli.finish(1)
            buildJsonObject { put("input", input); put("candidates", strings(engine.nBestPath(input, count))) }
        }
        command == "convert" -> {
            val options = cli.searchOptions()
            val expected = cli.many("expect")
            val excluded = cli.many("exclude")
            val compare = cli.flag("compare")
            cli.finish(1)
            val service = checkNotNull(grammar)
            val result = service.convert(input, count, options)
            val surfaces = result.candidates.map { it.value }
            check(expected.all { it in surfaces }) { "Missing in top $count: ${expected - surfaces.toSet()}" }
            check(excluded.none { service.containsCandidate(input, it, options) }) { "Excluded surface still has a legal path" }
            conversionJson(result, if (compare) engine.nBestPath(input, count) else null)
        }
        command == "context" -> {
            cli.finish(1)
            contextJson(checkNotNull(grammar).context(input.toShort()))
        }
        command == "inflect" -> {
            val reading = cli.positional.getOrNull(1) ?: error("Provide a basic reading")
            val surface = cli.one("surface")
            cli.finish(2)
            JsonArray(checkNotNull(grammar).inflect(reading, InflectionForm.valueOf(input), surface).map(::inflectedJson))
        }
        command == "particles" -> {
            val readings = cli.positional.drop(1)
            require(readings.isNotEmpty()) { "Provide at least one particle reading" }
            val following = cli.one("following")?.toShort()
            cli.finish(cli.positional.size)
            JsonArray(checkNotNull(grammar).particleConnections(readings, input.toShort(), following).map { item ->
                buildJsonObject {
                    put("reading", item.reading); put("text", item.surface); put("grammar", wordJson(item.grammar))
                    put("previousConnectionCost", item.previousConnectionCost)
                    put("followingConnectionCost", item.followingConnectionCost?.let(::JsonPrimitive) ?: JsonNull)
                    put("requiredPreviousForms", strings(item.requiredPreviousForms))
                    put("decision", item.decision.name); put("reason", item.reason.name)
                }
            })
        }
        else -> error("Unknown command $command")
    }
    println(output)
}

private class GrammarCliArguments(args: Array<String>) {
    val command = args.firstOrNull()
    val positional = mutableListOf<String>()
    private val values = mutableMapOf<String, MutableList<String>>()
    private val flags = setOf("trace", "compare", "legacy")

    init {
        val iterator = args.drop(1).iterator()
        while (iterator.hasNext()) {
            val arg = iterator.next()
            if (arg.startsWith("--")) {
                val name = arg.removePrefix("--")
                val value = if (name in flags) "true" else {
                    require(iterator.hasNext()) { "Missing value for $arg" }
                    iterator.next()
                }
                values.getOrPut(name) { mutableListOf() }.add(value)
            } else positional += arg
        }
    }

    fun has(name: String): Boolean = name in values
    fun many(name: String): List<String> = values.remove(name).orEmpty()
    fun one(name: String): String? = many(name).let {
        require(it.size <= 1) { "--$name can only be given once" }
        it.firstOrNull()
    }
    fun flag(name: String): Boolean = one(name) != null

    fun finish(arguments: Int) {
        require(positional.size == arguments) { "Unexpected argument count for $command" }
        require(values.isEmpty()) { "Unexpected options for $command: ${values.keys}" }
    }

    fun searchOptions(): GrammarSearchOptions {
        val constraints = buildList {
            many("span").forEach {
                val fields = it.split(':')
                require(fields.size == 3) { "Use --span START:END:ROLE" }
                add(GrammarConstraint.Span(fields[0].toInt(), fields[1].toInt(), GrammarRole.valueOf(fields[2])))
            }
            many("pos").forEach {
                val fields = it.split(':')
                require(fields.size in 3..5) { "Use --pos START:END:POS[:TYPE[:FORM]]" }
                fun field(index: Int) = fields.getOrNull(index)?.takeUnless { name -> name == "_" }
                add(GrammarConstraint.Span(fields[0].toInt(), fields[1].toInt(),
                    listOf(GrammarInterpretation(GrammarSelector(field(2), conjugationType = field(3),
                        conjugationForm = field(4))))))
            }
            many("boundary").forEach { add(GrammarConstraint.Boundary(it.toInt())) }
        }
        return GrammarSearchOptions(constraints, one("penalty")?.toInt() ?: 0, flag("trace"))
    }
}

private fun strings(values: Iterable<String>) = JsonArray(values.map(::JsonPrimitive))

private fun contextJson(context: ContextGrammar) = buildJsonObject {
    put("id", context.id); put("pos", context.partOfSpeech); put("subdivisions", strings(context.subdivisions))
    put("type", context.conjugationType); put("form", context.conjugationForm); put("label", context.contextLabel)
}

private fun wordJson(grammar: WordGrammar) = buildJsonObject {
    put("left", contextJson(grammar.left)); put("right", contextJson(grammar.right))
}

private fun inflectedJson(word: InflectedWord) = buildJsonObject {
    put("reading", word.reading); put("text", word.surface); put("class", word.lexeme.inflectionClass.name)
    put("basicReading", word.lexeme.reading); put("basicSurface", word.lexeme.surface); put("form", word.form.name)
}

private fun rejectionJson(rejection: GrammarRejection?) = rejection?.let {
    buildJsonObject { put("constraint", it.constraintIndex); put("reason", it.reason.name) }
} ?: JsonNull

private fun candidateJson(candidate: GrammarCandidate) = buildJsonObject {
    put("rank", candidate.rank); put("text", candidate.value); put("totalCost", candidate.totalCost)
    put("eosConnectionCost", candidate.eosConnectionCost)
    put("ranking", buildJsonObject {
        put("ngram", candidate.ranking.ngram); put("unigram", candidate.ranking.unigram)
        put("standaloneUnigram", candidate.ranking.standaloneUnigram)
    })
    put("constraintMatches", JsonArray(candidate.constraintMatches.map { match ->
        buildJsonObject {
            put("constraint", match.constraintIndex)
            put("alternatives", JsonArray(match.alternativeIndices.map(::JsonPrimitive)))
        }
    }))
    put("words", JsonArray(candidate.path.bestPath.zip(candidate.annotations).map { (node, word) ->
        buildJsonObject {
            put("reading", node.key); put("text", node.value); put("start", node.start); put("end", node.end)
            put("wordCost", node.wcost); put("connectionCost", word.incomingConnectionCost)
            put("grammarPenalty", word.incomingGrammarPenalty); put("cumulativeCost", word.cumulativeCost)
            put("grammar", wordJson(word.grammar))
        }
    }))
}

private fun selectorJson(selector: GrammarSelector) = buildJsonObject {
    put("partOfSpeech", selector.partOfSpeech)
    put("subdivisions", JsonArray(selector.subdivisions.map { it?.let(::JsonPrimitive) ?: JsonNull }))
    put("conjugationType", selector.conjugationType)
    put("conjugationForm", selector.conjugationForm)
    put("role", selector.role?.name)
}

private fun constraintJson(constraint: GrammarConstraint) = buildJsonObject {
    when (constraint) {
        is GrammarConstraint.Boundary -> put("boundary", constraint.position)
        is GrammarConstraint.Span -> {
            put("start", constraint.start)
            put("end", constraint.end)
            put("alternatives", JsonArray(constraint.alternatives.map {
                buildJsonObject {
                    put("token", selectorJson(it.token))
                    put("previous", it.previous?.let(::selectorJson) ?: JsonNull)
                    put("following", it.following?.let(::selectorJson) ?: JsonNull)
                }
            }))
        }
    }
}

private fun conversionJson(result: GrammarConversionResult, legacy: List<String>?) = buildJsonObject {
    put("input", result.input)
    put("failure", result.failure?.name)
    put("constraints", JsonArray(result.constraints.map(::constraintJson)))
    put("candidates", JsonArray(result.candidates.map(::candidateJson)))
    put("minimumCostPath", result.minimumCostPath?.let(::candidateJson) ?: JsonNull)
    put("statistics", statisticsJson(result.statistics))
    put("rejections", JsonArray(result.rejections.map {
        buildJsonObject { put("rejection", rejectionJson(it.rejection)); put("count", it.count) }
    }))
    if (legacy != null) {
        put("legacyCandidates", strings(legacy))
        put("missingFromThisTopN", strings(legacy - result.candidates.map { it.value }.toSet()))
    }
    result.lattice?.let { lattice ->
        put("lattice", buildJsonObject {
            put("nodes", JsonArray(lattice.nodes.map {
                buildJsonObject {
                    put("id", it.id); put("reading", it.reading); put("text", it.value)
                    put("start", it.start); put("end", it.end); put("wordCost", it.wordCost)
                    put("grammar", wordJson(it.grammar)); put("rejection", rejectionJson(it.rejection))
                }
            }))
            put("edges", JsonArray(lattice.edges.map {
                buildJsonObject {
                    put("from", it.from); put("to", it.to)
                    put("fromState", it.fromState); put("toState", it.toState?.let(::JsonPrimitive) ?: JsonNull)
                    put("connectionCost", it.connectionCost); put("grammarPenalty", it.grammarPenalty)
                    put("rejection", rejectionJson(it.rejection))
                }
            }))
        })
    }
}

internal fun statisticsJson(stats: SearchStatistics) = buildJsonObject {
    put("lexicalNodes", stats.lexicalNodes); put("latticeStates", stats.latticeStates); put("allowedEdges", stats.allowedEdges)
    put("createdPathStates", stats.createdPathStates); put("expandedPathStates", stats.expandedPathStates)
    put("maximumQueueSize", stats.maximumQueueSize); put("completedPaths", stats.completedPaths)
}
