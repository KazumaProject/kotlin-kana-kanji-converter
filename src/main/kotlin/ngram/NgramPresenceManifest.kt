package com.kazumaproject.ngram

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.createDirectories

data class NgramOrderManifest(
    val order: Int,
    val entryCount: Int,
    val bdzVertexCount: Int,
    val bdzRetryCount: Int,
    val binaryByteSize: Long,
)

data class NgramPresenceManifest(
    val format: String,
    val version: Int,
    val keyMode: String,
    val sourceFiles: List<String>,
    val sourceRowCount: Int,
    val resolvedRuleCount: Int,
    val unresolvedRuleCount: Int,
    val duplicateCount: Int,
    val skippedCount: Int,
    val orders: List<NgramOrderManifest>,
    val dictionaryBuildId: String,
    val contentChecksum: String,
    val unresolvedRuleSamples: List<UnresolvedNgramRule>,
)

object NgramPresenceManifestWriter {
    fun write(outputPath: Path, manifest: NgramPresenceManifest) {
        outputPath.parent?.createDirectories()
        Files.writeString(outputPath, toJson(manifest), StandardCharsets.UTF_8)
    }

    fun toJson(manifest: NgramPresenceManifest): String = buildString {
        appendLine("{")
        field("format", manifest.format, comma = true)
        field("version", manifest.version, comma = true)
        field("keyMode", manifest.keyMode, comma = true)
        arrayField("sourceFiles", manifest.sourceFiles, comma = true)
        field("sourceRowCount", manifest.sourceRowCount, comma = true)
        field("resolvedRuleCount", manifest.resolvedRuleCount, comma = true)
        field("unresolvedRuleCount", manifest.unresolvedRuleCount, comma = true)
        field("duplicateCount", manifest.duplicateCount, comma = true)
        field("skippedCount", manifest.skippedCount, comma = true)
        appendLine("  \"orders\": [")
        manifest.orders.forEachIndexed { index, order ->
            appendLine("    {")
            appendLine("      \"order\": ${order.order},")
            appendLine("      \"entryCount\": ${order.entryCount},")
            appendLine("      \"bdzVertexCount\": ${order.bdzVertexCount},")
            appendLine("      \"bdzRetryCount\": ${order.bdzRetryCount},")
            appendLine("      \"binaryByteSize\": ${order.binaryByteSize}")
            append("    }")
            if (index != manifest.orders.lastIndex) append(',')
            appendLine()
        }
        appendLine("  ],")
        field("dictionaryBuildId", manifest.dictionaryBuildId, comma = true)
        field("contentChecksum", manifest.contentChecksum, comma = true)
        appendLine("  \"unresolvedRuleSamples\": [")
        manifest.unresolvedRuleSamples.forEachIndexed { index, sample ->
            appendLine("    {")
            appendLine("      \"order\": ${sample.order},")
            appendLine("      \"reading\": ${jsonString(sample.reading)},")
            appendLine("      \"surfaces\": [${sample.surfaces.joinToString(", ") { jsonString(it) }}],")
            appendLine("      \"sourceFile\": ${jsonString(sample.sourceFile)},")
            appendLine("      \"lineNumber\": ${sample.lineNumber},")
            appendLine("      \"reason\": ${jsonString(sample.reason)}")
            append("    }")
            if (index != manifest.unresolvedRuleSamples.lastIndex) append(',')
            appendLine()
        }
        appendLine("  ]")
        appendLine("}")
    }

    private fun StringBuilder.field(name: String, value: String, comma: Boolean) {
        append("  ")
        append(jsonString(name))
        append(": ")
        append(jsonString(value))
        if (comma) append(',')
        appendLine()
    }

    private fun StringBuilder.field(name: String, value: Int, comma: Boolean) {
        append("  ")
        append(jsonString(name))
        append(": ")
        append(value)
        if (comma) append(',')
        appendLine()
    }

    private fun StringBuilder.arrayField(name: String, values: List<String>, comma: Boolean) {
        append("  ")
        append(jsonString(name))
        append(": [")
        append(values.joinToString(", ") { jsonString(it) })
        append(']')
        if (comma) append(',')
        appendLine()
    }

    private fun jsonString(value: String): String = buildString {
        append('"')
        value.forEach { ch ->
            when (ch) {
                '\\' -> append("\\\\")
                '"' -> append("\\\"")
                '\b' -> append("\\b")
                '\u000C' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> {
                    if (ch.code < 0x20) {
                        append("\\u")
                        append(ch.code.toString(16).padStart(4, '0'))
                    } else {
                        append(ch)
                    }
                }
            }
        }
        append('"')
    }
}
