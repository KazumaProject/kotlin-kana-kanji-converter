package com.kazumaproject.mozc

import java.io.BufferedInputStream
import java.io.BufferedReader
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.Path
import kotlin.math.sqrt

data class ConnectionMatrix(
    val size: Int,
    val costs: ShortArray,
) {
    fun getCost(leftId: Short, rightId: Short): Int = getCost(leftId.toInt(), rightId.toInt())

    fun getCost(leftId: Int, rightId: Int): Int {
        require(leftId >= 0 && rightId >= 0) {
            "Connection ID out of range: leftId=$leftId, rightId=$rightId, size=$size"
        }
        require(leftId < size && rightId < size) {
            "Connection ID out of range: leftId=$leftId, rightId=$rightId, size=$size"
        }
        return costs[leftId * size + rightId].toInt()
    }

    override fun equals(other: Any?): Boolean =
        other is ConnectionMatrix && size == other.size && costs.contentEquals(other.costs)

    override fun hashCode(): Int = 31 * size + costs.contentHashCode()
}

object ConnectionMatrixParser {
    fun parse(path: Path): ConnectionMatrix =
        Files.newBufferedReader(path).use { reader ->
            parse(reader, path.toString())
        }

    fun parse(reader: BufferedReader, filePath: String): ConnectionMatrix {
        val iterator = reader.lineSequence().iterator()
        if (!iterator.hasNext()) {
            error("connection matrix is empty: file path=$filePath")
        }

        val firstLine = iterator.next()
        val matrixSize = firstLine.toIntOrNull()
            ?: error("Invalid connection matrix size: file path=$filePath, line number=1, value='$firstLine'")
        require(matrixSize > 0) {
            "Invalid connection matrix size: file path=$filePath, line number=1, value='$firstLine', reason=size must be positive"
        }

        val expectedCountLong = matrixSize.toLong() * matrixSize.toLong()
        require(expectedCountLong <= Int.MAX_VALUE) {
            "Connection matrix is too large: file path=$filePath, matrixSize=$matrixSize, expected count=$expectedCountLong"
        }

        val expectedCount = expectedCountLong.toInt()
        val costs = ShortArray(expectedCount)
        var actualCount = 0
        var lineNumber = 1
        while (iterator.hasNext()) {
            val rawLine = iterator.next()
            lineNumber += 1
            val value = rawLine.toIntOrNull()
                ?: error("Invalid connection matrix cost: file path=$filePath, line number=$lineNumber, value='$rawLine'")
            if (value !in Short.MIN_VALUE..Short.MAX_VALUE) {
                error("Invalid connection matrix cost: file path=$filePath, line number=$lineNumber, value='$rawLine', reason=outside Short range")
            }
            if (actualCount < expectedCount) {
                costs[actualCount] = value.toShort()
            }
            actualCount += 1
        }

        if (actualCount != expectedCount) {
            error(
                "Connection matrix count mismatch: file path=$filePath, matrixSize=$matrixSize, " +
                        "expected count=$expectedCount, actual count=$actualCount"
            )
        }

        return ConnectionMatrix(matrixSize, costs)
    }
}

object ConnectionMatrixIO {
    fun writeRaw(matrix: ConnectionMatrix, path: Path) {
        Files.createDirectories(path.parent)
        val byteBuffer = ByteBuffer.allocate(matrix.costs.size * Short.SIZE_BYTES)
        matrix.costs.forEach(byteBuffer::putShort)
        Files.write(path, byteBuffer.array())
    }

    fun read(path: Path): ConnectionMatrix =
        Files.newInputStream(path).use { input ->
            read(input, path.toString(), Files.size(path))
        }

    fun read(inputStream: InputStream, filePath: String = "<stream>", fileSizeBytes: Long? = null): ConnectionMatrix {
        val bytes = BufferedInputStream(inputStream).readBytes()
        val actualFileSizeBytes = fileSizeBytes ?: bytes.size.toLong()
        if (bytes.size % Short.SIZE_BYTES != 0) {
            error(
                "Invalid raw connectionId.dat size: file path=$filePath, file size bytes=$actualFileSizeBytes, " +
                        "short count=${bytes.size / Short.SIZE_BYTES}, reason=file size must be divisible by 2"
            )
        }

        val shortCount = bytes.size / Short.SIZE_BYTES
        val matrixSize = sqrt(shortCount.toDouble()).toInt()
        if (matrixSize * matrixSize != shortCount) {
            error(
                "Invalid raw connectionId.dat size: file path=$filePath, file size bytes=$actualFileSizeBytes, " +
                        "short count=$shortCount, reason=short count must be a perfect square"
            )
        }

        val costs = ShortArray(shortCount)
        ByteBuffer.wrap(bytes).asShortBuffer().get(costs)
        return ConnectionMatrix(matrixSize, costs)
    }
}
