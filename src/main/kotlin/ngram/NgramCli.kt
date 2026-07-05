package com.kazumaproject.ngram

import java.nio.file.Path

object GenerateStableTermIdMap {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val outputData = Path.of(cli.required("--output_data"))
        val outputManifest = Path.of(cli.required("--output_manifest"))
        val build = NgramTokenTermIdBuilder.build(NgramDictionarySource.buildMainDictionaryList())
        val checksum = NgramTokenTermIdDataWriter().write(outputData, build)
        NgramTokenTermIdManifestWriter.write(
            outputPath = outputManifest,
            build = build,
            contentChecksumHex = checksum,
            byteSize = java.nio.file.Files.size(outputData),
        )
        println(
            "Wrote compact N-gram token termId sidecar: $outputData " +
                    "postings=${build.termIdsByTokenPosting.size} uniqueTerms=${build.uniqueTermCount}"
        )
    }
}

object GenerateNgramPresenceData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifest = NgramPresenceGenerator.generate(
            NgramGenerationOptions(
                sourceDirectory = Path.of(cli.required("--sources_dir")),
                outputDataPath = Path.of(cli.required("--output_data")),
                outputManifestPath = Path.of(cli.required("--output_manifest")),
                strictUnresolved = cli.hasFlag("--strict_unresolved"),
            )
        )
        cli.optional("--dictionary_manifest")?.let { output ->
            JapaneseKeyboardDictionaryManifestWriter.write(
                outputPath = Path.of(output),
                ngramManifest = manifest,
                tokenTermIdDataPath = "ngram/token_term_id.data",
                tokenTermIdManifestPath = "ngram/token_term_id_manifest.json",
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
            dataPath = Path.of(cli.required("--input_data")),
            strictUnresolved = cli.hasFlag("--strict_unresolved"),
        )
        println(
            "Verified N-gram presence data: entries=${result.verifiedEntryCount} " +
                    "negativeProbes=${result.negativeProbeCount} elapsedMs=${result.elapsedNanos / 1_000_000.0}"
        )
    }
}

object GenerateNgramCorrectionData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifest = NgramCorrectionGenerator.generate(
            sourceDirectory = Path.of(cli.required("--sources_dir")),
            outputDataPath = Path.of(cli.required("--output_data")),
            outputManifestPath = Path.of(cli.required("--output_manifest")),
        )
        cli.optional("--dictionary_manifest")?.let { output ->
            JapaneseKeyboardDictionaryManifestWriter.writeCorrection(
                outputPath = Path.of(output),
                manifest = manifest,
            )
        }
        println(
            "Wrote N-gram correction data: candidates=${manifest.candidateCount} " +
                    "readings=${manifest.readingCount} checksum=${manifest.contentChecksum}"
        )
    }
}

object VerifyNgramCorrectionData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val verified = NgramCorrectionVerifier.verify(
            sourceDirectory = Path.of(cli.required("--sources_dir")),
            dataPath = Path.of(cli.required("--input_data")),
        )
        println("Verified N-gram correction data: candidates=$verified")
    }
}

object GenerateCoarsePosClassData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifest = CoarsePosClassGenerator.generate(
            idDefPath = Path.of(cli.required("--id_def")),
            outputDataPath = Path.of(cli.required("--output_data")),
            outputManifestPath = Path.of(cli.required("--output_manifest")),
        )
        println(
            "Wrote coarse POS class data: ids=${manifest.idDefEntryCount} " +
                    "checksum=${manifest.contentChecksum}"
        )
    }
}

object VerifyCoarsePosClassData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val verified = CoarsePosClassVerifier.verify(
            idDefPath = Path.of(cli.required("--id_def")),
            dataPath = Path.of(cli.required("--input_data")),
        )
        println(
            "Verified coarse POS class data: ids=${verified.verifiedIdCount} " +
                    "elapsedMs=${verified.elapsedNanos / 1_000_000.0}"
        )
    }
}

object GenerateContextualCorrectionData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifest = ContextualCorrectionGenerator.generate(
            sourceDirectory = Path.of(cli.required("--sources_dir")),
            outputDataPath = Path.of(cli.required("--output_data")),
            outputManifestPath = Path.of(cli.required("--output_manifest")),
        )
        cli.optional("--dictionary_manifest")?.let { output ->
            val ngramManifestPath = Path.of(cli.required("--ngram_manifest"))
            val ngramManifestJson = java.nio.file.Files.readString(ngramManifestPath)
            val coarsePosManifestPath = Path.of(cli.required("--coarse_pos_manifest"))
            val coarsePosManifestJson = java.nio.file.Files.readString(coarsePosManifestPath)
            JapaneseKeyboardDictionaryManifestWriter.writeCorrection(
                outputPath = Path.of(output),
                ngramCorrectionDataPath = "ngram/ngram_correction.data",
                ngramCorrectionManifestPath = "ngram/ngram_correction_manifest.json",
                ngramCorrectionFormat = generatedJsonString(ngramManifestJson, "format"),
                ngramCorrectionLookupMode = generatedJsonString(ngramManifestJson, "lookupMode"),
                ngramCorrectionCandidateOrder = generatedJsonString(ngramManifestJson, "candidateOrder"),
                ngramCorrectionDictionaryBuildId = generatedJsonString(ngramManifestJson, "dictionaryBuildId"),
                ngramCorrectionContentChecksum = generatedJsonString(ngramManifestJson, "contentChecksum"),
                contextualCorrectionManifest = manifest,
                coarsePosClassDataPath = "ngram/coarse_pos_class.data",
                coarsePosClassManifestPath = "ngram/coarse_pos_class_manifest.json",
                coarsePosClassFormat = generatedJsonString(coarsePosManifestJson, "format"),
                coarsePosClassKeyMode = generatedJsonString(coarsePosManifestJson, "keyMode"),
                coarsePosClassMappingPolicy = generatedJsonString(coarsePosManifestJson, "mappingPolicy"),
                coarsePosClassDictionaryBuildId = generatedJsonString(coarsePosManifestJson, "dictionaryBuildId"),
                coarsePosClassContentChecksum = generatedJsonString(coarsePosManifestJson, "contentChecksum"),
                coarsePosClassSourceChecksum = generatedJsonString(coarsePosManifestJson, "sourceChecksum"),
            )
        }
        println(
            "Wrote contextual correction data: rules=${manifest.ruleCount} " +
                    "checksum=${manifest.contentChecksum}"
        )
    }
}

object VerifyContextualCorrectionData {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val verified = ContextualCorrectionVerifier.verify(
            sourceDirectory = Path.of(cli.required("--sources_dir")),
            dataPath = Path.of(cli.required("--input_data")),
        )
        println("Verified contextual correction data: rules=$verified")
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

object DumpNgramCorrectionManifest {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifestPath = Path.of(cli.required("--manifest"))
        print(java.nio.file.Files.readString(manifestPath))
    }
}

object DumpContextualCorrectionManifest {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        val manifestPath = Path.of(cli.required("--manifest"))
        print(java.nio.file.Files.readString(manifestPath))
    }
}

object DumpCoarsePosClassManifest {
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
                dataPath = Path.of(cli.required("--input_data")),
            )
        )
    }
}

object ProbeNgramCorrectionPerformance {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        println(
            NgramCorrectionPerformanceProbe.run(
                sourceDirectory = Path.of(cli.required("--sources_dir")),
                dataPath = Path.of(cli.required("--input_data")),
            )
        )
    }
}

object ProbeContextualCorrectionPerformance {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        println(
            ContextualCorrectionPerformanceProbe.run(
                sourceDirectory = Path.of(cli.required("--sources_dir")),
                dataPath = Path.of(cli.required("--input_data")),
            )
        )
    }
}

object ProbeCoarsePosClassPerformance {
    @JvmStatic
    fun main(args: Array<String>) {
        val cli = CliArgs(args)
        println(
            CoarsePosClassPerformanceProbe.run(
                idDefPath = Path.of(cli.required("--id_def")),
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

private fun generatedJsonString(json: String, key: String): String {
    val pattern = Regex(""""${Regex.escape(key)}"\s*:\s*"([^"]*)"""")
    return pattern.find(json)?.groupValues?.get(1)
        ?: error("Missing generated manifest JSON string field: $key")
}
