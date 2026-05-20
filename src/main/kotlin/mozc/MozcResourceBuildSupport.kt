package com.kazumaproject.mozc

import java.nio.file.Path
import kotlin.io.path.isRegularFile

private val mozcDictionaryResourceNames = (0..9).map { "dictionary%02d.txt".format(it) } + "suffix.txt"

fun validateBundledMozcDictionaryResources(
    resourcesDirectory: Path = Path.of("src/main/resources"),
) {
    val idDefFile = resourcesDirectory.resolve("id.def")
    val connectionFile = resourcesDirectory.resolve("connection_single_column.txt")
    require(idDefFile.isRegularFile()) { "Missing Mozc id.def: file path=$idDefFile" }
    require(connectionFile.isRegularFile()) { "Missing Mozc connection_single_column.txt: file path=$connectionFile" }

    val idDefEntries = MozcIdDefParser.parse(idDefFile)
    val connectionMatrix = ConnectionMatrixParser.parse(connectionFile)
    val dictionaryFiles = mozcDictionaryResourceNames.map { resourcesDirectory.resolve(it) }
    dictionaryFiles.forEach { path ->
        require(path.isRegularFile()) { "Missing Mozc dictionary file: file path=$path" }
    }
    MozcDictionaryValidator.validateDictionaryFiles(
        dictionaryFiles = dictionaryFiles,
        idDefEntryCount = idDefEntries.size,
        connectionMatrixSize = connectionMatrix.size,
    )
}

fun buildConnectionIdsFromResource(
    resourceName: String = "/connection_single_column.txt",
    outputPath: String = "./src/main/resources/connectionId.dat",
) {
    val stream = object {}::class.java.getResourceAsStream(resourceName)
        ?: error("connection_single_column.txt was not found in resources: resource=$resourceName")
    val connectionMatrix = stream.bufferedReader().use { reader ->
        ConnectionMatrixParser.parse(reader, resourceName)
    }
    println("connection matrix size: ${connectionMatrix.size}")
    println("connectionID size: ${connectionMatrix.costs.size}")
    // The matrix width belongs to Mozc's connection file, so keep it in the file-derived matrix instead of a Kotlin constant.
    ConnectionMatrixIO.writeRaw(connectionMatrix, Path.of(outputPath))
}
