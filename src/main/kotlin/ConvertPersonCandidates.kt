import com.kazumaproject.classification.PersonDictionaryReplacementDistribution
import com.kazumaproject.engine.KanaKanjiEngine
import java.io.File
import java.nio.file.Files
import kotlin.system.exitProcess

private data class PersonCliOptions(
    val archive: File,
    val baseArchive: File,
    val category: String,
    val count: Int,
    val expectedCandidate: String?,
    val inputs: List<String>,
)

fun main(args: Array<String>) {
    if (args.any { it == "--help" || it == "-h" }) {
        println(personCliUsage())
        return
    }
    val options = try {
        parsePersonCliOptions(args)
    } catch (exception: IllegalArgumentException) {
        System.err.println("Error: ${exception.message}")
        System.err.println(personCliUsage())
        exitProcess(2)
    }

    val distribution = PersonDictionaryReplacementDistribution()
    distribution.verify(options.baseArchive, options.archive)
    val directory = Files.createTempDirectory("person-dictionary-cli-").toFile()
    try {
        distribution.extractCategoryAssets(options.archive, options.category, directory)
        val engine = KanaKanjiEngine().apply {
            buildEngineFromResourceDirectory(directory.path, mode = 1)
        }
        options.inputs.forEach { input ->
            val candidates = engine.nBestPath(input, options.count)
            if (options.expectedCandidate != null && options.expectedCandidate !in candidates) {
                error("Expected candidate was not returned for input: $input")
            }
            println(
                "{\"input\":${input.toJsonString()},\"candidates\":[" +
                    candidates.mapIndexed { index, candidate ->
                        "{\"rank\":${index + 1},\"text\":${candidate.toJsonString()}}"
                    }.joinToString(",") +
                    "]}",
            )
        }
    } finally {
        directory.deleteRecursively()
    }
}

private fun parsePersonCliOptions(args: Array<String>): PersonCliOptions {
    var archive: File? = null
    var baseArchive: File? = null
    var category: String? = null
    var count = 10
    var expectedCandidate: String? = null
    val inputs = mutableListOf<String>()
    var index = 0
    while (index < args.size) {
        val argument = args[index]
        when {
            argument == "--help" || argument == "-h" -> error("help is handled before option parsing")
            argument == "--archive" -> {
                archive = File(args.getOrNull(index + 1)
                    ?: throw IllegalArgumentException("--archive requires a ZIP path"))
                index++
            }
            argument.startsWith("--archive=") -> archive = File(argument.substringAfter('='))
            argument == "--base" -> {
                baseArchive = File(args.getOrNull(index + 1)
                    ?: throw IllegalArgumentException("--base requires a ZIP path"))
                index++
            }
            argument.startsWith("--base=") -> baseArchive = File(argument.substringAfter('='))
            argument == "--category" -> {
                category = args.getOrNull(index + 1)?.takeIf { it.isNotBlank() }
                    ?: throw IllegalArgumentException("--category requires a person category ID")
                index++
            }
            argument.startsWith("--category=") -> {
                category = argument.substringAfter('=').takeIf { it.isNotBlank() }
                    ?: throw IllegalArgumentException("--category requires a person category ID")
            }
            argument == "--count" -> {
                count = args.getOrNull(index + 1)?.toIntOrNull()?.takeIf { it > 0 }
                    ?: throw IllegalArgumentException("--count requires a positive integer")
                index++
            }
            argument.startsWith("--count=") -> {
                count = argument.substringAfter('=').toIntOrNull()?.takeIf { it > 0 }
                    ?: throw IllegalArgumentException("--count must be a positive integer")
            }
            argument == "--expect-candidate" -> {
                expectedCandidate = args.getOrNull(index + 1)?.takeIf { it.isNotBlank() }
                    ?: throw IllegalArgumentException("--expect-candidate requires text")
                index++
            }
            argument.startsWith("--expect-candidate=") -> {
                expectedCandidate = argument.substringAfter('=').takeIf { it.isNotBlank() }
                    ?: throw IllegalArgumentException("--expect-candidate requires text")
            }
            argument.startsWith("-") -> throw IllegalArgumentException("unknown option: $argument")
            argument.isBlank() -> throw IllegalArgumentException("input readings must not be blank")
            else -> inputs += argument
        }
        index++
    }
    val parsedArchive = archive ?: throw IllegalArgumentException("provide --archive")
    val parsedBaseArchive = baseArchive ?: throw IllegalArgumentException("provide --base")
    val parsedCategory = category ?: throw IllegalArgumentException("provide --category")
    if (inputs.isEmpty()) throw IllegalArgumentException("provide at least one hiragana reading")
    require(parsedArchive.isFile) { "Dictionary ZIP does not exist: ${parsedArchive.path}" }
    require(parsedBaseArchive.isFile) { "Base dictionary ZIP does not exist: ${parsedBaseArchive.path}" }
    return PersonCliOptions(parsedArchive, parsedBaseArchive, parsedCategory, count, expectedCandidate, inputs)
}

private fun personCliUsage(): String =
    "Usage: ./gradlew convertPersonCandidates --args='--archive <replacement-zip> --base <base-zip> " +
        "--category <person-category> [--count N] [--expect-candidate TEXT] <reading> ...'\n" +
        "Loads one replacement person-category dictionary from the prerelease ZIP with KanaKanjiEngine."

private fun String.toJsonString(): String = buildString {
    append('"')
    for (character in this@toJsonString) {
        when (character) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\b' -> append("\\b")
            '\u000C' -> append("\\f")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            in '\u0000'..'\u001F' -> append("\\u%04x".format(character.code))
            else -> append(character)
        }
    }
    append('"')
}
