import org.gradle.api.GradleException
import org.gradle.api.tasks.bundling.Zip
import org.gradle.jvm.tasks.Jar

plugins {
    kotlin("jvm") version "1.9.21"
    kotlin("plugin.serialization") version "1.9.22"
    id("application")
}

data class BuildIdDefEntry(val id: Int, val name: String, val lineNumber: Int)

fun parseBuildIdDef(file: File): List<BuildIdDefEntry> {
    if (!file.isFile) {
        throw GradleException("Missing Mozc id.def: file path=${file.path}. Set -PmozcIdDefFile=/path/to/id.def or place src/main/resources/id.def.")
    }
    val entries = mutableListOf<BuildIdDefEntry>()
    val seenIds = mutableMapOf<Int, BuildIdDefEntry>()
    val seenNames = mutableMapOf<String, BuildIdDefEntry>()
    file.useLines { lines ->
        lines.forEachIndexed { index, rawLine ->
            val lineNumber = index + 1
            if (rawLine.isEmpty()) {
                throw GradleException("Failed to parse id.def: file path=${file.path}, line number=$lineNumber, raw line='$rawLine', reason=blank lines are not valid")
            }
            val separatorIndex = rawLine.indexOfFirst { it.isWhitespace() }
            if (separatorIndex <= 0) {
                throw GradleException("Failed to parse id.def: file path=${file.path}, line number=$lineNumber, raw line='$rawLine', reason=expected '<id> <name>'")
            }
            val idText = rawLine.substring(0, separatorIndex)
            val name = rawLine.substring(separatorIndex + 1)
            val id = idText.toIntOrNull()
                ?: throw GradleException("Failed to parse id.def: file path=${file.path}, line number=$lineNumber, raw line='$rawLine', reason=invalid Int ID '$idText'")
            if (id !in Short.MIN_VALUE..Short.MAX_VALUE) {
                throw GradleException("Failed to parse id.def: file path=${file.path}, line number=$lineNumber, raw line='$rawLine', reason=ID is outside Short range: ID=$id name=$name")
            }
            val entry = BuildIdDefEntry(id, name, lineNumber)
            seenIds.putIfAbsent(id, entry)?.let { first ->
                throw GradleException("Duplicate id.def ID in ${file.path}: duplicated ID=$id, first line=${first.lineNumber}, second line=$lineNumber, name=$name")
            }
            seenNames.putIfAbsent(name, entry)?.let { first ->
                throw GradleException("Duplicate id.def name in ${file.path}: name=$name, first ID=${first.id} line=${first.lineNumber}, second ID=$id line=$lineNumber")
            }
            entries += entry
        }
    }
    if (entries.isEmpty()) {
        throw GradleException("id.def is empty: file path=${file.path}")
    }
    val first = entries.first()
    if (first.id != 0) {
        throw GradleException("Invalid id.def sequence in ${file.path}: expected ID=0, actual ID=${first.id}, line=${first.lineNumber}, name=${first.name}, reason=ID must start from 0")
    }
    if (first.name != "BOS/EOS,*,*,*,*,*,*") {
        throw GradleException("Invalid BOS/EOS in ${file.path}: actual ID 0 name=${first.name}, expected name=BOS/EOS,*,*,*,*,*,*")
    }
    entries.forEachIndexed { expectedId, entry ->
        if (entry.id != expectedId) {
            throw GradleException("Invalid id.def sequence in ${file.path}: expected ID=$expectedId, actual ID=${entry.id}, line=${entry.lineNumber}, name=${entry.name}, reason=ID must be continuous")
        }
    }
    val lastId = entries.last().id
    if (entries.size != lastId + 1) {
        throw GradleException("Invalid id.def entry count in ${file.path}: entry count=${entries.size}, last ID=$lastId, reason=entry count must equal last ID + 1")
    }
    return entries
}

fun generateBuildIdDefConstants(entries: List<BuildIdDefEntry>): String = buildString {
    appendLine("@file:Suppress(\"DANGEROUS_CHARACTERS\")")
    appendLine()
    appendLine("package com.kazumaproject")
    appendLine()
    appendLine("/**")
    appendLine(" * Auto-generated from Mozc id.def.")
    appendLine(" * Do not edit manually.")
    appendLine(" */")
    appendLine("object IdDefConstants {")
    val nonPropertyEntries = mutableListOf<BuildIdDefEntry>()
    entries.forEach { entry ->
        if (entry.id == 0) {
            appendLine("    const val BOS_EOS = (0).toShort()")
        } else if (canUseBuildBacktickIdentifier(entry.name)) {
            appendLine("    const val `${entry.name}` = (${entry.id}).toShort()")
        } else {
            nonPropertyEntries += entry
            appendLine("    // Cannot be emitted as a Kotlin property; the exact Mozc name is kept below.")
            appendLine("    // const val `${entry.name}` = (${entry.id}).toShort()")
        }
    }
    if (nonPropertyEntries.isNotEmpty()) {
        appendLine()
        appendLine("    val NON_PROPERTY_ENTRIES_BY_NAME: Map<String, Short> = mapOf(")
        nonPropertyEntries.forEach { entry ->
            appendLine("        ${entry.name.toBuildKotlinStringLiteral()} to (${entry.id}).toShort(),")
        }
        appendLine("    )")
    }
    appendLine("}")
}

fun canUseBuildBacktickIdentifier(name: String): Boolean =
    name.none { it == '`' || it == '\n' || it == '\r' || it == '.' || it == ';' || it == '[' || it == ']' || it == '/' || it == '<' || it == '>' || it == ':' || it == '\\' }

fun String.toBuildKotlinStringLiteral(): String = buildString {
    append('"')
    this@toBuildKotlinStringLiteral.forEach { ch ->
        when (ch) {
            '\\' -> append("\\\\")
            '"' -> append("\\\"")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> append(ch)
        }
    }
    append('"')
}

group = "com.kazumaproject"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation("org.jetbrains.kotlin:kotlin-test")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0-RC.2")
}

val generatedMozcIdDefDir = layout.buildDirectory.dir("generated/source/mozcIdDef/main/kotlin")
val generatedMozcDataDir = layout.buildDirectory.dir("generated/mozc-data")
val generatedMozcDataFile = generatedMozcDataDir.map { it.file("mozc.data") }
val generatedMozcDataManifestFile = generatedMozcDataDir.map { it.file("mozc_data_manifest.json") }
val generatedMozcHelperDir = layout.buildDirectory.dir("generated/mozc-helper")
val mozcGoldenDictionaryLookupFile = layout.projectDirectory.file("src/test/resources/mozc_golden/dictionary/system_dictionary_lookup.json")
val mozcGoldenConnectorCostFile = layout.projectDirectory.file("src/test/resources/mozc_golden/connector/connector_cost.json")
val mozcGoldenSegmenterBoundaryFile = layout.projectDirectory.file("src/test/resources/mozc_golden/segmenter/segmenter_boundary.json")
val mozcGoldenImmutableConverterFile = layout.projectDirectory.file("src/test/resources/mozc_golden/converter/immutable_converter.json")
val mozcGoldenNBestGeneratorFile = layout.projectDirectory.file("src/test/resources/mozc_golden/converter/nbest_generator.json")
val mozcGoldenCandidateFilterFile = layout.projectDirectory.file("src/test/resources/mozc_golden/converter/candidate_filter.json")
val mozcGoldenPredictorFile = layout.projectDirectory.file("src/test/resources/mozc_golden/prediction/predictor.json")
val mozcGoldenZeroQueryFile = layout.projectDirectory.file("src/test/resources/mozc_golden/prediction/zero_query.json")
val mozcGoldenRewriterFile = layout.projectDirectory.file("src/test/resources/mozc_golden/rewriter/rewriter.json")
val mozcImmutableConverterHelperSource = layout.projectDirectory.file("tools/mozc_golden/mozc_immutable_converter_helper.cc")
val mozcNBestCandidateFilterHelperSource = layout.projectDirectory.file("tools/mozc_golden/mozc_nbest_candidate_filter_helper.cc")
val mozcPredictionHelperSource = layout.projectDirectory.file("tools/mozc_golden/mozc_prediction_helper.cc")
val mozcRewriterHelperSource = layout.projectDirectory.file("tools/mozc_golden/mozc_rewriter_helper.cc")
val mozcIdDefFileProvider = providers.gradleProperty("mozcIdDefFile")
    .map { layout.projectDirectory.file(it) }
    .orElse(layout.projectDirectory.file("src/main/resources/id.def"))
val mozcConnectionFileProvider = layout.projectDirectory.file("src/main/resources/connection_single_column.txt")
val mozcDictionaryFilesProvider = files(
    (0..9).map { "src/main/resources/dictionary%02d.txt".format(it) } + "src/main/resources/suffix.txt"
)

fun resolveMozcSourceDirectoryForBuild(): File {
    providers.gradleProperty("mozcSrcDir").orNull?.takeIf { it.isNotBlank() }?.let { explicit ->
        val explicitFile = file(explicit)
        if (!explicitFile.isDirectory) {
            throw GradleException("Mozc source directory does not exist: mozcSrcDir=${explicitFile.path}")
        }
        return explicitFile
    }
    val candidates = listOf(
        rootDir.resolve("third_party/mozc/src"),
        rootDir.resolve("../mozc/src").normalize(),
        rootDir.resolve("../mozc-master/src").normalize(),
    )
    return candidates.firstOrNull { it.isDirectory }
        ?: throw GradleException(
            "Mozc source directory was not found. Set -PmozcSrcDir=/path/to/mozc/src or place Mozc at one of: " +
                    candidates.joinToString { it.path }
        )
}

fun mozcBazelCommand(): String =
    providers.gradleProperty("mozcBazelCommand").orNull?.takeIf { it.isNotBlank() } ?: "bazel"

fun mozcExpectedVersion(): String =
    providers.gradleProperty("mozcExpectedVersion").orNull?.takeIf { it.isNotBlank() } ?: "24.11.oss"

val generateIdDefConstants = tasks.register("generateIdDefConstants") {
    val idDefFile = mozcIdDefFileProvider
    inputs.file(idDefFile)
    inputs.property("generatorVersion", "3")
    outputs.dir(generatedMozcIdDefDir)
    doLast {
        val entries = parseBuildIdDef(idDefFile.get().asFile)
        val outputFile = generatedMozcIdDefDir.get().asFile.resolve("com/kazumaproject/IdDefConstants.kt")
        outputFile.parentFile.mkdirs()
        outputFile.writeText(generateBuildIdDefConstants(entries))
    }
}

val validateMozcIdDef = tasks.register("validateMozcIdDef") {
    group = "verification"
    description = "Validates Mozc id.def and its ID/name sequence."
    inputs.file(mozcIdDefFileProvider)
    doLast {
        val entries = parseBuildIdDef(mozcIdDefFileProvider.get().asFile)
        logger.lifecycle("Validated Mozc id.def: entries=${entries.size}, maxId=${entries.last().id}")
    }
}

val validateConnectionMatrix = tasks.register("validateConnectionMatrix") {
    group = "verification"
    description = "Validates Mozc connection_single_column.txt matrix size and costs."
    inputs.file(mozcConnectionFileProvider)
    doLast {
        val file = mozcConnectionFileProvider.asFile
        if (!file.isFile) {
            throw GradleException("Missing Mozc connection_single_column.txt: file path=${file.path}")
        }
        file.bufferedReader().use { reader ->
            val firstLine = reader.readLine()
                ?: throw GradleException("connection matrix is empty: file path=${file.path}")
            val matrixSize = firstLine.toIntOrNull()
                ?: throw GradleException("Invalid connection matrix size: file path=${file.path}, line number=1, value='$firstLine'")
            val expected = matrixSize.toLong() * matrixSize.toLong()
            var actual = 0L
            var lineNumber = 1
            reader.lineSequence().forEach { rawLine ->
                lineNumber += 1
                val value = rawLine.toIntOrNull()
                    ?: throw GradleException("Invalid connection matrix cost: file path=${file.path}, line number=$lineNumber, value='$rawLine'")
                if (value !in Short.MIN_VALUE..Short.MAX_VALUE) {
                    throw GradleException("Invalid connection matrix cost: file path=${file.path}, line number=$lineNumber, value='$rawLine', reason=outside Short range")
                }
                actual += 1
            }
            if (actual != expected) {
                throw GradleException("Connection matrix count mismatch: file path=${file.path}, matrixSize=$matrixSize, expected count=$expected, actual count=$actual")
            }
            logger.lifecycle("Validated connection matrix: matrixSize=$matrixSize, data count=$actual")
        }
    }
}

val validateDictionaryIds = tasks.register("validateDictionaryIds") {
    group = "verification"
    description = "Validates Mozc dictionary leftId/rightId against id.def and connection matrix size."
    inputs.file(mozcIdDefFileProvider)
    inputs.file(mozcConnectionFileProvider)
    inputs.files(mozcDictionaryFilesProvider)
    dependsOn(validateMozcIdDef, validateConnectionMatrix)
    doLast {
        val idDefEntries = parseBuildIdDef(mozcIdDefFileProvider.get().asFile)
        val connectionHeader = mozcConnectionFileProvider.asFile.useLines { lines ->
            lines.firstOrNull()?.toIntOrNull()
        } ?: throw GradleException("Invalid connection matrix size: file path=${mozcConnectionFileProvider.asFile.path}, line number=1")
        mozcDictionaryFilesProvider.files.sortedBy { it.name }.forEach { file ->
            if (!file.isFile) {
                throw GradleException("Missing Mozc dictionary file: file path=${file.path}")
            }
            file.useLines { lines ->
                lines.forEachIndexed { index, rawLine ->
                    if (rawLine.isEmpty()) return@forEachIndexed
                    val lineNumber = index + 1
                    val columns = rawLine.split('\t')
                    val leftId = columns.getOrNull(1)?.toIntOrNull()
                    val rightId = columns.getOrNull(2)?.toIntOrNull()
                    val invalid = leftId == null || rightId == null ||
                            leftId < 0 || rightId < 0 ||
                            leftId >= idDefEntries.size || rightId >= idDefEntries.size ||
                            leftId >= connectionHeader || rightId >= connectionHeader
                    if (invalid) {
                        throw GradleException(
                            "Dictionary ID validation failed: file path=${file.path}, line number=$lineNumber, " +
                                    "surface/yomi=${columns.getOrNull(4).orEmpty()}/${columns.getOrNull(0).orEmpty()}, " +
                                    "leftId=$leftId, rightId=$rightId, idDefEntryCount=${idDefEntries.size}, connectionMatrixSize=$connectionHeader"
                        )
                    }
                }
            }
        }
        logger.lifecycle("Validated dictionary IDs: files=${mozcDictionaryFilesProvider.files.size}, idDefEntryCount=${idDefEntries.size}, connectionMatrixSize=$connectionHeader")
    }
}

val validateIdDefReferences = tasks.register("validateIdDefReferences") {
    group = "verification"
    description = "Validates IdDefConstants references in Kotlin files against Mozc id.def."
    val kotlinSourceFiles = fileTree("src/main/kotlin") { include("**/*.kt") }
    inputs.file(mozcIdDefFileProvider)
    inputs.files(kotlinSourceFiles)
    dependsOn(validateMozcIdDef)
    doLast {
        val validNames = parseBuildIdDef(mozcIdDefFileProvider.get().asFile).mapTo(mutableSetOf()) { it.name }
        validNames += "BOS_EOS"
        val referenceRegex = Regex("""(?:import\s+com\.kazumaproject\.IdDefConstants\.|IdDefConstants\.)(`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)""")
        kotlinSourceFiles.files.sortedBy { it.path }.forEach { file ->
            file.useLines { lines ->
                lines.forEachIndexed { index, line ->
                    referenceRegex.findAll(line).forEach { match ->
                        val entryName = match.groupValues[1].removeSurrounding("`")
                        if (entryName !in validNames) {
                            throw GradleException("Missing IdDefConstants reference: Kotlin file path=${file.path}, line number=${index + 1}, entry name=$entryName")
                        }
                    }
                }
            }
        }
        logger.lifecycle("Validated IdDefConstants references in Kotlin sources")
    }
}

val generateOfficialMozcData = tasks.register("generateOfficialMozcData") {
    group = "mozc"
    description = "Builds official Mozc mozc.data with Bazel and copies it into build/generated/mozc-data."
    outputs.file(generatedMozcDataFile)
    doLast {
        val mozcSrcDir = resolveMozcSourceDirectoryForBuild()
        exec {
            workingDir = mozcSrcDir
            commandLine(mozcBazelCommand(), "build", "//data_manager/oss:mozc_dataset_for_oss")
        }
        val generated = mozcSrcDir.resolve("bazel-bin/data_manager/oss/mozc.data")
        if (!generated.isFile) {
            throw GradleException("Bazel did not produce official mozc.data: ${generated.path}")
        }
        val output = generatedMozcDataFile.get().asFile
        output.parentFile.mkdirs()
        generated.copyTo(output, overwrite = true)
        logger.lifecycle("Generated official mozc.data: ${output.path}")
    }
}

val verifyMozcData = tasks.register<JavaExec>("verifyMozcData") {
    group = "verification"
    description = "Verifies build/generated/mozc-data/mozc.data using the Kotlin Mozc data reader."
    dependsOn(generateOfficialMozcData, "classes")
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("mozc_data.MozcDataToolMainKt")
    inputs.file(generatedMozcDataFile)
    doFirst {
        setArgs(
            listOf(
                "verify",
                "--input=${generatedMozcDataFile.get().asFile.path}",
                "--expectedVersion=${mozcExpectedVersion()}",
            )
        )
    }
}

val writeMozcDataManifest = tasks.register<JavaExec>("writeMozcDataManifest") {
    group = "mozc"
    description = "Writes build/generated/mozc-data/mozc_data_manifest.json for the generated mozc.data."
    dependsOn(verifyMozcData, "classes")
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("mozc_data.MozcDataToolMainKt")
    inputs.file(generatedMozcDataFile)
    outputs.file(generatedMozcDataManifestFile)
    doFirst {
        setArgs(
            listOf(
                "manifest",
                "--input=${generatedMozcDataFile.get().asFile.path}",
                "--output=${generatedMozcDataManifestFile.get().asFile.path}",
            )
        )
    }
}

val generateMozcGoldenFixtures = tasks.register("generateMozcGoldenFixtures") {
    group = "verification"
    description = "Builds official Mozc helper binaries and writes dictionary, connector, segmenter, immutable converter, N-best, candidate filter, predictor, zero query, and rewriter golden fixtures."
    dependsOn(generateOfficialMozcData)
    inputs.file(generatedMozcDataFile)
    inputs.file(mozcImmutableConverterHelperSource)
    inputs.file(mozcNBestCandidateFilterHelperSource)
    inputs.file(mozcPredictionHelperSource)
    inputs.file(mozcRewriterHelperSource)
    inputs.property("dictionaryLookupHelperVersion", "1")
    inputs.property("connectorSegmenterHelperVersion", "1")
    inputs.property("immutableConverterHelperVersion", "1")
    inputs.property("nbestCandidateFilterHelperVersion", "1")
    inputs.property("predictionHelperVersion", "1")
    inputs.property("rewriterHelperVersion", "1")
    outputs.file(mozcGoldenDictionaryLookupFile)
    outputs.file(mozcGoldenConnectorCostFile)
    outputs.file(mozcGoldenSegmenterBoundaryFile)
    outputs.file(mozcGoldenImmutableConverterFile)
    outputs.file(mozcGoldenNBestGeneratorFile)
    outputs.file(mozcGoldenCandidateFilterFile)
    outputs.file(mozcGoldenPredictorFile)
    outputs.file(mozcGoldenZeroQueryFile)
    outputs.file(mozcGoldenRewriterFile)
    doLast {
        val mozcSrcDir = resolveMozcSourceDirectoryForBuild()
        val helperDir = generatedMozcHelperDir.get().asFile
        helperDir.mkdirs()
        helperDir.resolve("MODULE.bazel").writeText("module(name = \"mozc_helper\")\n")
        helperDir.resolve("BUILD.bazel").writeText(
            """
            load("@rules_cc//cc:cc_binary.bzl", "cc_binary")

            cc_binary(
                name = "mozc_dictionary_lookup_helper",
                srcs = ["mozc_dictionary_lookup_helper.cc"],
                deps = [
                    "@mozc//data_manager",
                    "@mozc//dictionary:dictionary_interface",
                    "@mozc//dictionary:dictionary_token",
                    "@mozc//dictionary/system:system_dictionary",
                    "@com_google_absl//absl/status:statusor",
                    "@com_google_absl//absl/strings",
                ],
            )

            cc_binary(
                name = "mozc_connector_segmenter_helper",
                srcs = ["mozc_connector_segmenter_helper.cc"],
                deps = [
                    "@mozc//converter:connector",
                    "@mozc//converter:segmenter",
                    "@mozc//data_manager",
                    "@mozc//dictionary:dictionary_interface",
                    "@mozc//dictionary:dictionary_token",
                    "@mozc//dictionary:pos_matcher",
                    "@mozc//dictionary/system:system_dictionary",
                    "@com_google_absl//absl/status:statusor",
                    "@com_google_absl//absl/strings",
                ],
            )

            cc_binary(
                name = "mozc_immutable_converter_helper",
                srcs = ["mozc_immutable_converter_helper.cc"],
                deps = [
                    "@mozc//converter:attribute",
                    "@mozc//converter:immutable_converter",
                    "@mozc//converter:inner_segment",
                    "@mozc//converter:lattice",
                    "@mozc//converter:node",
                    "@mozc//converter:segments",
                    "@mozc//data_manager",
                    "@mozc//engine:modules",
                    "@mozc//request:options",
                    "@com_google_absl//absl/status:statusor",
                ],
            )

            cc_binary(
                name = "mozc_nbest_candidate_filter_helper",
                srcs = ["mozc_nbest_candidate_filter_helper.cc"],
                deps = [
                    "@mozc//converter:attribute",
                    "@mozc//converter:candidate_filter",
                    "@mozc//converter:immutable_converter",
                    "@mozc//converter:inner_segment",
                    "@mozc//converter:lattice",
                    "@mozc//converter:node",
                    "@mozc//converter:segments",
                    "@mozc//data_manager",
                    "@mozc//engine:modules",
                    "@mozc//request:options",
                    "@com_google_absl//absl/status:statusor",
                ],
            )

            cc_binary(
                name = "mozc_prediction_helper",
                srcs = ["mozc_prediction_helper.cc"],
                deps = [
                    "@mozc//converter:attribute",
                    "@mozc//converter:converter_interface",
                    "@mozc//converter:immutable_converter",
                    "@mozc//converter:segments",
                    "@mozc//data_manager",
                    "@mozc//engine:modules",
                    "@mozc//prediction:predictor",
                    "@mozc//prediction:result",
                    "@mozc//protocol:commands_cc_proto",
                    "@mozc//protocol:config_cc_proto",
                    "@mozc//request:conversion_request",
                    "@com_google_absl//absl/status:statusor",
                    "@com_google_absl//absl/strings",
                    "@com_google_absl//absl/types:span",
                ],
            )

            cc_binary(
                name = "mozc_rewriter_helper",
                testonly = True,
                srcs = ["mozc_rewriter_helper.cc"],
                deps = [
                    "@mozc//base:clock",
                    "@mozc//base:clock_mock",
                    "@mozc//converter:attribute",
                    "@mozc//converter:immutable_converter",
                    "@mozc//converter:inner_segment",
                    "@mozc//converter:lattice",
                    "@mozc//converter:segments",
                    "@mozc//data_manager",
                    "@mozc//engine:modules",
                    "@mozc//protocol:commands_cc_proto",
                    "@mozc//protocol:config_cc_proto",
                    "@mozc//request:conversion_request",
                    "@mozc//request:options",
                    "@mozc//rewriter:rewriter",
                    "@mozc//rewriter:rewriter_interface",
                    "@com_google_absl//absl/status:statusor",
                ],
            )
            """.trimIndent()
        )
        helperDir.resolve("mozc_dictionary_lookup_helper.cc").writeText(
            """
            #include <cstdint>
            #include <fstream>
            #include <iostream>
            #include <memory>
            #include <string>
            #include <string_view>
            #include <vector>

            #include "absl/status/statusor.h"
            #include "absl/strings/string_view.h"
            #include "data_manager/data_manager.h"
            #include "dictionary/dictionary_interface.h"
            #include "dictionary/dictionary_token.h"
            #include "dictionary/system/system_dictionary.h"

            namespace {

            struct Options {
              std::string data_path;
              std::string output_path;
            };

            struct Entry {
              std::string key;
              std::string value;
              uint16_t lid;
              uint16_t rid;
              int cost;
            };

            class CollectCallback final : public mozc::dictionary::DictionaryInterface::Callback {
             public:
              ResultType OnToken(absl::string_view key, absl::string_view actual_key,
                                 const mozc::dictionary::Token& token) override {
                entries_.push_back(Entry{token.key, token.value, token.lid, token.rid, token.cost});
                return TRAVERSE_CONTINUE;
              }

              const std::vector<Entry>& entries() const { return entries_; }

             private:
              std::vector<Entry> entries_;
            };

            Options ParseOptions(int argc, char** argv) {
              Options options;
              for (int i = 1; i < argc; ++i) {
                const std::string arg = argv[i];
                const std::string data_prefix = "--data=";
                const std::string output_prefix = "--output=";
                if (arg.rfind(data_prefix, 0) == 0) {
                  options.data_path = arg.substr(data_prefix.size());
                } else if (arg.rfind(output_prefix, 0) == 0) {
                  options.output_path = arg.substr(output_prefix.size());
                }
              }
              if (options.data_path.empty() || options.output_path.empty()) {
                std::cerr << "Usage: mozc_dictionary_lookup_helper --data=/path/mozc.data --output=/path/system_dictionary_lookup.json\n";
                std::exit(2);
              }
              return options;
            }

            std::string JsonString(std::string_view value) {
              std::string out = "\"";
              for (const unsigned char ch : value) {
                switch (ch) {
                  case '\\':
                    out += "\\\\";
                    break;
                  case '"':
                    out += "\\\"";
                    break;
                  case '\b':
                    out += "\\b";
                    break;
                  case '\f':
                    out += "\\f";
                    break;
                  case '\n':
                    out += "\\n";
                    break;
                  case '\r':
                    out += "\\r";
                    break;
                  case '\t':
                    out += "\\t";
                    break;
                  default:
                    if (ch < 0x20) {
                      constexpr char hex[] = "0123456789ABCDEF";
                      out += "\\u00";
                      out += hex[ch >> 4];
                      out += hex[ch & 0x0F];
                    } else {
                      out.push_back(static_cast<char>(ch));
                    }
                }
              }
              out += "\"";
              return out;
            }

            void WriteEntries(std::ostream& out, const char* name,
                              const std::vector<Entry>& entries, int indent) {
              const std::string pad(indent, ' ');
              out << pad << JsonString(name) << ": [\n";
              for (size_t i = 0; i < entries.size(); ++i) {
                const Entry& entry = entries[i];
                out << pad << "  {\n";
                out << pad << "    \"key\": " << JsonString(entry.key) << ",\n";
                out << pad << "    \"value\": " << JsonString(entry.value) << ",\n";
                out << pad << "    \"lid\": " << entry.lid << ",\n";
                out << pad << "    \"rid\": " << entry.rid << ",\n";
                out << pad << "    \"cost\": " << entry.cost << "\n";
                out << pad << "  }";
                if (i + 1 != entries.size()) {
                  out << ",";
                }
                out << "\n";
              }
              out << pad << "]";
            }

            std::vector<Entry> LookupPrefix(const mozc::dictionary::SystemDictionary& dictionary,
                                            absl::string_view query) {
              CollectCallback callback;
              dictionary.LookupPrefix(query, &callback);
              return callback.entries();
            }

            std::vector<Entry> LookupExact(const mozc::dictionary::SystemDictionary& dictionary,
                                           absl::string_view query) {
              CollectCallback callback;
              dictionary.LookupExact(query, &callback);
              return callback.entries();
            }

            std::vector<Entry> LookupPredictive(const mozc::dictionary::SystemDictionary& dictionary,
                                                absl::string_view query) {
              CollectCallback callback;
              dictionary.LookupPredictive(query, &callback);
              return callback.entries();
            }

            std::vector<Entry> LookupReverse(const mozc::dictionary::SystemDictionary& dictionary,
                                             absl::string_view query) {
              CollectCallback callback;
              dictionary.LookupReverse(query, &callback);
              return callback.entries();
            }

            }  // namespace

            int main(int argc, char** argv) {
              const Options options = ParseOptions(argc, argv);
              absl::StatusOr<std::unique_ptr<const mozc::DataManager>> data_manager =
                  mozc::DataManager::CreateFromFile(options.data_path, mozc::DataManager::GetDataSetMagicNumber("oss"));
              if (!data_manager.ok()) {
                std::cerr << data_manager.status() << "\n";
                return 1;
              }
              const absl::string_view dictionary_data = (*data_manager)->GetSystemDictionaryData();
              absl::StatusOr<std::unique_ptr<mozc::dictionary::SystemDictionary>> dictionary =
                  mozc::dictionary::SystemDictionary::Builder(dictionary_data.data(), dictionary_data.size()).Build();
              if (!dictionary.ok()) {
                std::cerr << dictionary.status() << "\n";
                return 1;
              }

              const std::vector<std::string> queries = {
                  "へん", "へんかん", "きょう", "ありがとう", "とうきょう",
                  "かんじ", "にほん", "にほんご", "わたし", "123",
              };

              std::ofstream out(options.output_path);
              if (!out) {
                std::cerr << "Cannot open output: " << options.output_path << "\n";
                return 1;
              }

              out << "{\n";
              out << "  \"engineDataVersion\": " << JsonString((*data_manager)->GetDataVersion()) << ",\n";
              out << "  \"queries\": [\n";
              for (size_t i = 0; i < queries.size(); ++i) {
                const std::string& query = queries[i];
                out << "    {\n";
                out << "      \"query\": " << JsonString(query) << ",\n";
                WriteEntries(out, "lookupPrefix", LookupPrefix(**dictionary, query), 6);
                out << ",\n";
                WriteEntries(out, "lookupExact", LookupExact(**dictionary, query), 6);
                out << ",\n";
                WriteEntries(out, "lookupPredictive", LookupPredictive(**dictionary, query), 6);
                out << ",\n";
                WriteEntries(out, "lookupReverse", LookupReverse(**dictionary, query), 6);
                out << "\n";
                out << "    }";
                if (i + 1 != queries.size()) {
                  out << ",";
                }
                out << "\n";
              }
              out << "  ]\n";
              out << "}\n";
              return 0;
            }
            """.trimIndent()
        )
        helperDir.resolve("mozc_connector_segmenter_helper.cc").writeText(
            """
            #include <algorithm>
            #include <cstdint>
            #include <cstdlib>
            #include <fstream>
            #include <iostream>
            #include <memory>
            #include <set>
            #include <string>
            #include <string_view>
            #include <tuple>
            #include <utility>
            #include <vector>

            #include "absl/status/statusor.h"
            #include "absl/strings/string_view.h"
            #include "converter/connector.h"
            #include "converter/segmenter.h"
            #include "data_manager/data_manager.h"
            #include "dictionary/dictionary_interface.h"
            #include "dictionary/dictionary_token.h"
            #include "dictionary/pos_matcher.h"
            #include "dictionary/system/system_dictionary.h"

            namespace {

            struct Options {
              std::string data_path;
              std::string id_def_path;
              std::string connector_output_path;
              std::string segmenter_output_path;
            };

            struct IdDefEntry {
              int id;
              std::string name;
            };

            struct ConnectorCostCase {
              int left_id;
              int right_id;
              int cost;
              std::string label;
            };

            struct DictionaryEntry {
              std::string key;
              std::string value;
              uint16_t lid;
              uint16_t rid;
              int cost;
            };

            struct SegmenterCheck {
              uint16_t left_pos_id;
              uint16_t right_pos_id;
              std::string boundary_type;
              bool result;
            };

            struct SegmenterCase {
              std::string input;
              std::vector<SegmenterCheck> checks;
            };

            class CollectCallback final : public mozc::dictionary::DictionaryInterface::Callback {
             public:
              ResultType OnToken(absl::string_view key, absl::string_view actual_key,
                                 const mozc::dictionary::Token& token) override {
                entries_.push_back(DictionaryEntry{token.key, token.value, token.lid, token.rid, token.cost});
                return TRAVERSE_CONTINUE;
              }

              const std::vector<DictionaryEntry>& entries() const { return entries_; }

             private:
              std::vector<DictionaryEntry> entries_;
            };

            Options ParseOptions(int argc, char** argv) {
              Options options;
              for (int i = 1; i < argc; ++i) {
                const std::string arg = argv[i];
                const std::string data_prefix = "--data=";
                const std::string id_def_prefix = "--id_def=";
                const std::string connector_output_prefix = "--connector_output=";
                const std::string segmenter_output_prefix = "--segmenter_output=";
                if (arg.rfind(data_prefix, 0) == 0) {
                  options.data_path = arg.substr(data_prefix.size());
                } else if (arg.rfind(id_def_prefix, 0) == 0) {
                  options.id_def_path = arg.substr(id_def_prefix.size());
                } else if (arg.rfind(connector_output_prefix, 0) == 0) {
                  options.connector_output_path = arg.substr(connector_output_prefix.size());
                } else if (arg.rfind(segmenter_output_prefix, 0) == 0) {
                  options.segmenter_output_path = arg.substr(segmenter_output_prefix.size());
                }
              }
              if (options.data_path.empty() || options.id_def_path.empty() ||
                  options.connector_output_path.empty() || options.segmenter_output_path.empty()) {
                std::cerr << "Usage: mozc_connector_segmenter_helper --data=/path/mozc.data --id_def=/path/id.def --connector_output=/path/connector_cost.json --segmenter_output=/path/segmenter_boundary.json\n";
                std::exit(2);
              }
              return options;
            }

            std::string JsonString(std::string_view value) {
              std::string out = "\"";
              for (const unsigned char ch : value) {
                switch (ch) {
                  case '\\':
                    out += "\\\\";
                    break;
                  case '"':
                    out += "\\\"";
                    break;
                  case '\b':
                    out += "\\b";
                    break;
                  case '\f':
                    out += "\\f";
                    break;
                  case '\n':
                    out += "\\n";
                    break;
                  case '\r':
                    out += "\\r";
                    break;
                  case '\t':
                    out += "\\t";
                    break;
                  default:
                    if (ch < 0x20) {
                      constexpr char hex[] = "0123456789ABCDEF";
                      out += "\\u00";
                      out += hex[ch >> 4];
                      out += hex[ch & 0x0F];
                    } else {
                      out.push_back(static_cast<char>(ch));
                    }
                }
              }
              out += "\"";
              return out;
            }

            std::vector<IdDefEntry> ReadIdDef(const std::string& path) {
              std::ifstream input(path);
              if (!input) {
                std::cerr << "Cannot open id.def: " << path << "\n";
                std::exit(1);
              }
              std::vector<IdDefEntry> entries;
              std::string line;
              int line_number = 0;
              while (std::getline(input, line)) {
                ++line_number;
                if (line.empty()) {
                  continue;
                }
                const size_t separator = line.find(' ');
                if (separator == std::string::npos) {
                  std::cerr << "Invalid id.def line " << line_number << ": " << line << "\n";
                  std::exit(1);
                }
                entries.push_back(IdDefEntry{std::stoi(line.substr(0, separator)), line.substr(separator + 1)});
              }
              if (entries.empty()) {
                std::cerr << "id.def has no entries: " << path << "\n";
                std::exit(1);
              }
              return entries;
            }

            int FindIdByName(const std::vector<IdDefEntry>& entries, std::string_view name) {
              for (const IdDefEntry& entry : entries) {
                if (entry.name == name) {
                  return entry.id;
                }
              }
              std::cerr << "Cannot resolve POS id from id.def: " << name << "\n";
              std::exit(1);
            }

            std::vector<DictionaryEntry> LookupExact(
                const mozc::dictionary::SystemDictionary& dictionary,
                absl::string_view query) {
              CollectCallback callback;
              dictionary.LookupExact(query, &callback);
              return callback.entries();
            }

            bool IsUtf8Boundary(const std::string& value, size_t index) {
              return index == 0 || index == value.size() ||
                     ((static_cast<unsigned char>(value[index]) & 0xC0) != 0x80);
            }

            void AddSegmenterCheck(const mozc::Segmenter& segmenter,
                                   uint16_t left_pos_id,
                                   uint16_t right_pos_id,
                                   std::set<std::pair<uint16_t, uint16_t>>* seen,
                                   std::vector<SegmenterCheck>* checks) {
              const std::pair<uint16_t, uint16_t> key = {left_pos_id, right_pos_id};
              if (!seen->insert(key).second) {
                return;
              }
              const bool is_boundary = segmenter.IsBoundary(left_pos_id, right_pos_id);
              checks->push_back(SegmenterCheck{
                  left_pos_id,
                  right_pos_id,
                  is_boundary ? "BOUNDARY" : "NO_BOUNDARY",
                  true,
              });
            }

            std::vector<ConnectorCostCase> BuildConnectorCases(
                const mozc::Connector& connector,
                const mozc::dictionary::PosMatcher& pos_matcher,
                const std::vector<IdDefEntry>& id_def_entries) {
              const int common_noun = pos_matcher.GetGeneralNounId();
              const int case_particle = FindIdByName(id_def_entries, "助詞,格助詞,一般,*,*,*,に");
              const int verb = pos_matcher.GetWeakCompoundVerbSuffixId();
              const int auxiliary_verb = FindIdByName(id_def_entries, "助動詞,*,*,*,特殊・タ,基本形,た");
              const int proper_noun = pos_matcher.GetUniqueNounId();
              const int number = pos_matcher.GetNumberId();
              const int counter_suffix = pos_matcher.GetCounterSuffixWordId();
              const int prefix = pos_matcher.GetNounPrefixId();
              const int noun_suffix = FindIdByName(id_def_entries, "名詞,接尾,一般,*,*,*,*");

              std::vector<ConnectorCostCase> cases = {
                  {0, common_noun, 0, "BOS_TO_COMMON_NOUN"},
                  {common_noun, common_noun, 0, "COMMON_NOUN_TO_COMMON_NOUN"},
                  {common_noun, case_particle, 0, "COMMON_NOUN_TO_CASE_PARTICLE"},
                  {case_particle, verb, 0, "CASE_PARTICLE_TO_VERB"},
                  {verb, auxiliary_verb, 0, "VERB_TO_AUXILIARY_VERB"},
                  {auxiliary_verb, 0, 0, "AUXILIARY_VERB_TO_EOS"},
                  {proper_noun, case_particle, 0, "PROPER_NOUN_TO_CASE_PARTICLE"},
                  {number, counter_suffix, 0, "NUMBER_TO_COUNTER_SUFFIX"},
                  {prefix, common_noun, 0, "PREFIX_TO_NOUN"},
                  {common_noun, noun_suffix, 0, "NOUN_TO_SUFFIX"},
              };
              for (ConnectorCostCase& cost_case : cases) {
                cost_case.cost = connector.GetTransitionCost(cost_case.left_id, cost_case.right_id);
              }
              return cases;
            }

            std::vector<SegmenterCase> BuildSegmenterCases(
                const mozc::Segmenter& segmenter,
                const mozc::dictionary::SystemDictionary& dictionary,
                const mozc::dictionary::PosMatcher& pos_matcher,
                const std::vector<IdDefEntry>& id_def_entries) {
              const std::vector<std::string> inputs = {
                  "へんかん",
                  "きょう",
                  "ありがとう",
                  "とうきょう",
                  "にほんご",
                  "わたしは",
                  "これは",
                  "123",
                  "第一",
                  "山田太郎",
              };
              std::vector<SegmenterCase> cases;
              for (const std::string& input : inputs) {
                SegmenterCase segmenter_case;
                segmenter_case.input = input;
                std::set<std::pair<uint16_t, uint16_t>> seen;
                for (size_t split = 1; split < input.size(); ++split) {
                  if (!IsUtf8Boundary(input, split)) {
                    continue;
                  }
                  const std::vector<DictionaryEntry> left_entries =
                      LookupExact(dictionary, absl::string_view(input.data(), split));
                  const std::vector<DictionaryEntry> right_entries =
                      LookupExact(dictionary, absl::string_view(input.data() + split, input.size() - split));
                  const size_t left_limit = std::min<size_t>(left_entries.size(), 4);
                  const size_t right_limit = std::min<size_t>(right_entries.size(), 4);
                  for (size_t left_index = 0; left_index < left_limit; ++left_index) {
                    for (size_t right_index = 0; right_index < right_limit; ++right_index) {
                      AddSegmenterCheck(
                          segmenter,
                          left_entries[left_index].rid,
                          right_entries[right_index].lid,
                          &seen,
                          &segmenter_case.checks);
                      if (segmenter_case.checks.size() >= 12) {
                        break;
                      }
                    }
                    if (segmenter_case.checks.size() >= 12) {
                      break;
                    }
                  }
                  if (segmenter_case.checks.size() >= 12) {
                    break;
                  }
                }
                if (segmenter_case.checks.empty()) {
                  const std::vector<DictionaryEntry> exact_entries = LookupExact(dictionary, input);
                  const size_t limit = std::min<size_t>(exact_entries.size(), 12);
                  for (size_t index = 0; index < limit; ++index) {
                    AddSegmenterCheck(
                        segmenter,
                        exact_entries[index].rid,
                        exact_entries[index].lid,
                        &seen,
                        &segmenter_case.checks);
                  }
                }
                if (segmenter_case.checks.empty() &&
                    std::all_of(input.begin(), input.end(), [](unsigned char ch) {
                      return ch >= '0' && ch <= '9';
                    })) {
                  AddSegmenterCheck(
                      segmenter,
                      pos_matcher.GetNumberId(),
                      pos_matcher.GetNumberId(),
                      &seen,
                      &segmenter_case.checks);
                }
                if (segmenter_case.checks.empty() && input == "第一") {
                  AddSegmenterCheck(
                      segmenter,
                      FindIdByName(id_def_entries, "接頭詞,数接続,*,*,*,*,*"),
                      pos_matcher.GetKanjiNumberId(),
                      &seen,
                      &segmenter_case.checks);
                }
                if (segmenter_case.checks.empty() && input == "山田太郎") {
                  AddSegmenterCheck(
                      segmenter,
                      pos_matcher.GetLastNameId(),
                      pos_matcher.GetFirstNameId(),
                      &seen,
                      &segmenter_case.checks);
                }
                if (segmenter_case.checks.empty()) {
                  std::cerr << "Cannot generate segmenter checks for input: " << input << "\n";
                  std::exit(1);
                }
                cases.push_back(std::move(segmenter_case));
              }
              return cases;
            }

            void WriteConnectorFixture(const std::string& output_path,
                                       std::string_view version,
                                       const std::vector<ConnectorCostCase>& cases) {
              std::ofstream out(output_path);
              if (!out) {
                std::cerr << "Cannot open connector output: " << output_path << "\n";
                std::exit(1);
              }
              out << "{\n";
              out << "  \"engineDataVersion\": " << JsonString(version) << ",\n";
              out << "  \"costs\": [\n";
              for (size_t i = 0; i < cases.size(); ++i) {
                const ConnectorCostCase& cost_case = cases[i];
                out << "    {\n";
                out << "      \"leftId\": " << cost_case.left_id << ",\n";
                out << "      \"rightId\": " << cost_case.right_id << ",\n";
                out << "      \"cost\": " << cost_case.cost << ",\n";
                out << "      \"order\": " << i << ",\n";
                out << "      \"label\": " << JsonString(cost_case.label) << "\n";
                out << "    }";
                if (i + 1 != cases.size()) {
                  out << ",";
                }
                out << "\n";
              }
              out << "  ]\n";
              out << "}\n";
            }

            void WriteSegmenterFixture(const std::string& output_path,
                                       std::string_view version,
                                       const std::vector<SegmenterCase>& cases) {
              std::ofstream out(output_path);
              if (!out) {
                std::cerr << "Cannot open segmenter output: " << output_path << "\n";
                std::exit(1);
              }
              out << "{\n";
              out << "  \"engineDataVersion\": " << JsonString(version) << ",\n";
              out << "  \"cases\": [\n";
              for (size_t i = 0; i < cases.size(); ++i) {
                const SegmenterCase& segmenter_case = cases[i];
                out << "    {\n";
                out << "      \"input\": " << JsonString(segmenter_case.input) << ",\n";
                out << "      \"checks\": [\n";
                for (size_t j = 0; j < segmenter_case.checks.size(); ++j) {
                  const SegmenterCheck& check = segmenter_case.checks[j];
                  out << "        {\n";
                  out << "          \"leftPosId\": " << check.left_pos_id << ",\n";
                  out << "          \"rightPosId\": " << check.right_pos_id << ",\n";
                  out << "          \"boundaryType\": " << JsonString(check.boundary_type) << ",\n";
                  out << "          \"result\": " << (check.result ? "true" : "false") << ",\n";
                  out << "          \"order\": " << j << "\n";
                  out << "        }";
                  if (j + 1 != segmenter_case.checks.size()) {
                    out << ",";
                  }
                  out << "\n";
                }
                out << "      ]\n";
                out << "    }";
                if (i + 1 != cases.size()) {
                  out << ",";
                }
                out << "\n";
              }
              out << "  ]\n";
              out << "}\n";
            }

            }  // namespace

            int main(int argc, char** argv) {
              const Options options = ParseOptions(argc, argv);
              absl::StatusOr<std::unique_ptr<const mozc::DataManager>> data_manager =
                  mozc::DataManager::CreateFromFile(options.data_path, mozc::DataManager::GetDataSetMagicNumber("oss"));
              if (!data_manager.ok()) {
                std::cerr << data_manager.status() << "\n";
                return 1;
              }

              absl::StatusOr<mozc::Connector> connector =
                  mozc::Connector::Create((*data_manager)->GetConnectorData());
              if (!connector.ok()) {
                std::cerr << connector.status() << "\n";
                return 1;
              }
              const mozc::dictionary::PosMatcher pos_matcher((*data_manager)->GetPosMatcherData());
              auto segmenter_data = (*data_manager)->GetSegmenterData();
              const mozc::Segmenter segmenter(
                  std::get<0>(segmenter_data),
                  std::get<1>(segmenter_data),
                  std::get<2>(segmenter_data),
                  std::get<3>(segmenter_data),
                  std::get<4>(segmenter_data),
                  std::get<5>(segmenter_data));
              const absl::string_view dictionary_data = (*data_manager)->GetSystemDictionaryData();
              absl::StatusOr<std::unique_ptr<mozc::dictionary::SystemDictionary>> dictionary =
                  mozc::dictionary::SystemDictionary::Builder(dictionary_data.data(), dictionary_data.size()).Build();
              if (!dictionary.ok()) {
                std::cerr << dictionary.status() << "\n";
                return 1;
              }

              const std::vector<IdDefEntry> id_def_entries = ReadIdDef(options.id_def_path);
              WriteConnectorFixture(
                  options.connector_output_path,
                  (*data_manager)->GetDataVersion(),
                  BuildConnectorCases(std::move(connector).value(), pos_matcher, id_def_entries));
              WriteSegmenterFixture(
                  options.segmenter_output_path,
                  (*data_manager)->GetDataVersion(),
                  BuildSegmenterCases(segmenter, **dictionary, pos_matcher, id_def_entries));
              return 0;
            }
            """.trimIndent()
        )
        helperDir.resolve("mozc_immutable_converter_helper.cc").writeText(mozcImmutableConverterHelperSource.asFile.readText())
        helperDir.resolve("mozc_nbest_candidate_filter_helper.cc").writeText(mozcNBestCandidateFilterHelperSource.asFile.readText())
        helperDir.resolve("mozc_prediction_helper.cc").writeText(mozcPredictionHelperSource.asFile.readText())
        helperDir.resolve("mozc_rewriter_helper.cc").writeText(mozcRewriterHelperSource.asFile.readText())
        val fixtureFile = mozcGoldenDictionaryLookupFile.asFile
        fixtureFile.parentFile.mkdirs()
        exec {
            workingDir = mozcSrcDir
            commandLine(
                mozcBazelCommand(),
                "run",
                "--check_visibility=false",
                "--inject_repository=mozc_helper=${helperDir.absolutePath}",
                "@mozc_helper//:mozc_dictionary_lookup_helper",
                "--",
                "--data=${generatedMozcDataFile.get().asFile.absolutePath}",
                "--output=${fixtureFile.absolutePath}",
            )
        }
        if (!fixtureFile.isFile || fixtureFile.length() == 0L) {
            throw GradleException("Official Mozc dictionary lookup helper did not write fixture: ${fixtureFile.path}")
        }
        logger.lifecycle("Generated official Mozc dictionary lookup fixture: ${fixtureFile.path}")

        val connectorFixtureFile = mozcGoldenConnectorCostFile.asFile
        val segmenterFixtureFile = mozcGoldenSegmenterBoundaryFile.asFile
        connectorFixtureFile.parentFile.mkdirs()
        segmenterFixtureFile.parentFile.mkdirs()
        exec {
            workingDir = mozcSrcDir
            commandLine(
                mozcBazelCommand(),
                "run",
                "--check_visibility=false",
                "--inject_repository=mozc_helper=${helperDir.absolutePath}",
                "@mozc_helper//:mozc_connector_segmenter_helper",
                "--",
                "--data=${generatedMozcDataFile.get().asFile.absolutePath}",
                "--id_def=${mozcSrcDir.resolve("data/dictionary_oss/id.def").absolutePath}",
                "--connector_output=${connectorFixtureFile.absolutePath}",
                "--segmenter_output=${segmenterFixtureFile.absolutePath}",
            )
        }
        if (!connectorFixtureFile.isFile || connectorFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc connector helper did not write fixture: ${connectorFixtureFile.path}")
        }
        if (!segmenterFixtureFile.isFile || segmenterFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc segmenter helper did not write fixture: ${segmenterFixtureFile.path}")
        }
        logger.lifecycle("Generated official Mozc connector fixture: ${connectorFixtureFile.path}")
        logger.lifecycle("Generated official Mozc segmenter fixture: ${segmenterFixtureFile.path}")

        val immutableConverterFixtureFile = mozcGoldenImmutableConverterFile.asFile
        immutableConverterFixtureFile.parentFile.mkdirs()
        exec {
            workingDir = mozcSrcDir
            commandLine(
                mozcBazelCommand(),
                "run",
                "--check_visibility=false",
                "--inject_repository=mozc_helper=${helperDir.absolutePath}",
                "@mozc_helper//:mozc_immutable_converter_helper",
                "--",
                "--data=${generatedMozcDataFile.get().asFile.absolutePath}",
                "--output=${immutableConverterFixtureFile.absolutePath}",
            )
        }
        if (!immutableConverterFixtureFile.isFile || immutableConverterFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc immutable converter helper did not write fixture: ${immutableConverterFixtureFile.path}")
        }
        logger.lifecycle("Generated official Mozc immutable converter fixture: ${immutableConverterFixtureFile.path}")

        val nbestGeneratorFixtureFile = mozcGoldenNBestGeneratorFile.asFile
        val candidateFilterFixtureFile = mozcGoldenCandidateFilterFile.asFile
        nbestGeneratorFixtureFile.parentFile.mkdirs()
        candidateFilterFixtureFile.parentFile.mkdirs()
        exec {
            workingDir = mozcSrcDir
            commandLine(
                mozcBazelCommand(),
                "run",
                "--check_visibility=false",
                "--inject_repository=mozc_helper=${helperDir.absolutePath}",
                "@mozc_helper//:mozc_nbest_candidate_filter_helper",
                "--",
                "--data=${generatedMozcDataFile.get().asFile.absolutePath}",
                "--nbest_output=${nbestGeneratorFixtureFile.absolutePath}",
                "--candidate_filter_output=${candidateFilterFixtureFile.absolutePath}",
            )
        }
        if (!nbestGeneratorFixtureFile.isFile || nbestGeneratorFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc NBestGenerator helper did not write fixture: ${nbestGeneratorFixtureFile.path}")
        }
        if (!candidateFilterFixtureFile.isFile || candidateFilterFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc CandidateFilter helper did not write fixture: ${candidateFilterFixtureFile.path}")
        }
        logger.lifecycle("Generated official Mozc NBestGenerator fixture: ${nbestGeneratorFixtureFile.path}")
        logger.lifecycle("Generated official Mozc CandidateFilter fixture: ${candidateFilterFixtureFile.path}")

        val predictorFixtureFile = mozcGoldenPredictorFile.asFile
        val zeroQueryFixtureFile = mozcGoldenZeroQueryFile.asFile
        predictorFixtureFile.parentFile.mkdirs()
        zeroQueryFixtureFile.parentFile.mkdirs()
        exec {
            workingDir = mozcSrcDir
            commandLine(
                mozcBazelCommand(),
                "run",
                "--check_visibility=false",
                "--inject_repository=mozc_helper=${helperDir.absolutePath}",
                "@mozc_helper//:mozc_prediction_helper",
                "--",
                "--data=${generatedMozcDataFile.get().asFile.absolutePath}",
                "--predictor_output=${predictorFixtureFile.absolutePath}",
                "--zero_query_output=${zeroQueryFixtureFile.absolutePath}",
            )
        }
        if (!predictorFixtureFile.isFile || predictorFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc Predictor helper did not write fixture: ${predictorFixtureFile.path}")
        }
        if (!zeroQueryFixtureFile.isFile || zeroQueryFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc ZeroQuery helper did not write fixture: ${zeroQueryFixtureFile.path}")
        }
        logger.lifecycle("Generated official Mozc Predictor fixture: ${predictorFixtureFile.path}")
        logger.lifecycle("Generated official Mozc ZeroQuery fixture: ${zeroQueryFixtureFile.path}")

        val rewriterFixtureFile = mozcGoldenRewriterFile.asFile
        rewriterFixtureFile.parentFile.mkdirs()
        exec {
            workingDir = mozcSrcDir
            commandLine(
                mozcBazelCommand(),
                "run",
                "--check_visibility=false",
                "--inject_repository=mozc_helper=${helperDir.absolutePath}",
                "@mozc_helper//:mozc_rewriter_helper",
                "--",
                "--data=${generatedMozcDataFile.get().asFile.absolutePath}",
                "--output=${rewriterFixtureFile.absolutePath}",
            )
        }
        if (!rewriterFixtureFile.isFile || rewriterFixtureFile.length() == 0L) {
            throw GradleException("Official Mozc Rewriter helper did not write fixture: ${rewriterFixtureFile.path}")
        }
        logger.lifecycle("Generated official Mozc Rewriter fixture: ${rewriterFixtureFile.path}")
    }
}

tasks.test {
    useJUnitPlatform()
    dependsOn(validateMozcIdDef, validateConnectionMatrix, validateDictionaryIds, validateIdDefReferences)
}

tasks.register<Test>("dictionaryBuildTest") {
    description = "Runs the full real-dictionary build integration test."
    group = "verification"
    useJUnitPlatform()
    maxHeapSize = "4g"
    systemProperty("dictionaryBuild.full", "true")
    filter {
        includeTestsMatching("*DictionaryBuildIntegrationTest")
    }
}

tasks.register<Test>("updateDictionaryBuildBaseline") {
    description = "Runs the full dictionary build test and updates the committed performance baseline."
    group = "verification"
    useJUnitPlatform()
    maxHeapSize = "4g"
    systemProperty("dictionaryBuild.full", "true")
    systemProperty("dictionaryBuild.updateBaseline", "true")
    filter {
        includeTestsMatching("*DictionaryBuildIntegrationTest")
    }
}

kotlin {
    jvmToolchain(17)
    sourceSets.main {
        kotlin.srcDir(generatedMozcIdDefDir)
    }
}

tasks.named("compileKotlin") {
    dependsOn(generateIdDefConstants)
}

tasks.named("check") {
    dependsOn(validateMozcIdDef, validateConnectionMatrix, validateDictionaryIds, validateIdDefReferences)
}

application {
    mainClass.set("com.kazumaproject.MainKt")
}

tasks.named<JavaExec>("run") {
    dependsOn(validateDictionaryIds)
}

tasks.register<JavaExec>("runMozcUT") {
    mainClass.set("com.kazumaproject.MozcUTKt")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn(validateDictionaryIds)
}

tasks.register<JavaExec>("runMozcUTWiki") {
    mainClass.set("com.kazumaproject.MozcUTWikiKt")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn(validateDictionaryIds)
}

tasks.register<JavaExec>("runMozcUTNeologd") {
    mainClass.set("com.kazumaproject.MozcUTNeologdKt")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn(validateDictionaryIds)
}

tasks.register<JavaExec>("runMozcUTWikiNeologdCommon") {
    mainClass.set("com.kazumaproject.MozcUTWikiNeologdCommonKt")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn(validateDictionaryIds)
}

tasks.register<Zip>("packageMozcAndroidBundle") {
    group = "distribution"
    description = "Packages mozc.data, its manifest, and the Kotlin runtime jar for Android integration."
    dependsOn(verifyMozcData, writeMozcDataManifest, "test", "jar")
    archiveFileName.set("mozc_android_bundle.zip")
    destinationDirectory.set(layout.buildDirectory.dir("distributions"))
    from(generatedMozcDataFile) {
        rename { "mozc.data" }
    }
    from(generatedMozcDataManifestFile) {
        rename { "mozc_data_manifest.json" }
    }
    from(tasks.named<Jar>("jar").flatMap { it.archiveFile }) {
        rename { "mozc-runtime.jar" }
    }
}

tasks.register<Zip>("packageMozcDataBundle") {
    group = "distribution"
    description = "Packages only official mozc.data and its manifest without runtime tests."
    dependsOn(verifyMozcData, writeMozcDataManifest)
    archiveFileName.set("mozc_data_bundle.zip")
    destinationDirectory.set(layout.buildDirectory.dir("distributions"))
    from(generatedMozcDataFile) {
        rename { "mozc.data" }
    }
    from(generatedMozcDataManifestFile) {
        rename { "mozc_data_manifest.json" }
    }
}
