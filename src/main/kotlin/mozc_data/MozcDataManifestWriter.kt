package mozc_data

import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

class MozcDataManifestWriter {
    fun create(dataSet: MozcDataSet, sourceBytes: ByteArray): MozcDataManifest {
        val version = dataSet.sections["version"]?.data?.toUtf8String()?.trimEnd('\u0000', '\r', '\n').orEmpty()
        return MozcDataManifest(
            format = MozcDataVersion.FormatName,
            magic = MozcDataVersion.MagicHex,
            engineVersion = version,
            version = version,
            sha1 = dataSet.computedSha1.toHex(),
            sha256 = MessageDigest.getInstance("SHA-256").digest(sourceBytes).toHex(),
            fileSize = dataSet.fileSize,
            sections = dataSet.metadata.entries.map {
                MozcDataManifest.Section(it.name, it.offset, it.size)
            },
        )
    }

    fun write(path: Path, manifest: MozcDataManifest) {
        path.parent?.let(Files::createDirectories)
        Files.writeString(path, toJson(manifest))
    }

    fun toJson(manifest: MozcDataManifest): String = buildString {
        appendLine("{")
        appendLine("  \"format\": ${manifest.format.jsonString()},")
        appendLine("  \"magic\": ${manifest.magic.jsonString()},")
        appendLine("  \"engineVersion\": ${manifest.engineVersion.jsonString()},")
        appendLine("  \"version\": ${manifest.version.jsonString()},")
        appendLine("  \"sha1\": ${manifest.sha1.jsonString()},")
        appendLine("  \"sha256\": ${manifest.sha256.jsonString()},")
        appendLine("  \"fileSize\": ${manifest.fileSize},")
        appendLine("  \"sections\": [")
        manifest.sections.forEachIndexed { index, section ->
            appendLine("    {")
            appendLine("      \"name\": ${section.name.jsonString()},")
            appendLine("      \"offset\": ${section.offset},")
            appendLine("      \"size\": ${section.size}")
            append("    }")
            if (index != manifest.sections.lastIndex) {
                append(',')
            }
            appendLine()
        }
        appendLine("  ]")
        appendLine("}")
    }
}

internal fun ByteBuffer.toUtf8String(): String {
    val copy = asReadOnlyBuffer()
    copy.position(0)
    val bytes = ByteArray(copy.remaining())
    copy.get(bytes)
    return bytes.toString(Charsets.UTF_8)
}

internal fun String.jsonString(): String = buildString {
    append('"')
    this@jsonString.forEach { ch ->
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
                    append("\\u%04X".format(ch.code))
                } else {
                    append(ch)
                }
            }
        }
    }
    append('"')
}
