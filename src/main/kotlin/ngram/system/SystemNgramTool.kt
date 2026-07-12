package com.kazumaproject.ngram.system

import java.io.File

object SystemNgramTool {
    @JvmStatic
    fun main(args: Array<String>) {
        require(args.isNotEmpty()) { usage() }
        val command = args[0]
        val options = parseOptions(args.drop(1))
        val source = File(options.required("source"))
        val idDef = File(options.required("id-def"))
        when (command) {
            "validate" -> {
                val rules = SystemNgramCompiler.validate(source, idDef)
                println("Validated system N-gram patterns: count=${rules.size}")
            }
            "build" -> {
                val output = File(options.required("output"))
                val manifest = File(options.required("manifest"))
                val result = SystemNgramCompiler.build(source, idDef, output, manifest)
                println(
                    "Built system N-gram dictionary: rules=${result.dictionary.ruleCount}, words=${result.dictionary.wordCount}, " +
                        "binaryBytes=${output.length()}, estimatedHeapBytes=${result.dictionary.estimatedHeapBytes()}, sha256=${result.sha256}"
                )
            }
            "verify" -> {
                val input = File(options.required("input"))
                val rules = SystemNgramRuleParser.parseDirectory(source)
                val dictionary = SystemNgramDictionary.readFrom(input)
                SystemNgramCompiler.verifyRules(dictionary, rules)
                println("Verified system N-gram dictionary: rules=${dictionary.ruleCount}, file=${input.path}")
            }
            "benchmark" -> {
                val input = File(options.required("input"))
                val markdown = File(options.required("markdown"))
                val properties = File(options.required("properties"))
                val operations = options["operations"]?.toInt() ?: 300_000
                val rules = SystemNgramRuleParser.parseDirectory(source)
                val result = SystemNgramBenchmark.run(input, rules, operations)
                SystemNgramBenchmark.writeReports(result, markdown, properties)
                println(
                    "Benchmarked system N-gram dictionary: binaryBytes=${result.binaryBytes}, " +
                        "estimatedHeapBytes=${result.estimatedHeapBytes}, patternMedianNs=${result.patternLookup.medianNs}, " +
                        "wordMedianNs=${result.wordLookup.medianNs}"
                )
            }
            else -> error("Unknown command '$command'. ${usage()}")
        }
    }

    private fun parseOptions(args: List<String>): Map<String, String> {
        require(args.size % 2 == 0) { usage() }
        return args.chunked(2).associate { pair ->
            require(pair[0].startsWith("--")) { usage() }
            pair[0].removePrefix("--") to pair[1]
        }
    }

    private fun Map<String, String>.required(name: String): String =
        this[name] ?: error("Missing --$name. ${usage()}")

    private fun usage(): String =
        "Usage: SystemNgramTool <validate|build|verify|benchmark> --source DIR --id-def FILE [command options]"
}
