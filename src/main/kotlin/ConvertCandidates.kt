import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.ngram.EmptySystemNgramDictionary
import com.kazumaproject.ngram.EmptyStandaloneUnigramDictionary
import com.kazumaproject.ngram.PackedStandaloneUnigramDictionary
import com.kazumaproject.ngram.EmptySystemUnigramDictionary
import com.kazumaproject.ngram.PackedSystemNgramDictionary
import com.kazumaproject.ngram.PackedSystemUnigramDictionary
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream
import kotlin.system.exitProcess

private data class CandidateCliOptions(
    val inputs: List<String>,
    val count: Int,
    val archive: File?,
    val category: String,
    val expectedConversions: Map<String, Set<String>>,
    val showHelp: Boolean,
)

private data class CandidateCliRuntime(
    val engine: KanaKanjiEngine,
    val temporaryDirectory: File? = null,
)

fun main(args: Array<String>) {
    val options = try {
        parseCandidateCliOptions(args)
    } catch (exception: IllegalArgumentException) {
        System.err.println("Error: ${exception.message}")
        System.err.println(candidateCliUsage())
        exitProcess(2)
    }

    if (options.showHelp) {
        println(candidateCliUsage())
        return
    }

    val runtime = if (options.archive == null) {
        CandidateCliRuntime(createCandidateCliEngineFromResources())
    } else {
        createCandidateCliEngineFromArchive(options.archive, options.category)
    }
    try {
        options.inputs.forEach { input ->
            val candidates = runtime.engine.nBestPath(input, options.count)
            val missing = options.expectedConversions[input].orEmpty() - candidates.toSet()
            check(missing.isEmpty()) {
                "Expected candidates were not returned for input $input: ${missing.sorted().joinToString()}; " +
                    "actual=${candidates.joinToString()}"
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
        runtime.temporaryDirectory?.deleteRecursively()
    }
}

private fun parseCandidateCliOptions(args: Array<String>): CandidateCliOptions {
    var count = 10
    var archive: File? = null
    var category = "system"
    var showHelp = false
    val inputs = mutableListOf<String>()
    val expectedConversions = linkedMapOf<String, MutableSet<String>>()
    var index = 0

    while (index < args.size) {
        val argument = args[index]
        when {
            argument == "--help" || argument == "-h" -> showHelp = true
            argument == "--count" -> {
                val value = args.getOrNull(index + 1)
                    ?: throw IllegalArgumentException("--count requires a positive integer")
                count = value.toIntOrNull()?.takeIf { it > 0 }
                    ?: throw IllegalArgumentException("--count must be a positive integer: $value")
                index++
            }
            argument.startsWith("--count=") -> {
                val value = argument.substringAfter('=')
                count = value.toIntOrNull()?.takeIf { it > 0 }
                    ?: throw IllegalArgumentException("--count must be a positive integer: $value")
            }
            argument == "--archive" -> {
                archive = File(args.getOrNull(index + 1)
                    ?: throw IllegalArgumentException("--archive requires a ZIP path"))
                index++
            }
            argument.startsWith("--archive=") -> archive = File(argument.substringAfter('='))
            argument == "--category" -> {
                category = args.getOrNull(index + 1)?.takeIf { it.isNotBlank() }
                    ?: throw IllegalArgumentException("--category requires an asset category")
                index++
            }
            argument.startsWith("--category=") -> {
                category = argument.substringAfter('=').takeIf { it.isNotBlank() }
                    ?: throw IllegalArgumentException("--category requires an asset category")
            }
            argument == "--expect-conversion" -> {
                val value = args.getOrNull(index + 1)
                    ?: throw IllegalArgumentException("--expect-conversion requires reading=surface")
                addExpectedConversion(expectedConversions, value)
                index++
            }
            argument.startsWith("--expect-conversion=") ->
                addExpectedConversion(expectedConversions, argument.substringAfter('='))
            argument.startsWith("-") -> throw IllegalArgumentException("unknown option: $argument")
            argument.isBlank() -> throw IllegalArgumentException("input readings must not be blank")
            else -> inputs += argument
        }
        index++
    }

    if (!showHelp && inputs.isEmpty()) {
        throw IllegalArgumentException("provide at least one hiragana reading")
    }
    if (archive == null && category != "system") {
        throw IllegalArgumentException("--category requires --archive")
    }
    if (archive != null && !archive.isFile) {
        throw IllegalArgumentException("Dictionary ZIP does not exist: ${archive.path}")
    }
    if (!expectedConversions.keys.all { it in inputs }) {
        throw IllegalArgumentException("each --expect-conversion reading must also be an input")
    }
    return CandidateCliOptions(
        inputs,
        count,
        archive,
        category,
        expectedConversions.mapValues { it.value.toSet() },
        showHelp,
    )
}

private fun addExpectedConversion(expected: MutableMap<String, MutableSet<String>>, value: String) {
    val separator = value.indexOf('=')
    if (separator <= 0 || separator == value.lastIndex) {
        throw IllegalArgumentException("--expect-conversion requires nonempty reading=surface: $value")
    }
    val reading = value.substring(0, separator)
    val surface = value.substring(separator + 1)
    expected.getOrPut(reading) { linkedSetOf() }.add(surface)
}

private fun createCandidateCliEngineFromResources(): KanaKanjiEngine {
    val requiredFiles = listOf("yomi.dat", "tango.dat", "token.dat", "connectionId.dat", "pos_table.dat")
    val missingFiles = requiredFiles.filterNot { File("src/main/resources/$it").isFile }
    check(missingFiles.isEmpty()) {
        "Generated conversion dictionaries are missing: ${missingFiles.joinToString()}. " +
            "Prepare the Mozc dictionary resources and run ./gradlew run first."
    }

    val ngramFile = File("src/main/resources/ngram/system_ngram.dat")
    val unigramFile = File("src/main/resources/ngram/system_ngram_unigram.dat")
    val ngram = if (ngramFile.isFile) {
        PackedSystemNgramDictionary.fromFile(ngramFile)
    } else {
        EmptySystemNgramDictionary
    }
    val packedUnigram = if (unigramFile.isFile) {
        PackedSystemUnigramDictionary.fromFile(unigramFile)
    } else {
        EmptySystemUnigramDictionary
    }
    val standaloneFile = File("src/main/resources/ngram/system_ngram_standalone_unigram.dat")
    val standalone = if (standaloneFile.isFile) {
        PackedStandaloneUnigramDictionary.fromFile(standaloneFile)
    } else {
        EmptyStandaloneUnigramDictionary
    }
    return KanaKanjiEngine(ngram, packedUnigram, standalone).apply { buildEngine() }
}

private fun createCandidateCliEngineFromArchive(archive: File, category: String): CandidateCliRuntime {
    require(category == "system" || category.matches(Regex("[a-z_]+(/[a-z_]+)*"))) {
        "Invalid dictionary asset category: $category"
    }
    val directory = Files.createTempDirectory("dictionary-release-cli-").toFile()
    try {
        ZipFile(archive).use { zip ->
            val assetRoot = "app/src/main/assets"
            val categoryPath = if (category == "system") "system" else "categories/$category"
            listOf("yomi.dat", "tango.dat", "token.dat").forEach { fileName ->
                val asset = "$assetRoot/$categoryPath/$fileName.zip"
                extractSingleFile(zip, asset, fileName, File(directory, fileName))
            }
            extractSingleFile(
                zip,
                "$assetRoot/connectionId.dat.zip",
                "connectionId.dat",
                File(directory, "connectionId.dat"),
            )
            copyAsset(zip, "$assetRoot/pos_table.dat", File(directory, "pos_table.dat"))
            listOf(
                "system_ngram.dat",
                "system_ngram_unigram.dat",
                "system_ngram_standalone_unigram.dat",
            ).forEach { fileName ->
                copyAsset(zip, "$assetRoot/ngram/$fileName", File(directory, fileName))
            }
        }
        val engine = KanaKanjiEngine(
            PackedSystemNgramDictionary.fromFile(File(directory, "system_ngram.dat")),
            PackedSystemUnigramDictionary.fromFile(File(directory, "system_ngram_unigram.dat")),
            PackedStandaloneUnigramDictionary.fromFile(File(directory, "system_ngram_standalone_unigram.dat")),
        ).apply { buildEngineFromResourceDirectory(directory.path, mode = 1) }
        return CandidateCliRuntime(engine, directory)
    } catch (exception: Exception) {
        directory.deleteRecursively()
        throw exception
    }
}

private fun copyAsset(zip: ZipFile, assetPath: String, destination: File) {
    val entry = zip.getEntry(assetPath) ?: error("Dictionary archive is missing $assetPath")
    check(!entry.isDirectory && entry.size > 0) { "Dictionary asset is empty: $assetPath" }
        zip.getInputStream(entry).use { input -> destination.outputStream().use { input.copyTo(it) } }
}

private fun extractSingleFile(zip: ZipFile, assetPath: String, expectedName: String, destination: File) {
    val entry = zip.getEntry(assetPath) ?: error("Dictionary archive is missing $assetPath")
    check(!entry.isDirectory && entry.size > 0) { "Dictionary asset is empty: $assetPath" }
    ZipInputStream(zip.getInputStream(entry)).use { nested ->
        val first = nested.nextEntry ?: error("Nested dictionary ZIP is empty: $assetPath")
        check(first.name == expectedName) { "Unexpected nested dictionary file in $assetPath: ${first.name}" }
        destination.outputStream().use { nested.copyTo(it) }
        check(nested.nextEntry == null) { "Nested dictionary ZIP has multiple files: $assetPath" }
    }
    check(destination.length() > 0) { "Extracted dictionary asset is empty: $assetPath" }
}

private fun candidateCliUsage(): String =
    "Usage: ./gradlew convertCandidates --args='[--archive ZIP] [--category system|<category-id>] " +
        "[--count N] [--expect-conversion reading=surface] <reading> [<reading> ...]'\n" +
        "Loads packaged assets from the release ZIP when --archive is set, then prints one JSON object per reading."

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
