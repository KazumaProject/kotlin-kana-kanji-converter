package com.kazumaproject.mozc.zeroquery

import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path

object SerializedStringArrayReader {
    fun read(path: Path): List<String> = read(Files.readAllBytes(path), path.toString())

    fun read(bytes: ByteArray, filePath: String = "<bytes>"): List<String> {
        if (bytes.size < 4) {
            error("Invalid SerializedStringArray: file path=$filePath, file size=${bytes.size}, reason=file size must be at least 4")
        }

        val arraySize = bytes.readUInt32LE(0)
        val tableEnd = 4L + 8L * arraySize
        if (arraySize > Int.MAX_VALUE || tableEnd > bytes.size.toLong()) {
            error(
                "Invalid SerializedStringArray: file path=$filePath, array_size=$arraySize, " +
                        "file size=${bytes.size}, reason=offset/length table is outside file"
            )
        }

        val dataStart = tableEnd
        val strings = ArrayList<String>(arraySize.toInt())
        repeat(arraySize.toInt()) { index ->
            val tableOffset = 4 + index * 8
            val offset = bytes.readUInt32LE(tableOffset)
            val length = bytes.readUInt32LE(tableOffset + 4)
            val end = offset + length
            if (offset < dataStart) {
                failInvalidRange(filePath, index, offset, length, bytes.size, "offset points inside offset/length table")
            }
            if (end > bytes.size.toLong()) {
                failInvalidRange(filePath, index, offset, length, bytes.size, "offset + length is outside file")
            }
            if (end >= bytes.size.toLong() || bytes[end.toInt()] != 0.toByte()) {
                failInvalidRange(filePath, index, offset, length, bytes.size, "missing null terminator")
            }
            if (offset > Int.MAX_VALUE || length > Int.MAX_VALUE) {
                failInvalidRange(filePath, index, offset, length, bytes.size, "offset/length is too large")
            }

            val decoded = decodeUtf8(bytes, offset.toInt(), length.toInt(), filePath, index)
            strings += decoded
        }

        for (index in 1 until strings.size) {
            val previous = strings[index - 1]
            val current = strings[index]
            if (UnicodeCodePointStringComparator.compare(previous, current) >= 0) {
                error(
                    "Invalid SerializedStringArray: file path=$filePath, index=$index, " +
                            "previous='$previous', current='$current', reason=strings are not sorted unique"
                )
            }
        }
        return strings
    }

    private fun decodeUtf8(bytes: ByteArray, offset: Int, length: Int, filePath: String, index: Int): String {
        val decoder = StandardCharsets.UTF_8.newDecoder()
            .onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
        return try {
            decoder.decode(ByteBuffer.wrap(bytes, offset, length)).toString()
        } catch (exception: Exception) {
            error(
                "Invalid SerializedStringArray: file path=$filePath, index=$index, " +
                        "reason=UTF-8 decode failed: ${exception.message}"
            )
        }
    }

    private fun failInvalidRange(
        filePath: String,
        index: Int,
        offset: Long,
        length: Long,
        fileSize: Int,
        reason: String,
    ): Nothing {
        error(
            "Invalid SerializedStringArray: file path=$filePath, index=$index, " +
                    "offset=$offset, length=$length, file size=$fileSize, reason=$reason"
        )
    }
}
