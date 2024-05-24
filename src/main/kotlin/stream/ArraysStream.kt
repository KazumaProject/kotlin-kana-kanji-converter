package com.kazumaproject.stream

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.boolArrayToBitSet
import java.io.ByteArrayOutputStream
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.CharBuffer
import java.nio.charset.StandardCharsets

object ArraysStream {

    fun writeLOUDS(
        LBS: BooleanArray,
        isLeaf: BooleanArray,
        labels: CharArray,
        fileName: String
    ){
        val booleanArray1Size = LBS.size
        val booleanArray2Size = isLeaf.size
        val charArraySize = labels.size

        val totalSize = 4 + booleanArray1Size + 4 + booleanArray2Size + 4 + charArraySize * 2
        val byteBuffer = ByteBuffer.allocate(totalSize)

        byteBuffer.putInt(booleanArray1Size)
        byteBuffer.putInt(booleanArray2Size)
        byteBuffer.putInt(charArraySize)

        LBS.forEach { byteBuffer.put(if (it) 1.toByte() else 0.toByte()) }
        isLeaf.forEach { byteBuffer.put(if (it) 1.toByte() else 0.toByte()) }
        labels.forEach { byteBuffer.putChar(it) }
        FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
    }

    fun readLOUDS(
        fileName: String,
    ): LOUDS{
        val byteArray = FileInputStream(fileName).use { it.readBytes() }
        val byteBuffer = ByteBuffer.wrap(byteArray)

        val booleanArray1Size = byteBuffer.int
        val booleanArray2Size = byteBuffer.int
        val charArraySize = byteBuffer.int

        val LBS = BooleanArray(booleanArray1Size) { byteBuffer.get().toInt() != 0 }
        val isLeaf = BooleanArray(booleanArray2Size) { byteBuffer.get().toInt() != 0 }
        val labels = CharArray(charArraySize) { byteBuffer.char }
        return LOUDS(
            LBS.boolArrayToBitSet(),
            labels.toMutableList(),
            isLeaf.boolArrayToBitSet()
        )
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

    fun writeCharArrayAsBytes(charArray: CharArray, outputStream: OutputStream) {
        val byteArray = StandardCharsets.UTF_8.encode(CharBuffer.wrap(charArray)).array()
        outputStream.use { it.write(byteArray) }
    }

    fun readCharArrayFromBytes(inputStream: InputStream): CharArray {
        val byteArray = inputStream.use { it.readBytes() }
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