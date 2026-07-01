package com.kazumaproject.mozc.zeroquery

import java.io.ByteArrayOutputStream
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path

object SerializedStringArrayWriter {
    fun write(strings: List<String>, output: Path) {
        Files.createDirectories(output.parent)
        Files.write(output, toByteArray(strings))
    }

    fun toByteArray(strings: List<String>): ByteArray {
        requireSortedUnique(strings)

        val encodedStrings = strings.map { it.toByteArray(StandardCharsets.UTF_8) }
        val tableSize = 4L + 8L * encodedStrings.size
        require(tableSize <= UInt.MAX_VALUE.toLong()) {
            "SerializedStringArray table is too large: array_size=${encodedStrings.size}"
        }

        val offsets = mutableListOf<Long>()
        val lengths = mutableListOf<Int>()
        var offset = tableSize
        val stringBytes = ByteArrayOutputStream()
        encodedStrings.forEach { bytes ->
            offsets += offset
            lengths += bytes.size
            stringBytes.write(bytes)
            stringBytes.write(0)
            offset += bytes.size.toLong() + 1L
            require(offset <= UInt.MAX_VALUE.toLong() + 1L) {
                "SerializedStringArray string block is too large"
            }
        }

        return ByteArrayOutputStream().use { output ->
            output.writeUInt32LE(strings.size.toLong())
            offsets.indices.forEach { index ->
                output.writeUInt32LE(offsets[index])
                output.writeUInt32LE(lengths[index].toLong())
            }
            output.write(stringBytes.toByteArray())
            output.toByteArray()
        }
    }

    private fun requireSortedUnique(strings: List<String>) {
        for (index in 1 until strings.size) {
            val previous = strings[index - 1]
            val current = strings[index]
            val comparison = UnicodeCodePointStringComparator.compare(previous, current)
            require(comparison < 0) {
                "SerializedStringArray strings must be sorted unique: index=$index, previous='$previous', current='$current'"
            }
        }
    }
}

internal fun ByteArrayOutputStream.writeUInt32LE(value: Long) {
    require(value in 0..UInt.MAX_VALUE.toLong()) { "uint32 value out of range: value=$value" }
    write((value and 0xff).toInt())
    write(((value ushr 8) and 0xff).toInt())
    write(((value ushr 16) and 0xff).toInt())
    write(((value ushr 24) and 0xff).toInt())
}

internal fun ByteArrayOutputStream.writeUInt16LE(value: Int) {
    require(value in 0..UShort.MAX_VALUE.toInt()) { "uint16 value out of range: value=$value" }
    write(value and 0xff)
    write((value ushr 8) and 0xff)
}

internal fun ByteArray.readUInt32LE(offset: Int): Long {
    require(offset >= 0 && offset + 4 <= size) { "uint32 read out of range: offset=$offset, file size=$size" }
    return (this[offset].toLong() and 0xffL) or
            ((this[offset + 1].toLong() and 0xffL) shl 8) or
            ((this[offset + 2].toLong() and 0xffL) shl 16) or
            ((this[offset + 3].toLong() and 0xffL) shl 24)
}

internal fun ByteArray.readUInt16LE(offset: Int): Int {
    require(offset >= 0 && offset + 2 <= size) { "uint16 read out of range: offset=$offset, file size=$size" }
    return (this[offset].toInt() and 0xff) or ((this[offset + 1].toInt() and 0xff) shl 8)
}
