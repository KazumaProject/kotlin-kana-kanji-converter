import com.kazumaproject.engine.DictionaryAssetSource
import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.ngram.*
import kotlinx.serialization.json.*
import java.io.File
import java.io.IOException
import kotlin.system.exitProcess

internal data class CandidateCliOptions(
    val inputs: List<String>,
    val count: Int,
    val categories: Set<String>,
    val predict: Boolean,
    val details: Boolean,
    val resourceDirectory: File,
    val archive: File?,
    val showHelp: Boolean,
    val listCategories: Boolean,
)

internal fun availableCandidateCategories(): Map<String, String> =
    listOf("src/main/classification/categories.json", "src/main/specialist/categories.json").flatMap { path ->
        Json.parseToJsonElement(File(path).readText()).jsonObject.getValue("categories").jsonArray.map {
            val category = it.jsonObject
            category.getValue("id").jsonPrimitive.content to category.getValue("name").jsonPrimitive.content
        }
    }.toMap()

fun main(args: Array<String>) {
    try {
        val options = parseCandidateCliOptions(args)
        if (options.showHelp) {
            println(candidateCliUsage())
            return
        }
        if (options.listCategories) {
            availableCandidateCategories().forEach { (id, name) -> println("$id\t$name") }
            return
        }
        val engine = createCandidateCliEngine(options)
        options.inputs.forEach { input ->
            val candidates = engine.candidates(input, options.count, options.predict)
            println(buildJsonObject {
                put("input", input)
                putJsonArray("candidates") {
                    candidates.forEachIndexed { index, candidate -> addJsonObject {
                        put("rank", index + 1)
                        put("text", candidate.text)
                        if (options.details) {
                            put("score", candidate.score)
                            put("kind", candidate.kind)
                            put("systemDictionaryMatched", candidate.matchedBySystemDictionary)
                            candidate.reading?.let { put("reading", it) }
                            candidate.category?.let { put("category", it) }
                        }
                    } }
                }
            })
        }
    } catch (exception: Exception) {
        if (exception !is IllegalArgumentException && exception !is IllegalStateException && exception !is IOException) throw exception
        System.err.println("Error: ${exception.message}")
        System.err.println(candidateCliUsage())
        exitProcess(2)
    }
}

internal fun parseCandidateCliOptions(args: Array<String>): CandidateCliOptions {
    var count = 10
    var showHelp = false
    var listCategories = false
    var predict = false
    var details = false
    var resourceDirectory: File? = null
    var archive: File? = null
    val categories = linkedSetOf<String>()
    val available = availableCandidateCategories()
    val inputs = mutableListOf<String>()
    var index = 0
    fun value(argument: String): String = if ('=' in argument) argument.substringAfter('=') else {
        args.getOrNull(++index) ?: throw IllegalArgumentException("$argument requires a value")
    }
    while (index < args.size) {
        val argument = args[index]
        if (argument.substringBefore('=') in setOf("--help", "-h", "--list-categories", "--predict", "--details")) {
            require('=' !in argument) { "Option does not take a value: $argument" }
        }
        when (argument.substringBefore('=')) {
            "--help", "-h" -> showHelp = true
            "--list-categories" -> listCategories = true
            "--predict" -> predict = true
            "--details" -> details = true
            "--count" -> {
                val number = value(argument)
                count = number.toIntOrNull()?.takeIf { it > 0 }
                    ?: throw IllegalArgumentException("--count must be a positive integer: $number")
            }
            "--categories" -> {
                val ids = value(argument)
                if (ids == "all") categories.addAll(available.keys) else {
                    val selected = ids.split(',')
                    require(selected.all { it in available }) { "Unknown category in '$ids'; use --list-categories" }
                    categories.addAll(selected)
                }
            }
            "--resource-dir" -> resourceDirectory = File(value(argument))
            "--assets-zip" -> archive = File(value(argument))
            else -> {
                require(!argument.startsWith("-")) { "Unknown option: $argument" }
                require(argument.isNotBlank()) { "Input readings must not be blank" }
                inputs += argument
            }
        }
        index++
    }
    require(resourceDirectory == null || archive == null) { "Use either --resource-dir or --assets-zip" }
    if (!showHelp && !listCategories) {
        require(inputs.isNotEmpty()) { "Provide at least one reading" }
        require(!predict || categories.isNotEmpty()) { "--predict requires --categories" }
    }
    return CandidateCliOptions(inputs, count, categories, predict, details,
        resourceDirectory ?: File("src/main/resources"), archive, showHelp, listCategories)
}

internal fun createCandidateCliEngine(options: CandidateCliOptions): KanaKanjiEngine {
    DictionaryAssetSource(options.resourceDirectory, options.archive).use { source ->
        val ngram = source.optionalBytes("ngram/system_ngram.dat")?.let(PackedSystemNgramDictionary::read)
            ?: EmptySystemNgramDictionary
        val unigram = source.optionalBytes("ngram/system_ngram_unigram.dat")?.let(PackedSystemUnigramDictionary::read)
            ?: EmptySystemUnigramDictionary
        val standalone = source.optionalBytes("ngram/system_ngram_standalone_unigram.dat")?.let(PackedStandaloneUnigramDictionary::read)
            ?: EmptyStandaloneUnigramDictionary
        return KanaKanjiEngine(ngram, unigram, standalone).apply {
            buildEngine(options.categories, options.resourceDirectory, options.archive)
        }
    }
}

private fun candidateCliUsage(): String = """
    Usage: ./gradlew --quiet convertCandidates --args='[options] <reading> [<reading> ...]'
      --count N                 Maximum candidates (default: 10)
      --categories all|ID,ID     Add all 30 categories or selected dictionaries; repeatable
      --list-categories         List category IDs and names
      --predict                 Include category completions (consumer standard defaults)
      --details                 Include score, kind and completion reading/category
      --resource-dir PATH       Generated resource directory (default: src/main/resources)
      --assets-zip PATH         Read a shipped dictionary ZIP with its shared POS/ngram assets
    Without --categories, only the system conversion dictionary is searched.
    This CLI does not reproduce the application's full candidate pipeline or UI ranking.
""".trimIndent()
