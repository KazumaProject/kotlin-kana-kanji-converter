package com.kazumaproject.ngram

import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

data class NgramBuildReport(
    val ruleCount: Int,
    val posClassCount: Int,
    val signatureCount: Int,
    val formatVersion: Int = NgramEncoding.VERSION,
    val stateCount: Int = 0,
    val edgeCount: Int = 0,
    val bytes: Int,
    val hashIndexBytes: Int,
    val exactDataBytes: Int,
)

object NgramV3 {
    private const val FNV_OFFSET = -3750763034362895579L
    private const val FNV_PRIME = 1099511628211L
    private const val MIX_1 = -49064778989728563L
    private const val MIX_2 = -4265267296055464877L

    fun hash64(bytes: ByteArray): Long {
        var hash = FNV_OFFSET
        for (byte in bytes) hash = (hash xor (byte.toLong() and 0xffL)) * FNV_PRIME
        hash = (hash xor (hash ushr 33)) * MIX_1
        hash = (hash xor (hash ushr 33)) * MIX_2
        return hash xor (hash ushr 33)
    }

    fun canonicalKey(rule: NgramRule, posIdByName: Map<String, Int>): ByteArray {
        val output = ByteArrayOutputStream()
        val signature = NgramEncoding.signature(rule.features)
        output.write(signature and 0xff)
        output.write((signature ushr 8) and 0xff)
        rule.features.forEach { feature ->
            when (feature) {
                is NgramFeature.Word -> {
                    val utf8 = feature.value.toByteArray(Charsets.UTF_8)
                    writeUVarint(output, utf8.size)
                    output.write(utf8)
                }
                is NgramFeature.Pos -> output.write(requireNotNull(posIdByName[feature.value]))
                NgramFeature.Any -> Unit
            }
        }
        return output.toByteArray()
    }

    fun writeUVarint(output: ByteArrayOutputStream, value: Int) {
        var remaining = value
        while (remaining >= 0x80) {
            output.write((remaining and 0x7f) or 0x80)
            remaining = remaining ushr 7
        }
        output.write(remaining)
    }

    fun compareUnsigned(left: ByteArray, right: ByteArray): Int {
        val common = minOf(left.size, right.size)
        for (index in 0 until common) {
            val comparison = (left[index].toInt() and 0xff).compareTo(right[index].toInt() and 0xff)
            if (comparison != 0) return comparison
        }
        return left.size.compareTo(right.size)
    }

    fun commonPrefix(left: ByteArray, right: ByteArray): Int {
        val limit = minOf(left.size, right.size)
        var index = 0
        while (index < limit && left[index] == right[index]) index++
        return index
    }
}

object SystemNgramBinaryBuilder {
    private data class HashEntry(val remainder: Long, val recordId: Int)

    fun build(
        rules: List<NgramRule>,
        idDef: File,
        output: File,
        formatVersion: Int = NgramEncoding.VERSION,
    ): NgramBuildReport {
        validateRules(rules, formatVersion)
        val contextNames = parseIdDef(idDef)
        val posNames = contextNames.map { it.substringBefore(',') }.distinct().sorted()
        require(posNames.size < 256) { "Too many coarse POS classes: ${posNames.size}" }
        val posIdByName = posNames.withIndex().associate { (index, name) -> name to index + 1 }
        rules.flatMap { it.features }.filterIsInstance<NgramFeature.Pos>().forEach {
            require(posIdByName.containsKey(it.value)) { "Unknown coarse POS '${it.value}'" }
        }
        val contextClasses = ByteArray(contextNames.size) { index ->
            requireNotNull(posIdByName[contextNames[index].substringBefore(',')]).toByte()
        }
        val signatures = rules.mapTo(sortedSetOf()) { NgramEncoding.signature(it.features) }
        val keys = rules.map { NgramV3.canonicalKey(it, posIdByName) }
            .sortedWith(NgramV3::compareUnsigned)
        require(keys.zipWithNext().none { (left, right) -> left.contentEquals(right) }) {
            "Duplicate canonical n-gram keys"
        }
        val maxKeyBytes = keys.maxOfOrNull(ByteArray::size) ?: 0

        val bucketCount = chooseBucketCount(keys.size)
        val bucketBits = Integer.numberOfTrailingZeros(bucketCount)
        val buckets = Array(bucketCount) { mutableListOf<HashEntry>() }
        keys.forEachIndexed { recordId, key ->
            val hash = NgramV3.hash64(key)
            val bucket = (hash ushr (64 - bucketBits)).toInt() and (bucketCount - 1)
            buckets[bucket] += HashEntry(hash and LOW_48_MASK, recordId)
        }
        buckets.forEach { entries ->
            entries.sortWith(compareBy<HashEntry> { it.remainder }.thenBy { it.recordId })
        }

        val exactOutput = ByteArrayOutputStream()
        val blockCount = (keys.size + NgramEncoding.BLOCK_SIZE - 1) / NgramEncoding.BLOCK_SIZE
        val blockOffsets = IntArray(blockCount + 1)
        for (block in 0 until blockCount) {
            blockOffsets[block] = exactOutput.size()
            val start = block * NgramEncoding.BLOCK_SIZE
            val end = minOf(start + NgramEncoding.BLOCK_SIZE, keys.size)
            var previous = ByteArray(0)
            for (recordId in start until end) {
                val key = keys[recordId]
                if (recordId == start) {
                    NgramV3.writeUVarint(exactOutput, key.size)
                    exactOutput.write(key)
                } else {
                    val prefix = NgramV3.commonPrefix(previous, key)
                    val suffixLength = key.size - prefix
                    NgramV3.writeUVarint(exactOutput, prefix)
                    NgramV3.writeUVarint(exactOutput, suffixLength)
                    exactOutput.write(key, prefix, suffixLength)
                }
                previous = key
            }
        }
        blockOffsets[blockCount] = exactOutput.size()
        val exactBytes = exactOutput.toByteArray()

        val signaturesOffset = NgramEncoding.HEADER_SIZE
        val contextsOffset = signaturesOffset + signatures.size * 4
        val bucketOffsetsOffset = align4(contextsOffset + contextClasses.size)
        val hashEntriesOffset = bucketOffsetsOffset + (bucketCount + 1) * 4
        val blockOffsetsOffset = hashEntriesOffset + keys.size * NgramEncoding.HASH_ENTRY_SIZE
        val recordsOffset = blockOffsetsOffset + blockOffsets.size * 4
        val fileSize = recordsOffset + exactBytes.size
        val bytes = ByteArray(fileSize)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        buffer.putInt(0, NgramEncoding.MAGIC)
        buffer.putInt(4, formatVersion)
        buffer.putInt(8, keys.size)
        buffer.putInt(12, contextClasses.size)
        buffer.putInt(16, posNames.size)
        buffer.putInt(20, signatures.size)
        buffer.putInt(24, maxKeyBytes)
        buffer.putInt(28, NgramEncoding.BLOCK_SIZE)
        buffer.putInt(32, signaturesOffset)
        buffer.putInt(36, contextsOffset)
        buffer.putInt(40, bucketOffsetsOffset)
        buffer.putInt(44, hashEntriesOffset)
        buffer.putInt(48, blockOffsetsOffset)
        buffer.putInt(52, recordsOffset)
        buffer.putInt(56, fileSize)
        buffer.putInt(64, bucketCount)
        buffer.putInt(68, blockCount)
        signatures.forEachIndexed { index, signature -> buffer.putInt(signaturesOffset + index * 4, signature) }
        contextClasses.copyInto(bytes, contextsOffset)
        var hashEntryIndex = 0
        for (bucket in buckets.indices) {
            buffer.putInt(bucketOffsetsOffset + bucket * 4, hashEntryIndex)
            for (entry in buckets[bucket]) {
                val offset = hashEntriesOffset + hashEntryIndex * NgramEncoding.HASH_ENTRY_SIZE
                putUInt48(bytes, offset, entry.remainder)
                buffer.putInt(offset + 6, entry.recordId)
                hashEntryIndex++
            }
        }
        buffer.putInt(bucketOffsetsOffset + bucketCount * 4, hashEntryIndex)
        blockOffsets.forEachIndexed { index, value -> buffer.putInt(blockOffsetsOffset + index * 4, value) }
        exactBytes.copyInto(bytes, recordsOffset)
        val crc = CRC32().apply { update(bytes, NgramEncoding.HEADER_SIZE, bytes.size - NgramEncoding.HEADER_SIZE) }
        buffer.putInt(60, crc.value.toInt())
        output.parentFile.mkdirs()
        output.writeBytes(bytes)
        SystemNgramBinaryReader(bytes).verify()
        return NgramBuildReport(
            ruleCount = keys.size,
            posClassCount = posNames.size,
            signatureCount = signatures.size,
            formatVersion = formatVersion,
            bytes = bytes.size,
            hashIndexBytes = (bucketCount + 1) * 4 + keys.size * NgramEncoding.HASH_ENTRY_SIZE,
            exactDataBytes = exactBytes.size,
        )
    }

    private fun parseIdDef(file: File): List<String> {
        require(file.isFile) { "Missing id.def: ${file.path}" }
        return file.readLines().mapIndexed { index, line ->
            val split = line.indexOfFirst(Char::isWhitespace)
            require(split > 0) { "Invalid id.def line ${index + 1}: $line" }
            require(line.substring(0, split).toInt() == index) { "Non-contiguous id.def at line ${index + 1}" }
            line.substring(split + 1)
        }
    }

    private fun validateRules(rules: List<NgramRule>, formatVersion: Int) {
        require(rules.isNotEmpty()) { "Cannot build an empty n-gram dictionary" }
        require(formatVersion == NgramEncoding.VERSION || formatVersion == NgramEncoding.UNIGRAM_VERSION) {
            "Unsupported n-gram format version: $formatVersion"
        }
        if (formatVersion == NgramEncoding.VERSION) {
            require(rules.all { it.features.size in 2..5 }) {
                "Version ${NgramEncoding.VERSION} supports only 2- to 5-gram rules"
            }
        } else {
            require(rules.all { rule ->
                rule.features.size == 1 && rule.features.single() is NgramFeature.Word
            }) {
                "Version ${NgramEncoding.UNIGRAM_VERSION} supports only single-word unigram rules"
            }
        }
    }

    private fun align4(value: Int): Int = (value + 3) and -4

    private fun chooseBucketCount(ruleCount: Int): Int {
        val wanted = ruleCount.coerceIn(256, NgramEncoding.BUCKET_COUNT)
        return if (wanted == 1) 1 else Integer.highestOneBit(wanted - 1) shl 1
    }

    private fun putUInt48(bytes: ByteArray, offset: Int, value: Long) {
        repeat(6) { index -> bytes[offset + index] = (value ushr (index * 8)).toByte() }
    }

    private const val LOW_48_MASK = 0x0000ffffffffffffL
}

class SystemNgramBinaryReader(private val bytes: ByteArray) {
    private val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)

    fun verify() {
        require(bytes.size >= NgramEncoding.HEADER_SIZE) { "Truncated n-gram header" }
        require(buffer.getInt(0) == NgramEncoding.MAGIC) { "Invalid n-gram magic" }
        val version = buffer.getInt(4)
        require(version == NgramEncoding.VERSION || version == NgramEncoding.UNIGRAM_VERSION) {
            "Unsupported n-gram version: $version"
        }
        require(buffer.getInt(56) == bytes.size) { "Invalid n-gram file size" }
        val ruleCount = buffer.getInt(8)
        val signatureCount = buffer.getInt(20)
        val signaturesOffset = buffer.getInt(32)
        require(signaturesOffset == NgramEncoding.HEADER_SIZE) { "Invalid signatures offset" }
        require(signatureCount > 0) { "N-gram dictionary has no signatures" }
        repeat(signatureCount) { index ->
            val order = NgramEncoding.order(buffer.getInt(signaturesOffset + index * 4))
            if (version == NgramEncoding.VERSION) {
                require(order in 2..5) { "Invalid v3 n-gram order: $order" }
            } else {
                require(order == 1) { "Invalid v4 n-gram order: $order" }
            }
        }
        val bucketCount = buffer.getInt(64)
        require(bucketCount in 256..NgramEncoding.BUCKET_COUNT && bucketCount.countOneBits() == 1) {
            "Invalid bucket count"
        }
        val crc = CRC32().apply { update(bytes, NgramEncoding.HEADER_SIZE, bytes.size - NgramEncoding.HEADER_SIZE) }
        require(buffer.getInt(60).toUInt().toLong() == crc.value) { "Invalid n-gram checksum" }
        val bucketOffsetsOffset = buffer.getInt(40)
        val hashEntriesOffset = buffer.getInt(44)
        val blockOffsetsOffset = buffer.getInt(48)
        val recordsOffset = buffer.getInt(52)
        val blockCount = buffer.getInt(68)
        require(hashEntriesOffset == bucketOffsetsOffset + (bucketCount + 1) * 4)
        require(blockOffsetsOffset == hashEntriesOffset + ruleCount * NgramEncoding.HASH_ENTRY_SIZE)
        require(recordsOffset == blockOffsetsOffset + (blockCount + 1) * 4)
        require(buffer.getInt(bucketOffsetsOffset) == 0)
        require(buffer.getInt(bucketOffsetsOffset + bucketCount * 4) == ruleCount)
        require(recordsOffset <= bytes.size)
    }
}
