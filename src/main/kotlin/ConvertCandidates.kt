import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.ngram.EmptySystemNgramDictionary
import com.kazumaproject.ngram.EmptySystemUnigramDictionary
import com.kazumaproject.ngram.PackedSystemNgramDictionary
import com.kazumaproject.ngram.PackedSystemUnigramDictionary
import java.io.File
import kotlin.system.exitProcess

private data class CandidateCliOptions(
    val inputs: List<String>,
    val count: Int,
    val showHelp: Boolean,
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

    val engine = createCandidateCliEngine()
    options.inputs.forEach { input ->
        val candidates = engine.nBestPath(input, options.count)
        println(
            "{\"input\":${input.toJsonString()},\"candidates\":[" +
                candidates.mapIndexed { index, candidate ->
                    "{\"rank\":${index + 1},\"text\":${candidate.toJsonString()}}"
                }.joinToString(",") +
                "]}",
        )
    }
}

private fun parseCandidateCliOptions(args: Array<String>): CandidateCliOptions {
    var count = 10
    var showHelp = false
    val inputs = mutableListOf<String>()
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
            argument.startsWith("-") -> throw IllegalArgumentException("unknown option: $argument")
            argument.isBlank() -> throw IllegalArgumentException("input readings must not be blank")
            else -> inputs += argument
        }
        index++
    }

    if (!showHelp && inputs.isEmpty()) {
        throw IllegalArgumentException("provide at least one hiragana reading")
    }
    return CandidateCliOptions(inputs, count, showHelp)
}

private fun createCandidateCliEngine(): KanaKanjiEngine {
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
    val unigram = if (unigramFile.isFile) {
        PackedSystemUnigramDictionary.fromFile(unigramFile)
    } else {
        EmptySystemUnigramDictionary
    }
    return KanaKanjiEngine(ngram, unigram).apply { buildEngine() }
}

private fun candidateCliUsage(): String =
    "Usage: ./gradlew convertCandidates --args='[--count N] <reading> [<reading> ...]'\n" +
        "Prints one JSON object per reading. Candidate ranks start at 1."

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
