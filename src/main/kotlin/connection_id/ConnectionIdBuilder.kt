package com.kazumaproject.connection_id

import com.kazumaproject.byteArrayToShortList
import com.kazumaproject.stream.ArraysStream
import com.kazumaproject.toByteArrayFromListShort
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.ObjectInput
import java.io.ObjectOutput

class ConnectionIdBuilder {
    fun build(
        out: ObjectOutput,
        value: List<Short>
    ){
        try {
            out.apply {
                writeObject(value.toShortArray())
                flush()
                close()
            }
        }catch (e: Exception){
            println(e.message)
        }
    }

    fun read(objectInput: ObjectInput): List<Short>{
        try {
            objectInput.apply {
                val a = (readObject() as ShortArray)
                close()
                return a.toList()
            }
        }catch (e: Exception){
            println(e.message)
            return emptyList()
        }
    }

    fun buildWithShortArray(
        fileOutputStream: FileOutputStream,
        value: List<Short>,
    ){
        ArraysStream.writeShortArray(
            fileOutputStream,
            value.toShortArray()
        )
    }

    fun readWithShortArray(
        fileInputStream: FileInputStream
    ): ShortArray{
        return ArraysStream.readShortArray(fileInputStream)
    }

}