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
    description = "Builds official Mozc helper binaries and writes dictionary lookup golden fixtures."
    dependsOn(generateOfficialMozcData)
    inputs.file(generatedMozcDataFile)
    inputs.property("dictionaryLookupHelperVersion", "1")
    outputs.file(mozcGoldenDictionaryLookupFile)
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
