import java.io.File

fun main(args: Array<String>) {
    val options = CliOptions(args.drop(1))
    when (args.firstOrNull()) {
        "build-legacy" -> {
            options.allow("--source", "--out")
            buildLegacyDictionary(
                File(options.optional("--source") ?: "data/1-grams_score_cost_pos_combined_with_ner.zip"),
                File(options.required("--out")),
            )
        }
        else -> error("Usage: build-legacy [--source ZIP] --out DIR")
    }
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
