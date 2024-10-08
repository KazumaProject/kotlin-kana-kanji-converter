package com.kazumaproject.connection_id

import java.io.*
import java.nio.ByteBuffer

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
        val byteArray = inputStream.readBytes()
        val byteBuffer = ByteBuffer.wrap(byteArray)
        val shortArray = ShortArray(byteArray.size / 2)
        byteBuffer.asShortBuffer().get(shortArray)
        return shortArray
    }

    fun writeShortArrayAsBytes(shortArray: ShortArray, fileName: String) {
        val byteBuffer = ByteBuffer.allocate(shortArray.size * 2)
        shortArray.forEach { byteBuffer.putShort(it) }
        FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
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
        val a = shortArray.map { Integer.toBinaryString(it.toInt()) }.map { it == "1" }.toBooleanArray()
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