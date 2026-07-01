package com.kazumaproject.mozc.zeroquery

import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.nio.file.Path

data class ZeroQueryBinaryData(
    val tokenBytes: ByteArray,
    val stringBytes: ByteArray,
    val strings: List<String>,
) {
    val tokenCount: Int get() = tokenBytes.size / ZeroQueryBinaryWriter.TokenEntrySize
}

object ZeroQueryBinaryWriter {
    const val TokenEntrySize: Int = 16

    fun write(entriesByKey: Map<String, List<ZeroQueryEntry>>, tokenOutput: Path, stringOutput: Path): ZeroQueryBinaryData {
        val binary = toBinary(entriesByKey)
        Files.createDirectories(tokenOutput.parent)
        Files.write(tokenOutput, binary.tokenBytes)
        Files.createDirectories(stringOutput.parent)
        Files.write(stringOutput, binary.stringBytes)
        return binary
    }

    fun toBinary(entriesByKey: Map<String, List<ZeroQueryEntry>>): ZeroQueryBinaryData {
        val sortedStrings = buildSortedStringArray(entriesByKey)
        val stringIndex = sortedStrings.withIndex().associate { it.value to it.index }
        val tokenBytes = ByteArrayOutputStream()
        entriesByKey.keys.sortedWith(UnicodeCodePointStringComparator).forEach { key ->
            val keyIndex = stringIndex.getValue(key)
            entriesByKey.getValue(key).forEach { entry ->
                require(entry.key == key) {
                    "Zero query entry key does not match map key: map key='$key', entry key='${entry.key}'"
                }
                tokenBytes.writeUInt32LE(keyIndex.toLong())
                tokenBytes.writeUInt32LE(stringIndex.getValue(entry.value).toLong())
                tokenBytes.writeUInt16LE(entry.type.code)
                tokenBytes.writeUInt16LE(0)
                tokenBytes.writeUInt32LE(0)
            }
        }

        return ZeroQueryBinaryData(
            tokenBytes = tokenBytes.toByteArray(),
            stringBytes = SerializedStringArrayWriter.toByteArray(sortedStrings),
            strings = sortedStrings,
        )
    }

    fun writeAuditTsv(entriesByKey: Map<String, List<ZeroQueryEntry>>, output: Path) {
        Files.createDirectories(output.parent)
        Files.newBufferedWriter(output).use { writer ->
            entriesByKey.keys.sortedWith(UnicodeCodePointStringComparator).forEach { key ->
                entriesByKey.getValue(key).forEach { entry ->
                    writer.append(key)
                    writer.append('\t')
                    writer.append(entry.value)
                    writer.newLine()
                }
            }
        }
    }

    private fun buildSortedStringArray(entriesByKey: Map<String, List<ZeroQueryEntry>>): List<String> {
        val strings = HashSet<String>()
        entriesByKey.forEach { (key, entries) ->
            strings += key
            entries.forEach { entry ->
                strings += entry.value
            }
        }
        return strings.sortedWith(UnicodeCodePointStringComparator)
    }
}
