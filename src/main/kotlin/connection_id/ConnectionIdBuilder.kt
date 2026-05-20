package com.kazumaproject.connection_id

import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.mozc.ConnectionMatrixIO
import java.io.*
import java.nio.ByteBuffer
import java.nio.file.Path

class ConnectionIdBuilder {
    fun build(
        out: ObjectOutput,
        value: List<Short>
    ) {
        try {
            out.apply {
                writeObject(value.toShortArray())
                flush()
                close()
            }
        } catch (e: Exception) {
            println(e.message)
        }
    }

    fun read(inputStream: InputStream): ShortArray {
        return readMatrix(inputStream).costs
    }

    fun readMatrix(inputStream: InputStream, filePath: String = "<stream>"): ConnectionMatrix {
        return ConnectionMatrixIO.read(inputStream, filePath)
    }

    fun writeShortArrayAsBytes(shortArray: ShortArray, fileName: String) {
        val byteBuffer = ByteBuffer.allocate(shortArray.size * 2)
        shortArray.forEach { byteBuffer.putShort(it) }
        FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
    }

    fun writeMatrixAsBytes(connectionMatrix: ConnectionMatrix, fileName: String) {
        ConnectionMatrixIO.writeRaw(connectionMatrix, Path.of(fileName))
    }


    fun readShortArrayFromBytes(fileName: String): ShortArray {
        val file = FileInputStream(fileName)
        val byteArray = file.readBytes()
        val byteBuffer = ByteBuffer.wrap(byteArray)
        val shortArray = ShortArray(byteArray.size / 2)
        byteBuffer.asShortBuffer().get(shortArray)
        return shortArray
    }

    fun writeBitSet(shortArray: ShortArray, fileName: String) {
        val byteBuffer = ByteBuffer.allocate(shortArray.size * 2)
        shortArray.forEach { byteBuffer.putShort(it) }
        FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
    }


    fun readBitSet(fileName: String): ShortArray {
        val file = FileInputStream(fileName)
        val byteArray = file.readBytes()
        val byteBuffer = ByteBuffer.wrap(byteArray)
        val shortArray = ShortArray(byteArray.size / 2)
        byteBuffer.asShortBuffer().get(shortArray)
        return shortArray
    }

}
