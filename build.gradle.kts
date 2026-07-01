import org.gradle.api.GradleException
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.InputStream
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

plugins {
    kotlin("jvm") version "1.9.21"
    kotlin("plugin.serialization") version "1.9.22"
    id("application")
}

data class BuildIdDefEntry(val id: Int, val name: String, val lineNumber: Int)

data class JapaneseKeyboardAssetSpec(
    val sourceRelativePath: String,
    val destinationRelativePath: String,
    val zipped: Boolean = false,
    val innerEntryName: String = File(sourceRelativePath).name,
)

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
val mozcIdDefFileProvider = providers.gradleProperty("mozcIdDefFile")
    .map { layout.projectDirectory.file(it) }
    .orElse(layout.projectDirectory.file("src/main/resources/id.def"))
val mozcConnectionFileProvider = layout.projectDirectory.file("src/main/resources/connection_single_column.txt")
val mozcDictionaryFilesProvider = files(
    (0..9).map { "src/main/resources/dictionary%02d.txt".format(it) } + "src/main/resources/suffix.txt"
)
val dictionaryResourcesDir = layout.projectDirectory.dir("src/main/resources")
val japaneseKeyboardAssetsRootPath = "app/src/main/assets"
val japaneseKeyboardAssetsStagingDir = layout.buildDirectory.dir("japaneseKeyboardDictionaryAssets")
val japaneseKeyboardAssetsReleaseDir = layout.projectDirectory.dir("release_zips")
val japaneseKeyboardAssetsReleaseZip = japaneseKeyboardAssetsReleaseDir.file("japanese_keyboard_dictionary_assets.zip")
val japaneseKeyboardAssetSpecs = listOf(
    JapaneseKeyboardAssetSpec("dictionary_manifest.json", "dictionary_manifest.json"),
    JapaneseKeyboardAssetSpec("connectionId.dat", "connectionId.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("pos_table.dat", "pos_table.dat"),
    JapaneseKeyboardAssetSpec("id.def", "id.def"),
    JapaneseKeyboardAssetSpec("yomi.dat", "system/yomi.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("tango.dat", "system/tango.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("token.dat", "system/token.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("yomi_singleKanji.dat", "single_kanji/yomi_singleKanji.dat"),
    JapaneseKeyboardAssetSpec("tango_singleKanji.dat", "single_kanji/tango_singleKanji.dat"),
    JapaneseKeyboardAssetSpec("token_singleKanji.dat", "single_kanji/token_singleKanji.dat"),
    JapaneseKeyboardAssetSpec("yomi_emoji.dat", "emoji/yomi_emoji.dat"),
    JapaneseKeyboardAssetSpec("tango_emoji.dat", "emoji/tango_emoji.dat"),
    JapaneseKeyboardAssetSpec("token_emoji.dat", "emoji/token_emoji.dat"),
    JapaneseKeyboardAssetSpec("yomi_emoticon.dat", "emoticon/yomi_emoticon.dat"),
    JapaneseKeyboardAssetSpec("tango_emoticon.dat", "emoticon/tango_emoticon.dat"),
    JapaneseKeyboardAssetSpec("token_emoticon.dat", "emoticon/token_emoticon.dat"),
    JapaneseKeyboardAssetSpec("yomi_symbol.dat", "symbol/yomi_symbol.dat"),
    JapaneseKeyboardAssetSpec("tango_symbol.dat", "symbol/tango_symbol.dat"),
    JapaneseKeyboardAssetSpec("token_symbol.dat", "symbol/token_symbol.dat"),
    JapaneseKeyboardAssetSpec("yomi_reading_correction.dat", "reading_correction/yomi_reading_correction.dat"),
    JapaneseKeyboardAssetSpec("tango_reading_correction.dat", "reading_correction/tango_reading_correction.dat"),
    JapaneseKeyboardAssetSpec("token_reading_correction.dat", "reading_correction/token_reading_correction.dat"),
    JapaneseKeyboardAssetSpec("yomi_kotowaza.dat", "kotowaza/yomi_kotowaza.dat"),
    JapaneseKeyboardAssetSpec("tango_kotowaza.dat", "kotowaza/tango_kotowaza.dat"),
    JapaneseKeyboardAssetSpec("token_kotowaza.dat", "kotowaza/token_kotowaza.dat"),
    JapaneseKeyboardAssetSpec("yomi_person_names.dat", "person_name/yomi_person_names.dat"),
    JapaneseKeyboardAssetSpec("tango_person_names.dat", "person_name/tango_person_names.dat"),
    JapaneseKeyboardAssetSpec("token_person_names.dat", "person_name/token_person_names.dat"),
    JapaneseKeyboardAssetSpec("yomi_places.dat", "places/yomi_places.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("tango_places.dat", "places/tango_places.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("token_places.dat", "places/token_places.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("yomi_wiki.dat", "wiki/yomi_wiki.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("tango_wiki.dat", "wiki/tango_wiki.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("token_wiki.dat", "wiki/token_wiki.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("yomi_neologd.dat", "neologd/yomi_neologd.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("tango_neologd.dat", "neologd/tango_neologd.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("token_neologd.dat", "neologd/token_neologd.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("yomi_web.dat", "web/yomi_web.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("tango_web.dat", "web/tango_web.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("token_web.dat", "web/token_web.dat.zip", zipped = true),
    JapaneseKeyboardAssetSpec("zero_query_token.data", "mozc/zero_query/zero_query_token.data"),
    JapaneseKeyboardAssetSpec("zero_query_string.data", "mozc/zero_query/zero_query_string.data"),
    JapaneseKeyboardAssetSpec("zero_query_number_token.data", "mozc/zero_query/zero_query_number_token.data"),
    JapaneseKeyboardAssetSpec("zero_query_number_string.data", "mozc/zero_query/zero_query_number_string.data"),
    JapaneseKeyboardAssetSpec("ngram/ngram_presence.data", "ngram/ngram_presence.data"),
    JapaneseKeyboardAssetSpec("ngram/ngram_presence_manifest.json", "ngram/ngram_presence_manifest.json"),
    JapaneseKeyboardAssetSpec("ngram/stable_term_id_map.tsv", "ngram/stable_term_id_map.tsv"),
)

val mozcZeroQueryOfficialResourceNames = listOf(
    "zero_query.def",
    "zero_query_number.def",
    "mozc_emoji_data.tsv",
    "mozc_emoticon_categorized.tsv",
    "mozc_symbol.tsv",
)
val mozcZeroQueryGeneratedResourceNames = listOf(
    "zero_query_token.data",
    "zero_query_string.data",
    "zero_query_number_token.data",
    "zero_query_number_string.data",
)
val mozcZeroQueryAuditResourceName = "zero_query_data.tsv"
val mozcCustomZeroQueryResourceName = "custom_zero_query.def"
val mozcCustomZeroQueryFileProvider = layout.projectDirectory.file("src/main/custom_zero_query.def")
val committedNgramSourcesDir = layout.projectDirectory.dir("src/main/ngram/sources")
val ngramSourcesDir = dictionaryResourcesDir.dir("ngram/sources")
val stableTermIdMapFile = dictionaryResourcesDir.file("ngram/stable_term_id_map.tsv")
val ngramPresenceDataFile = dictionaryResourcesDir.file("ngram/ngram_presence.data")
val ngramPresenceManifestFile = dictionaryResourcesDir.file("ngram/ngram_presence_manifest.json")
val dictionaryManifestFile = dictionaryResourcesDir.file("dictionary_manifest.json")

fun requireNonEmptyFile(file: File, label: String) {
    if (!file.isFile) {
        throw GradleException("Missing JapaneseKeyboard dictionary asset: $label, file path=${file.path}")
    }
    if (file.length() == 0L) {
        throw GradleException("Empty JapaneseKeyboard dictionary asset: $label, file path=${file.path}")
    }
}

fun splitBuildPreservingEmpty(value: String, delimiter: Char): List<String> {
    val result = mutableListOf<String>()
    var start = 0
    while (true) {
        val index = value.indexOf(delimiter, start)
        if (index < 0) {
            result += value.substring(start)
            return result
        }
        result += value.substring(start, index)
        start = index + 1
    }
}

fun isMozcDataLine(line: String): Boolean = line.trim().isNotEmpty() && !line.trimStart().startsWith("#")

fun requireMozcZeroQueryFile(file: File, label: String, allowEmpty: Boolean = false) {
    if (!file.isFile) {
        throw GradleException("Missing Mozc zero query resource: $label, file path=${file.path}")
    }
    if (!allowEmpty && file.length() == 0L) {
        throw GradleException("Empty Mozc zero query resource: $label, file path=${file.path}")
    }
}

fun validateMozcTwoColumnFile(file: File, label: String): List<List<String>> {
    val dataRows = mutableListOf<List<String>>()
    file.useLines { lines ->
        lines.forEachIndexed { index, rawLine ->
            if (!isMozcDataLine(rawLine)) return@forEachIndexed
            val columns = splitBuildPreservingEmpty(rawLine, '\t')
            if (columns.size != 2) {
                throw GradleException(
                    "Invalid $label: file path=${file.path}, line number=${index + 1}, " +
                            "reason=expected exactly 2 tab-separated columns"
                )
            }
            dataRows += columns
        }
    }
    return dataRows
}

fun validateZipEntryName(name: String, context: String) {
    if (name.isBlank() || name.startsWith("/") || name.contains('\\') || name.split('/').any { it == ".." }) {
        throw GradleException("Invalid zip entry path in $context: entry=$name")
    }
    val segments = name.split('/')
    if (segments.any { it == "__MACOSX" || it == ".DS_Store" || it.startsWith("._") }) {
        throw GradleException("Unexpected metadata entry in $context: entry=$name")
    }
}

fun writeSingleFileZip(sourceFile: File, destinationZip: File, entryName: String) {
    validateZipEntryName(entryName, destinationZip.path)
    if (entryName.contains('/')) {
        throw GradleException("Inner .dat.zip entry must not contain a directory: zip=${destinationZip.path}, entry=$entryName")
    }
    destinationZip.parentFile.mkdirs()
    ZipOutputStream(BufferedOutputStream(destinationZip.outputStream())).use { zipOutput ->
        val entry = ZipEntry(entryName)
        entry.time = 0L
        zipOutput.putNextEntry(entry)
        sourceFile.inputStream().use { input ->
            input.copyTo(zipOutput)
        }
        zipOutput.closeEntry()
    }
}

fun writeDirectoryZip(sourceDirectory: File, destinationZip: File) {
    val files = sourceDirectory.walkTopDown()
        .filter { it.isFile }
        .sortedBy { it.relativeTo(sourceDirectory).invariantSeparatorsPath }
        .toList()
    if (files.isEmpty()) {
        throw GradleException("No files to zip: source directory=${sourceDirectory.path}")
    }
    destinationZip.parentFile.mkdirs()
    ZipOutputStream(BufferedOutputStream(destinationZip.outputStream())).use { zipOutput ->
        files.forEach { file ->
            requireNonEmptyFile(file, file.relativeTo(sourceDirectory).invariantSeparatorsPath)
            val entryName = file.relativeTo(sourceDirectory).invariantSeparatorsPath
            validateZipEntryName(entryName, destinationZip.path)
            val entry = ZipEntry(entryName)
            entry.time = 0L
            zipOutput.putNextEntry(entry)
            file.inputStream().use { input ->
                input.copyTo(zipOutput)
            }
            zipOutput.closeEntry()
        }
    }
}

fun ensureNonEmptyZipEntry(zipFile: ZipFile, entry: ZipEntry, context: String) {
    if (entry.size == 0L) {
        throw GradleException("Empty zip entry in $context: entry=${entry.name}")
    }
    if (entry.size < 0L) {
        zipFile.getInputStream(entry).use { input ->
            if (input.read() == -1) {
                throw GradleException("Empty zip entry in $context: entry=${entry.name}")
            }
        }
    }
}

fun verifySingleEntryZip(inputStream: InputStream, outerEntryName: String, expectedInnerEntryName: String) {
    val innerEntries = mutableListOf<String>()
    ZipInputStream(BufferedInputStream(inputStream)).use { zipInput ->
        var entry = zipInput.nextEntry
        while (entry != null) {
            validateZipEntryName(entry.name, outerEntryName)
            if (entry.isDirectory) {
                throw GradleException("Directory entry is not allowed inside .dat.zip: zip=$outerEntryName, entry=${entry.name}")
            }
            if (entry.name.contains('/')) {
                throw GradleException("Nested path is not allowed inside .dat.zip: zip=$outerEntryName, entry=${entry.name}")
            }
            var uncompressedSize = 0L
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = zipInput.read(buffer)
                if (read < 0) break
                uncompressedSize += read
            }
            if (uncompressedSize == 0L) {
                throw GradleException("Empty .dat entry inside .dat.zip: zip=$outerEntryName, entry=${entry.name}")
            }
            innerEntries += entry.name
            zipInput.closeEntry()
            entry = zipInput.nextEntry
        }
    }
    if (innerEntries != listOf(expectedInnerEntryName)) {
        throw GradleException(
            "Invalid .dat.zip contents: zip=$outerEntryName, expected=[$expectedInnerEntryName], actual=$innerEntries"
        )
    }
}

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

val validateMozcZeroQueryResources = tasks.register("validateMozcZeroQueryResources") {
    group = "verification"
    description = "Validates Mozc zero query source resources copied from google/mozc and the custom overlay."
    inputs.files(mozcZeroQueryOfficialResourceNames.map { dictionaryResourcesDir.file(it) })
    inputs.file(mozcCustomZeroQueryFileProvider)
    doLast {
        val resourcesDirectory = dictionaryResourcesDir.asFile

        val zeroQueryDef = resourcesDirectory.resolve("zero_query.def")
        val zeroQueryNumberDef = resourcesDirectory.resolve("zero_query_number.def")
        val emojiData = resourcesDirectory.resolve("mozc_emoji_data.tsv")
        val emoticonCategorized = resourcesDirectory.resolve("mozc_emoticon_categorized.tsv")
        val symbol = resourcesDirectory.resolve("mozc_symbol.tsv")
        val custom = mozcCustomZeroQueryFileProvider.asFile

        requireMozcZeroQueryFile(zeroQueryDef, "zero_query.def")
        requireMozcZeroQueryFile(zeroQueryNumberDef, "zero_query_number.def")
        requireMozcZeroQueryFile(emojiData, "mozc_emoji_data.tsv")
        requireMozcZeroQueryFile(emoticonCategorized, "mozc_emoticon_categorized.tsv")
        requireMozcZeroQueryFile(symbol, "mozc_symbol.tsv")
        requireMozcZeroQueryFile(custom, mozcCustomZeroQueryResourceName, allowEmpty = true)

        validateMozcTwoColumnFile(zeroQueryDef, "zero_query.def")
        val numberRows = validateMozcTwoColumnFile(zeroQueryNumberDef, "zero_query_number.def")
        if (numberRows.none { it[0] == "default" }) {
            throw GradleException("Invalid zero_query_number.def: file path=${zeroQueryNumberDef.path}, reason=missing default key")
        }

        emojiData.useLines { lines ->
            lines.forEachIndexed { index, rawLine ->
                if (!isMozcDataLine(rawLine)) return@forEachIndexed
                val columns = splitBuildPreservingEmpty(rawLine, '\t')
                if (columns.size != 7) {
                    throw GradleException(
                        "Invalid mozc_emoji_data.tsv: file path=${emojiData.path}, line number=${index + 1}, " +
                                "reason=expected exactly 7 tab-separated columns"
                    )
                }
            }
        }

        emoticonCategorized.useLines { lines ->
            lines.forEachIndexed { index, rawLine ->
                if (!isMozcDataLine(rawLine)) return@forEachIndexed
                val columns = splitBuildPreservingEmpty(rawLine, '\t')
                if (columns.size != 3) {
                    throw GradleException(
                        "Invalid mozc_emoticon_categorized.tsv: file path=${emoticonCategorized.path}, line number=${index + 1}, " +
                                "reason=expected exactly 3 tab-separated columns"
                    )
                }
            }
        }

        var symbolHeaderSeen = false
        symbol.useLines { lines ->
            lines.forEachIndexed { index, rawLine ->
                if (!isMozcDataLine(rawLine)) return@forEachIndexed
                val columns = splitBuildPreservingEmpty(rawLine, '\t')
                if (!symbolHeaderSeen) {
                    if (columns.size >= 3 && columns[0] == "POS" && columns[1] == "CHAR") {
                        symbolHeaderSeen = true
                        return@forEachIndexed
                    }
                    throw GradleException(
                        "Invalid mozc_symbol.tsv: file path=${symbol.path}, line number=${index + 1}, reason=missing header"
                    )
                }
                if (columns.size < 3) {
                    throw GradleException(
                        "Invalid mozc_symbol.tsv: file path=${symbol.path}, line number=${index + 1}, " +
                                "reason=expected at least 3 tab-separated columns"
                    )
                }
            }
        }
        if (!symbolHeaderSeen) {
            throw GradleException("Invalid mozc_symbol.tsv: file path=${symbol.path}, reason=missing header")
        }

        logger.lifecycle("Validated Mozc zero query resources")
    }
}

tasks.test {
    useJUnitPlatform()
    dependsOn(validateMozcIdDef, validateConnectionMatrix, validateDictionaryIds, validateIdDefReferences, validateMozcZeroQueryResources)
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
    dependsOn(validateMozcIdDef, validateConnectionMatrix, validateDictionaryIds, validateIdDefReferences, validateMozcZeroQueryResources)
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

tasks.named("runMozcUT") {
    mustRunAfter("run")
}

tasks.named("runMozcUTWiki") {
    mustRunAfter("runMozcUT")
}

tasks.named("runMozcUTNeologd") {
    mustRunAfter("runMozcUTWiki")
}

tasks.named("runMozcUTWikiNeologdCommon") {
    mustRunAfter("runMozcUTNeologd")
}

val generateMozcZeroQueryData = tasks.register<JavaExec>("generateMozcZeroQueryData") {
    group = "distribution"
    description = "Generates Mozc-compatible zero query binary data from official resources and the custom overlay."
    mainClass.set("com.kazumaproject.mozc.zeroquery.GenerateMozcZeroQueryData")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn("compileKotlin", validateMozcZeroQueryResources)
    inputs.files(mozcZeroQueryOfficialResourceNames.map { dictionaryResourcesDir.file(it) })
    inputs.file(mozcCustomZeroQueryFileProvider)
    outputs.files((mozcZeroQueryGeneratedResourceNames + mozcZeroQueryAuditResourceName).map { dictionaryResourcesDir.file(it) })
    args(
        "--zero_query_def", dictionaryResourcesDir.file("zero_query.def").asFile.path,
        "--zero_query_number_def", dictionaryResourcesDir.file("zero_query_number.def").asFile.path,
        "--emoji_data", dictionaryResourcesDir.file("mozc_emoji_data.tsv").asFile.path,
        "--emoticon_categorized", dictionaryResourcesDir.file("mozc_emoticon_categorized.tsv").asFile.path,
        "--symbol", dictionaryResourcesDir.file("mozc_symbol.tsv").asFile.path,
        "--custom_zero_query_def", mozcCustomZeroQueryFileProvider.asFile.path,
        "--output_dir", dictionaryResourcesDir.asFile.path,
    )
}

val verifyMozcZeroQueryData = tasks.register<JavaExec>("verifyMozcZeroQueryData") {
    group = "verification"
    description = "Verifies generated Mozc zero query binary data and required lookups."
    mainClass.set("com.kazumaproject.mozc.zeroquery.VerifyMozcZeroQueryData")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn("compileKotlin", generateMozcZeroQueryData)
    inputs.files(mozcZeroQueryGeneratedResourceNames.map { dictionaryResourcesDir.file(it) })
    args("--input_dir", dictionaryResourcesDir.asFile.path)
}

val verifyMozcZeroQueryParity = tasks.register("verifyMozcZeroQueryParity") {
    group = "verification"
    description = "Compares Kotlin zero query generation with the official Mozc Python generators using an empty custom overlay."
    dependsOn("compileKotlin")
    doLast {
        val mozcSourceDir = file(providers.gradleProperty("mozcSourceDir").orNull ?: "./mozc-src")
        val mozcSrcRoot = mozcSourceDir.resolve("src")
        val officialGenerator = mozcSrcRoot.resolve("prediction/gen_zero_query_data.py")
        val officialNumberGenerator = mozcSrcRoot.resolve("prediction/gen_zero_query_number_data.py")
        if (!officialGenerator.isFile || !officialNumberGenerator.isFile) {
            throw GradleException("Missing Mozc official zero query generators: mozcSourceDir=${mozcSourceDir.path}")
        }

        delete(temporaryDir)
        val officialOutput = temporaryDir.resolve("official").apply { mkdirs() }
        val kotlinOutput = temporaryDir.resolve("kotlin").apply { mkdirs() }
        val emptyCustom = temporaryDir.resolve("empty_custom_zero_query.def").apply { writeText("") }

        exec {
            workingDir = mozcSrcRoot
            environment("PYTHONPATH", mozcSrcRoot.path)
            commandLine(
                "python3",
                "prediction/gen_zero_query_data.py",
                "--input_rule", "data/zero_query/zero_query.def",
                "--input_symbol", "data/symbol/symbol.tsv",
                "--input_emoji", "data/emoji/emoji_data.tsv",
                "--input_emoticon", "data/emoticon/categorized.tsv",
                "--output_token_array", officialOutput.resolve("zero_query_token.data").path,
                "--output_string_array", officialOutput.resolve("zero_query_string.data").path,
            )
        }
        exec {
            workingDir = mozcSrcRoot
            environment("PYTHONPATH", mozcSrcRoot.path)
            commandLine(
                "python3",
                "prediction/gen_zero_query_number_data.py",
                "--input", "data/zero_query/zero_query_number.def",
                "--output_token_array", officialOutput.resolve("zero_query_number_token.data").path,
                "--output_string_array", officialOutput.resolve("zero_query_number_string.data").path,
            )
        }
        javaexec {
            mainClass.set("com.kazumaproject.mozc.zeroquery.GenerateMozcZeroQueryData")
            classpath = sourceSets["main"].runtimeClasspath
            args(
                "--zero_query_def", mozcSrcRoot.resolve("data/zero_query/zero_query.def").path,
                "--zero_query_number_def", mozcSrcRoot.resolve("data/zero_query/zero_query_number.def").path,
                "--emoji_data", mozcSrcRoot.resolve("data/emoji/emoji_data.tsv").path,
                "--emoticon_categorized", mozcSrcRoot.resolve("data/emoticon/categorized.tsv").path,
                "--symbol", mozcSrcRoot.resolve("data/symbol/symbol.tsv").path,
                "--custom_zero_query_def", emptyCustom.path,
                "--output_dir", kotlinOutput.path,
            )
        }

        mozcZeroQueryGeneratedResourceNames.forEach { fileName ->
            val officialFile = officialOutput.resolve(fileName).toPath()
            val kotlinFile = kotlinOutput.resolve(fileName).toPath()
            val mismatch = Files.mismatch(officialFile, kotlinFile)
            if (mismatch != -1L) {
                throw GradleException("Zero query parity mismatch: file=$fileName, byte offset=$mismatch")
            }
        }
        logger.lifecycle("Verified Mozc zero query parity against official Python generators: mozcSourceDir=${mozcSourceDir.path}")
    }
}

val prepareNgramSources = tasks.register<Copy>("prepareNgramSources") {
    group = "distribution"
    description = "Copies committed N-gram TSV sources into the ignored resources input directory."
    val sourceTree = fileTree(committedNgramSourcesDir) {
        include("*.tsv")
    }
    from(sourceTree)
    into(ngramSourcesDir)
    doFirst {
        if (sourceTree.files.isEmpty()) {
            throw GradleException("Missing committed N-gram TSV sources: directory=${committedNgramSourcesDir.asFile.path}")
        }
    }
}

tasks.named("processResources") {
    dependsOn(prepareNgramSources)
}

val generateStableTermIdMap = tasks.register<JavaExec>("generateStableTermIdMap") {
    group = "distribution"
    description = "Generates the stable termId/token map used by the N-gram presence dictionary."
    mainClass.set("com.kazumaproject.ngram.GenerateStableTermIdMap")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn("compileKotlin", validateDictionaryIds)
    inputs.files(mozcDictionaryFilesProvider)
    inputs.file(mozcIdDefFileProvider)
    outputs.file(stableTermIdMapFile)
    args("--output", stableTermIdMapFile.asFile.path)
}

val generateTokenArrayV2 = tasks.register("generateTokenArrayV2") {
    group = "distribution"
    description = "Compatibility lifecycle task for token data with stable N-gram term IDs."
    dependsOn(generateStableTermIdMap)
}

val generateNgramPresenceData = tasks.register<JavaExec>("generateNgramPresenceData") {
    group = "distribution"
    description = "Generates the BDZ MPHF N-gram presence dictionary and manifest."
    mainClass.set("com.kazumaproject.ngram.GenerateNgramPresenceData")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn("compileKotlin", prepareNgramSources, generateStableTermIdMap)
    inputs.dir(ngramSourcesDir)
    inputs.file(stableTermIdMapFile)
    outputs.file(ngramPresenceDataFile)
    outputs.file(ngramPresenceManifestFile)
    outputs.file(dictionaryManifestFile)
    args(
        "--sources_dir", ngramSourcesDir.asFile.path,
        "--term_id_map", stableTermIdMapFile.asFile.path,
        "--output_data", ngramPresenceDataFile.asFile.path,
        "--output_manifest", ngramPresenceManifestFile.asFile.path,
        "--dictionary_manifest", dictionaryManifestFile.asFile.path,
    )
}

val verifyNgramPresenceData = tasks.register<JavaExec>("verifyNgramPresenceData") {
    group = "verification"
    description = "Verifies generated N-gram presence lookups and negative probes."
    mainClass.set("com.kazumaproject.ngram.VerifyNgramPresenceData")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn("compileKotlin", generateNgramPresenceData)
    inputs.dir(ngramSourcesDir)
    inputs.file(stableTermIdMapFile)
    inputs.file(ngramPresenceDataFile)
    args(
        "--sources_dir", ngramSourcesDir.asFile.path,
        "--term_id_map", stableTermIdMapFile.asFile.path,
        "--input_data", ngramPresenceDataFile.asFile.path,
    )
}

val dumpNgramPresenceManifest = tasks.register<JavaExec>("dumpNgramPresenceManifest") {
    group = "verification"
    description = "Dumps the generated N-gram presence manifest."
    mainClass.set("com.kazumaproject.ngram.DumpNgramPresenceManifest")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn(generateNgramPresenceData)
    inputs.file(ngramPresenceManifestFile)
    args("--manifest", ngramPresenceManifestFile.asFile.path)
}

tasks.register<JavaExec>("probeNgramPresencePerformance") {
    group = "verification"
    description = "Prints N-gram presence load, heap, lookup, size, and verification probes."
    mainClass.set("com.kazumaproject.ngram.ProbeNgramPresencePerformance")
    classpath = sourceSets["main"].runtimeClasspath
    dependsOn(generateNgramPresenceData)
    inputs.dir(ngramSourcesDir)
    inputs.file(stableTermIdMapFile)
    inputs.file(ngramPresenceDataFile)
    args(
        "--sources_dir", ngramSourcesDir.asFile.path,
        "--term_id_map", stableTermIdMapFile.asFile.path,
        "--input_data", ngramPresenceDataFile.asFile.path,
    )
}

val generateJapaneseKeyboardDictionaries = tasks.register("generateJapaneseKeyboardDictionaries") {
    group = "distribution"
    description = "Generates all dictionary .dat files used by the JapaneseKeyboard assets package."
    dependsOn(
        "run",
        "runMozcUT",
        "runMozcUTWiki",
        "runMozcUTNeologd",
        "runMozcUTWikiNeologdCommon",
        generateMozcZeroQueryData,
        generateStableTermIdMap,
        generateTokenArrayV2,
        generateNgramPresenceData,
        verifyNgramPresenceData,
        dumpNgramPresenceManifest,
    )
}

val packageJapaneseKeyboardDictionaryAssets = tasks.register("packageJapaneseKeyboardDictionaryAssets") {
    group = "distribution"
    description = "Packages generated dictionaries as app/src/main/assets for JapaneseKeyboard."
    dependsOn(generateJapaneseKeyboardDictionaries)
    inputs.files(japaneseKeyboardAssetSpecs.map { dictionaryResourcesDir.file(it.sourceRelativePath) })
    outputs.dir(japaneseKeyboardAssetsStagingDir)
    outputs.file(japaneseKeyboardAssetsReleaseZip)

    doLast {
        val resourcesDirectory = dictionaryResourcesDir.asFile
        val stagingDirectory = japaneseKeyboardAssetsStagingDir.get().asFile
        val assetsDirectory = stagingDirectory.resolve(japaneseKeyboardAssetsRootPath)
        val releaseDirectory = japaneseKeyboardAssetsReleaseDir.asFile
        val releaseZip = japaneseKeyboardAssetsReleaseZip.asFile

        delete(stagingDirectory)
        delete(releaseDirectory)
        assetsDirectory.mkdirs()

        japaneseKeyboardAssetSpecs.forEach { spec ->
            val sourceFile = resourcesDirectory.resolve(spec.sourceRelativePath)
            val destinationFile = assetsDirectory.resolve(spec.destinationRelativePath)
            requireNonEmptyFile(sourceFile, spec.sourceRelativePath)
            destinationFile.parentFile.mkdirs()
            if (spec.zipped) {
                writeSingleFileZip(sourceFile, destinationFile, spec.innerEntryName)
            } else {
                sourceFile.copyTo(destinationFile, overwrite = true)
            }
        }

        writeDirectoryZip(stagingDirectory, releaseZip)
        logger.lifecycle("Wrote JapaneseKeyboard dictionary assets: ${releaseZip.path}")
    }
}

tasks.register("verifyJapaneseKeyboardDictionaryAssets") {
    group = "verification"
    description = "Verifies the JapaneseKeyboard dictionary assets zip layout and nested .dat.zip files."
    dependsOn(packageJapaneseKeyboardDictionaryAssets)
    inputs.file(japaneseKeyboardAssetsReleaseZip)

    doLast {
        val releaseZip = japaneseKeyboardAssetsReleaseZip.asFile
        requireNonEmptyFile(releaseZip, "release zip")

        val expectedEntriesByName = japaneseKeyboardAssetSpecs.associateBy {
            "$japaneseKeyboardAssetsRootPath/${it.destinationRelativePath}"
        }

        ZipFile(releaseZip).use { zipFile ->
            val allEntries = zipFile.entries().asSequence().toList()
            if (allEntries.isEmpty()) {
                throw GradleException("Release zip is empty: file path=${releaseZip.path}")
            }
            allEntries.forEach { entry ->
                validateZipEntryName(entry.name.removeSuffix("/"), releaseZip.path)
            }

            val actualFileEntries = allEntries
                .filterNot { it.isDirectory }
                .map { it.name }
                .toSet()
            val expectedFileEntries = expectedEntriesByName.keys
            val missingEntries = expectedFileEntries - actualFileEntries
            val unexpectedEntries = actualFileEntries - expectedFileEntries
            if (missingEntries.isNotEmpty() || unexpectedEntries.isNotEmpty()) {
                throw GradleException(
                    "Invalid JapaneseKeyboard assets zip entries: missing=$missingEntries, unexpected=$unexpectedEntries"
                )
            }

            expectedEntriesByName.forEach { (entryName, spec) ->
                val entry = zipFile.getEntry(entryName)
                    ?: throw GradleException("Missing required zip entry: $entryName")
                if (entry.isDirectory) {
                    throw GradleException("Required zip entry is a directory: $entryName")
                }
                ensureNonEmptyZipEntry(zipFile, entry, releaseZip.path)
                if (spec.zipped) {
                    zipFile.getInputStream(entry).use { input ->
                        verifySingleEntryZip(input, entryName, spec.innerEntryName)
                    }
                }
            }
        }

        logger.lifecycle("Verified JapaneseKeyboard dictionary assets: ${releaseZip.path}")
    }
}
