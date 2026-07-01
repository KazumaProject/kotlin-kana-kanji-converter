package com.kazumaproject.ngram

import java.nio.file.Path

object GenerateStableTermIdMap {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val output = Path.of(cli.required("--output"))
        val map = StableTermIdMap.build(NgramDictionarySource.buildMainDictionaryList())
        map.writeTo(output)
        println("Wrote stable termId map: $output terms=${map.terms.size}")
    }
}

object GenerateNgramPresenceData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifest = NgramPresenceGenerator.generate(
            NgramGenerationOptions(
                sourceDirectory = Path.of(cli.required("--sources_dir")),
                stableTermIdMapPath = Path.of(cli.required("--term_id_map")),
                outputDataPath = Path.of(cli.required("--output_data")),
                outputManifestPath = Path.of(cli.required("--output_manifest")),
                strictUnresolved = cli.hasFlag("--strict_unresolved"),
            )
        )
        cli.optional("--dictionary_manifest")?.let { output ->
            JapaneseKeyboardDictionaryManifestWriter.write(
                outputPath = Path.of(output),
                ngramManifest = manifest,
                stableTermIdMapPath = "ngram/stable_term_id_map.tsv",
            )
        }
        println(
            "Wrote N-gram presence data: resolved=${manifest.resolvedRuleCount} " +
                    "unresolved=${manifest.unresolvedRuleCount} checksum=${manifest.contentChecksum}"
        )
    }
}

object VerifyNgramPresenceData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val result = NgramPresenceVerifier.verify(
            sourceDirectory = Path.of(cli.required("--sources_dir")),
            stableTermIdMapPath = Path.of(cli.required("--term_id_map")),
            dataPath = Path.of(cli.required("--input_data")),
            strictUnresolved = cli.hasFlag("--strict_unresolved"),
        )
        println(
            "Verified N-gram presence data: entries=${result.verifiedEntryCount} " +
                    "negativeProbes=${result.negativeProbeCount} elapsedMs=${result.elapsedNanos / 1_000_000.0}"
        )
    }
}

object DumpNgramPresenceManifest {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifestPath = Path.of(cli.required("--manifest"))
        print(java.nio.file.Files.readString(manifestPath))
    }
}

object ProbeNgramPresencePerformance {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        println(
            NgramPerformanceProbe.run(
                sourceDirectory = Path.of(cli.required("--sources_dir")),
                stableTermIdMapPath = Path.of(cli.required("--term_id_map")),
                dataPath = Path.of(cli.required("--input_data")),
            )
        )
    }
}

private class CliArgs(args: Array<String>) {
    private val values: Map<String, String>
    private val flags: Set<String>

    init {
        val valueMap = mutableMapOf<String, String>()
        val flagSet = mutableSetOf<String>()
        var index = 0
        while (index < args.size) {
            val key = args[index]
            require(key.startsWith("--")) { "Invalid argument: $key" }
            val next = args.getOrNull(index + 1)
            if (next == null || next.startsWith("--")) {
                flagSet += key
                index += 1
            } else {
                valueMap[key] = next
                index += 2
            }
        }
        values = valueMap
        flags = flagSet
    }

    fun required(name: String): String = values[name]
        ?: error("Missing required argument: $name")

    fun optional(name: String): String? = values[name]

    fun hasFlag(name: String): Boolean = name in flags
}
