package com.kazumaproject.stream

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.FileInputStream
import java.io.FileOutputStream

object ArraysStream {
    fun writeShortArray(
        fileOutputStream: FileOutputStream,
        shortArray: ShortArray
    ) {
        DataOutputStream(BufferedOutputStream(fileOutputStream)).use { bos ->
            println("write ${shortArray.size}")
            bos.writeInt(shortArray.size)
            shortArray.forEach {
                bos.writeShort(it.toInt())
            }
        }
    }

    fun writeCharArray(
        fileOutputStream: FileOutputStream,
        charArray: CharArray
    ) {
        BufferedOutputStream(fileOutputStream).use { bos ->
            bos.write(charArray.size)
            charArray.forEach { bos.write(it.code) }
        }
    }

    fun writeIntArray(
        fileOutputStream: FileOutputStream,
        intArray: IntArray
    ) {
        BufferedOutputStream(fileOutputStream).use { bos ->
            bos.write(intArray.size)
            intArray.forEach { bos.write(it) }
        }
    }

    fun writeBooleanArray(
        fileOutputStream: FileOutputStream,
        boolArray: BooleanArray
    ) {
        BufferedOutputStream(fileOutputStream).use { bos ->
            bos.write(boolArray.size)
            boolArray.forEach { bos.write(if (it) 1 else 0) }
        }
    }

    fun readShortArray(
        fileInputStream: FileInputStream
    ): ShortArray {
        DataInputStream(BufferedInputStream(fileInputStream)).use { bis ->
            val shortArraySize = bis.readInt()
            println("read: $shortArraySize")
            return ShortArray(shortArraySize) { bis.readShort() }
        }
    }

    fun readCharArray(fileInputStream: FileInputStream): CharArray {
        BufferedInputStream(fileInputStream).use { bis ->
            val charArraySize = bis.read()
            return CharArray(charArraySize) { bis.read().toChar() }
        }
    }

    fun readIntArray(fileInputStream: FileInputStream): IntArray {
        BufferedInputStream(fileInputStream).use { bis ->
            val intArraySize = bis.read()
            return IntArray(intArraySize) { bis.read() }
        }
    }

    fun readBooleanArray(fileInputStream: FileInputStream): BooleanArray {
        BufferedInputStream(fileInputStream).use { bis ->
            val boolArraySize = bis.read()
            return BooleanArray(boolArraySize) { bis.read() != 0 }
        }
    }
}