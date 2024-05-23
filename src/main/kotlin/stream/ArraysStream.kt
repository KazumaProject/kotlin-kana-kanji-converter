package com.kazumaproject.stream

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.CharBuffer
import java.nio.charset.StandardCharsets

object ArraysStream {
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

    fun writeIntArrayAsBytes(intArray: IntArray, fileName: String) {
        val byteBuffer = ByteBuffer.allocate(intArray.size * 4)
        intArray.forEach { byteBuffer.putInt(it) }
        FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
    }

    fun readIntArrayFromBytes(fileName: String): IntArray {
        val byteArray = FileInputStream(fileName).use { it.readBytes() }
        val byteBuffer = ByteBuffer.wrap(byteArray)
        val intArray = IntArray(byteArray.size / 4)
        byteBuffer.asIntBuffer().get(intArray)
        return intArray
    }

    fun writeCharArrayAsBytes(charArray: CharArray, fileName: String) {
        val byteArray = StandardCharsets.UTF_8.encode(CharBuffer.wrap(charArray)).array()
        FileOutputStream(fileName).use { it.write(byteArray) }
    }

    fun readCharArrayFromBytes(fileName: String): CharArray {
        val byteArray = FileInputStream(fileName).use { it.readBytes() }
        val charBuffer = StandardCharsets.UTF_8.decode(ByteBuffer.wrap(byteArray))
        return charBuffer.array()
    }

    fun writeBooleanArrayAsBytes(booleanArray: BooleanArray, fileName: String) {
        val byteBuffer = ByteBuffer.allocate(booleanArray.size)
        booleanArray.forEach { byteBuffer.put(if (it) 1.toByte() else 0.toByte()) }
        FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
    }

    fun readBooleanArrayFromBytes(fileName: String): BooleanArray {
        val byteArray = FileInputStream(fileName).use { it.readBytes() }
        val booleanArray = BooleanArray(byteArray.size) { byteArray[it].toInt() != 0 }
        return booleanArray
    }

}