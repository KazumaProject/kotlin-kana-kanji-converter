package com.kazumaproject.mozc

import java.nio.file.Files
import java.nio.file.Path

object IdDefConstantsReferenceValidator {
    private val referenceRegex = Regex("""(?:import\s+com\.kazumaproject\.IdDefConstants\.|IdDefConstants\.)(`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)""")

    fun validate(kotlinFiles: List<Path>, idDefEntries: List<IdDefEntry>) {
        val validNames = idDefEntries.mapTo(mutableSetOf()) { it.name }
        validNames += "BOS_EOS"

        kotlinFiles.forEach { path ->
            Files.newBufferedReader(path).use { reader ->
                reader.lineSequence().forEachIndexed { index, line ->
                    val lineNumber = index + 1
                    referenceRegex.findAll(line).forEach { match ->
                        val rawReference = match.groupValues[1]
                        val entryName = rawReference.removeSurrounding("`")
                        if (entryName !in validNames) {
                            error(
                                "Missing IdDefConstants reference: Kotlin file path=$path, " +
                                        "line number=$lineNumber, entry name=$entryName"
                            )
                        }
                    }
                }
            }
        }
    }
}
