package com.kazumaproject.mozc.zeroquery

import java.nio.file.Path
import kotlin.io.path.createDirectories

object GenerateMozcZeroQueryData {
    @JvmStatic
    fun main(args: Array<String>) {
        val options = GenerateOptions.parse(args.toList())
        generate(options)
    }

    fun generate(options: GenerateOptions) {
        options.outputDir.createDirectories()

        val ruleDict = ZeroQueryRuleParser.parse(options.zeroQueryDef)
        val emojiDict = ZeroQueryEmojiParser.parse(options.emojiData)
        val emoticonDict = ZeroQueryEmoticonParser.parse(options.emoticonCategorized)
        val symbolDict = ZeroQuerySymbolParser.parse(options.symbol)
        val customRuleDict = ZeroQueryRuleParser.parseCustom(options.customZeroQueryDef)
        val merged = ZeroQueryMerger.mergeWithCustom(
            ruleDict = ruleDict,
            emojiDict = emojiDict,
            emoticonDict = emoticonDict,
            symbolDict = symbolDict,
            customRuleDict = customRuleDict,
        )

        ZeroQueryBinaryWriter.write(
            entriesByKey = merged,
            tokenOutput = options.outputDir.resolve("zero_query_token.data"),
            stringOutput = options.outputDir.resolve("zero_query_string.data"),
        )
        ZeroQueryBinaryWriter.writeAuditTsv(
            entriesByKey = merged,
            output = options.outputDir.resolve("zero_query_data.tsv"),
        )

        val numberDict = ZeroQueryNumberParser.parse(options.zeroQueryNumberDef)
        ZeroQueryBinaryWriter.write(
            entriesByKey = numberDict,
            tokenOutput = options.outputDir.resolve("zero_query_number_token.data"),
            stringOutput = options.outputDir.resolve("zero_query_number_string.data"),
        )
    }
}

data class GenerateOptions(
    val zeroQueryDef: Path,
    val zeroQueryNumberDef: Path,
    val emojiData: Path,
    val emoticonCategorized: Path,
    val symbol: Path,
    val customZeroQueryDef: Path,
    val outputDir: Path,
) {
    companion object {
        private val requiredFlags = linkedSetOf(
            "--zero_query_def",
            "--zero_query_number_def",
            "--emoji_data",
            "--emoticon_categorized",
            "--symbol",
            "--custom_zero_query_def",
            "--output_dir",
        )

        fun parse(args: List<String>): GenerateOptions {
            val values = parseFlagMap(args, requiredFlags)
            return GenerateOptions(
                zeroQueryDef = Path.of(values.getValue("--zero_query_def")),
                zeroQueryNumberDef = Path.of(values.getValue("--zero_query_number_def")),
                emojiData = Path.of(values.getValue("--emoji_data")),
                emoticonCategorized = Path.of(values.getValue("--emoticon_categorized")),
                symbol = Path.of(values.getValue("--symbol")),
                customZeroQueryDef = Path.of(values.getValue("--custom_zero_query_def")),
                outputDir = Path.of(values.getValue("--output_dir")),
            )
        }
    }
}

internal fun parseFlagMap(args: List<String>, requiredFlags: Set<String>): Map<String, String> {
    val values = linkedMapOf<String, String>()
    var index = 0
    while (index < args.size) {
        val flag = args[index]
        if (flag !in requiredFlags) {
            error("Unknown argument for Mozc zero query generator: $flag")
        }
        if (index + 1 >= args.size) {
            error("Missing value for Mozc zero query generator argument: $flag")
        }
        val value = args[index + 1]
        if (value.startsWith("--")) {
            error("Missing value for Mozc zero query generator argument: $flag")
        }
        values[flag] = value
        index += 2
    }

    val missing = requiredFlags - values.keys
    if (missing.isNotEmpty()) {
        error("Missing Mozc zero query generator arguments: $missing")
    }
    return values
}
