import org.gradle.api.GradleException

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
val mozcIdDefFileProvider = providers.gradleProperty("mozcIdDefFile")
    .map { layout.projectDirectory.file(it) }
    .orElse(layout.projectDirectory.file("src/main/resources/id.def"))
val mozcConnectionFileProvider = layout.projectDirectory.file("src/main/resources/connection_single_column.txt")
val mozcDictionaryFilesProvider = files(
    (0..9).map { "src/main/resources/dictionary%02d.txt".format(it) } + "src/main/resources/suffix.txt"
)

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
