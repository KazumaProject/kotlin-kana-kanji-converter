package com.kazumaproject

import com.kazumaproject.bitset.rank0
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.*
import kotlin.time.measureTime

fun List<Boolean>.toBitSet(): BitSet {
    val bitSet = BitSet(this.size)
    this.forEachIndexed { index, value ->
        if (value) {
            bitSet.set(index,true)
        }
    }
    return bitSet
}

fun String.hiraToKata() =
    this.map {
        if (it.code in 0x3041..0x3093) {
            it + 0x60
        } else {
            it
        }
    }.joinToString("")

fun List<Char>.toByteArrayFromListChar(): ByteArray {
    return this.map { it.code }.toByteArray()
}

fun ByteArray.toListChar(): MutableList<Char> {
    return this.toListInt().map { it.toChar() }.toMutableList()
}

fun List<Int>.toByteArray(): ByteArray {
    val buffer = ByteBuffer.allocate(this.size * 4) // Each Int occupies 4 bytes
    this.forEach { buffer.putInt(it) }
    return buffer.array()
}

fun ByteArray.toListInt(): List<Int> {
    val intList = mutableListOf<Int>()
    for (i in indices step 4) {
        val value = (this[i].toInt() shl 24) or
                ((this[i + 1].toInt() and 0xFF) shl 16) or
                ((this[i + 2].toInt() and 0xFF) shl 8) or
                (this[i + 3].toInt() and 0xFF)
        intList.add(value)
    }
    return intList
}

fun List<Short>.toByteArrayFromListShort(): ByteArray {
    val byteArray = ByteArray(this.size * 2) // Each Short occupies 2 bytes
    for (i in this.indices) {
        val shortValue = this[i]
        byteArray[i * 2] = (shortValue.toInt() shr 8).toByte() // High byte
        byteArray[i * 2 + 1] = shortValue.toByte() // Low byte
    }
    return byteArray
}

fun ByteArray.byteArrayToShortList(): List<Short> {
    val shortList = mutableListOf<Short>()
    for (i in indices step 2) {
        val highByte = this[i].toInt() and 0xFF
        val lowByte = this[i + 1].toInt() and 0xFF
        val shortValue = (highByte shl 8) or lowByte
        shortList.add(shortValue.toShort())
    }
    return shortList
}

fun  BitSet.toBooleanList():List<Boolean>{
    return (0 until this.size()).map { this[it] }
}

fun ByteArray.toBitSet(): BitSet {
    val returnValue = BitSet(this.size * 8)
    val byteBuffer = ByteBuffer.wrap(this)

    for (i in indices) {
        val thebyte = byteBuffer.get(i)
        for (j in 0 until 8) {
            returnValue.set(i * 8 + j, isBitSet(thebyte, j))
        }
    }
    return returnValue
}

private fun isBitSet(b: Byte, bit: Int): Boolean {
    return (b.toInt() and (1 shl bit)) != 0
}

fun List<Int>.toBitSetExtension(): BitSet {
    val bitSet = BitSet()
    this.forEach { bitSet.set(it) }
    return bitSet
}

fun BitSet.toIntListExtension(): List<Int> {
    val intList = mutableListOf<Int>()
    for (index in 0 until this.size()) {
        if (this.get(index)) {
            intList.add(index)
        }
    }
    return intList
}

fun List<Int>.compressListInt(): List<Short>{
    val diffList: MutableList<Short> = mutableListOf()
    this.forEachIndexed { index, i ->
        if ((index + 1) != i ){
            diffList.add((i - index).toShort())
        }else{
           diffList.add(0)
        }
    }
    println("${diffList.size}")
    return diffList
}

fun List<Int>.writeToTxt(fileName: String){
    File("./src/main/resources/$fileName").bufferedWriter().use { out ->
        out.write(this.toString())
    }
}

fun BitSet.toBooleanArray(): BooleanArray {
    return BooleanArray(this.length()) { this[it] }
}

fun BooleanArray.boolArrayToBitSet(): BitSet {
    val bitSet = BitSet(this.size)
    this.forEachIndexed { index, value ->
        if (value) {
            bitSet.set(index)
        }
    }
    return bitSet
}

fun ByteArray.toShortArray(): ShortArray {
    val shortBuffer = ByteBuffer.wrap(this).order(ByteOrder.BIG_ENDIAN).asShortBuffer()
    val shortArray = ShortArray(shortBuffer.remaining())
    shortBuffer.get(shortArray)
    return shortArray
}

fun ShortArray.toByteArray(): ByteArray {
    val byteBuffer = ByteBuffer.allocate(this.size * 2).order(ByteOrder.BIG_ENDIAN)
    for (short in this) {
        byteBuffer.putShort(short)
    }
    return byteBuffer.array()
}

fun IntArray.toByteArray(): ByteArray {
    val byteBuffer = ByteBuffer.allocate(this.size * 4).order(ByteOrder.BIG_ENDIAN)
    for (int in this) {
        byteBuffer.putInt(int)
    }
    return byteBuffer.array()
}

fun CharArray.toByteArray(): ByteArray {
    val byteBuffer = ByteBuffer.allocate(this.size * 2).order(ByteOrder.BIG_ENDIAN)
    for (char in this) {
        byteBuffer.putChar(char)
    }
    return byteBuffer.array()
}

fun BooleanArray.toByteArray(): ByteArray {
    val byteArray = ByteArray(this.size)
    for (i in this.indices) {
        byteArray[i] = if (this[i]) 1.toByte() else 0.toByte()
    }
    return byteArray
}

fun writeIntArrayAsBytes(intArray: IntArray, fileName: String) {
    val byteBuffer = ByteBuffer.allocate(intArray.size * 4)
    intArray.forEach { byteBuffer.putInt(it) }
    FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
}


fun readIntArrayFromBytes(fileName: String): IntArray {
    val file = FileInputStream(fileName)
    val byteArray = file.readBytes()
    val byteBuffer = ByteBuffer.wrap(byteArray)
    val intArray = IntArray(byteArray.size / 4)
    byteBuffer.asIntBuffer().get(intArray)
    return intArray
}

fun writeCharArrayAsBytes(charArray: CharArray, fileName: String) {
    val byteBuffer = ByteBuffer.allocate(charArray.size * 2)
    charArray.forEach { byteBuffer.putChar(it) }
    FileOutputStream(fileName).use { it.write(byteBuffer.array()) }
}


fun readCharArrayFromBytes(fileName: String): CharArray {
    val file = FileInputStream(fileName)
    val byteArray = file.readBytes()
    val byteBuffer = ByteBuffer.wrap(byteArray)
    val charArray = CharArray(byteArray.size / 2)
    byteBuffer.asCharBuffer().get(charArray)
    return charArray
}
