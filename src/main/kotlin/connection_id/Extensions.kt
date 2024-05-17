package com.kazumaproject.connection_id

import org.xerial.snappy.Snappy
import java.util.zip.Deflater
import java.util.zip.Inflater

fun ByteArray.deflate(): ByteArray{
    val rawData: ByteArray = this
    val compressedData = ByteArray(rawData.size)
    val compressor = Deflater(Deflater.BEST_SPEED)
    compressor.apply {
        setInput(rawData)
        finish()
    }
    val compressedDataLength = compressor.deflate(compressedData)
    return compressedData.copyOfRange(0, compressedDataLength)
}

fun ByteArray.inflate(size: Int): ByteArray{
    val compressedData: ByteArray = this
    val originalData = ByteArray(size)
    val inflater = Inflater()
    inflater.apply {
        setInput(compressedData)
        finished()
    }
    val originalDataLength = inflater.inflate(originalData)
    return originalData.copyOfRange(0, originalDataLength)
}

fun ByteArray.deflateSnappy(): ByteArray{
    val rawData: ByteArray = this
    val compressed = Snappy.compress(rawData)
    return compressed
}

fun ByteArray.inflateSnappy(): ByteArray{
    return Snappy.uncompress(this)
}