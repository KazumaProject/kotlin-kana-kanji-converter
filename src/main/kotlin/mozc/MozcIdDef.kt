package com.kazumaproject.mozc

import java.io.BufferedReader
import java.nio.file.Files
import java.nio.file.Path

data class IdDefEntry(
    val id: Int,
    val name: String,
    val lineNumber: Int,
)

object MozcIdDefParser {
    private const val BosEosName = "BOS/EOS,*,*,*,*,*,*"

    fun parse(path: Path): List<IdDefEntry> =
        Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString())
        }

    fun parse(reader: BufferedReader, filePath: String): List<IdDefEntry> {
        val entries = mutableListOf<IdDefEntry>()
        val seenIds = mutableMapOf<Int, IdDefEntry>()
        val seenNames = mutableMapOf<String, IdDefEntry>()

        reader.lineSequence().forEachIndexed { index, rawLine ->
            val lineNumber = index + 1
            if (rawLine.isEmpty()) {
                fail(filePath, lineNumber, rawLine, "blank lines are not valid in id.def")
            }

            val separatorIndex = rawLine.indexOfFirst { it.isWhitespace() }
            if (separatorIndex <= 0) {
                fail(filePath, lineNumber, rawLine, "expected '<id> <name>'")
            }

            val idText = rawLine.substring(0, separatorIndex)
            val name = rawLine.substring(separatorIndex + 1)
            if (name.isEmpty()) {
                fail(filePath, lineNumber, rawLine, "missing name")
            }

            val id = idText.toIntOrNull()
                ?: fail(filePath, lineNumber, rawLine, "invalid Int ID '$idText'")
            if (id !in Short.MIN_VALUE..Short.MAX_VALUE) {
                fail(filePath, lineNumber, rawLine, "ID is outside Short range: id=$id name=$name")
            }

            val entry = IdDefEntry(id, name, lineNumber)
            seenIds.putIfAbsent(id, entry)?.let { first ->
                error(
                    "Duplicate id.def ID in $filePath: duplicated ID=$id, " +
                            "first line=${first.lineNumber}, second line=$lineNumber, name=$name"
                )
            }
            seenNames.putIfAbsent(name, entry)?.let { first ->
                error(
                    "Duplicate id.def name in $filePath: name=$name, " +
                            "first ID=${first.id} line=${first.lineNumber}, second ID=$id line=$lineNumber"
                )
            }
            entries += entry
        }

        validateSequence(entries, filePath)
        return entries
    }

    private fun validateSequence(entries: List<IdDefEntry>, filePath: String) {
        if (entries.isEmpty()) {
            error("id.def is empty: file path=$filePath")
        }
        val first = entries.first()
        if (first.id != 0) {
            error(
                "Invalid id.def sequence in $filePath: expected ID=0, actual ID=${first.id}, " +
                        "line=${first.lineNumber}, name=${first.name}, reason=ID must start from 0"
            )
        }
        if (first.name != BosEosName) {
            error(
                "Invalid BOS/EOS in $filePath: actual ID 0 name=${first.name}, expected name=$BosEosName"
            )
        }

        entries.forEachIndexed { expectedId, entry ->
            if (entry.id != expectedId) {
                error(
                    "Invalid id.def sequence in $filePath: expected ID=$expectedId, actual ID=${entry.id}, " +
                            "line=${entry.lineNumber}, name=${entry.name}, reason=ID must be continuous"
                )
            }
        }

        val lastId = entries.last().id
        if (entries.size != lastId + 1) {
            error(
                "Invalid id.def entry count in $filePath: entry count=${entries.size}, " +
                        "last ID=$lastId, reason=entry count must equal last ID + 1"
            )
        }
    }

    private fun fail(filePath: String, lineNumber: Int, rawLine: String, reason: String): Nothing {
        error("Failed to parse id.def: file path=$filePath, line number=$lineNumber, raw line='$rawLine', reason=$reason")
    }
}

object IdDefConstantsGenerator {
    fun generate(entries: List<IdDefEntry>): String = buildString {
        appendLine("@file:Suppress(\"DANGEROUS_CHARACTERS\")")
        appendLine()
        appendLine("package com.kazumaproject")
        appendLine()
        appendLine("/**")
        appendLine(" * Auto-generated from Mozc id.def.")
        appendLine(" * Do not edit manually.")
        appendLine(" */")
        appendLine("object IdDefConstants {")
        val nonPropertyEntries = mutableListOf<IdDefEntry>()
        entries.forEach { entry ->
            if (entry.id == 0) {
                appendLine("    const val BOS_EOS = (0).toShort()")
            } else if (canUseBacktickIdentifier(entry.name)) {
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
                appendLine("        ${entry.name.toKotlinStringLiteral()} to (${entry.id}).toShort(),")
            }
            appendLine("    )")
        }
        appendLine("}")
    }

    private fun canUseBacktickIdentifier(name: String): Boolean {
        return name.none { it == '`' || it == '\n' || it == '\r' || it == '.' || it == ';' || it == '[' || it == ']' || it == '/' || it == '<' || it == '>' || it == ':' || it == '\\' }
    }

    private fun String.toKotlinStringLiteral(): String = buildString {
        append('"')
        this@toKotlinStringLiteral.forEach { ch ->
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

    private fun validateBacktickIdentifier(entry: IdDefEntry) {
        if (!canUseBacktickIdentifier(entry.name)) {
            error(
                "Cannot generate IdDefConstants: ID=${entry.id}, name=${entry.name}, " +
                        "line=${entry.lineNumber}, reason=name cannot be used inside a Kotlin backtick identifier"
            )
        }
    }
}
