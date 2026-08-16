package com.kazumaproject.ngram

import com.kazumaproject.graph.Node
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** A scoreless dictionary used to promote already existing conversion paths. */
interface SystemNgramDictionary {
    val ruleCount: Int
    val storageBytes: Int

    fun matches(
        node0: Node,
        node1: Node,
        node2: Node?,
        node3: Node?,
        node4: Node?,
    ): Boolean

    /** A conservative prefix check. False must mean that no rule can match. */
    fun mayMatchFirstPair(node0: Node, node1: Node): Boolean = true

    /** A conservative prefix check. False must mean that no rule can start here. */
    fun mayMatchFirstNode(node: Node): Boolean = true
}

object EmptySystemNgramDictionary : SystemNgramDictionary {
    override val ruleCount: Int = 0
    override val storageBytes: Int = 0

    override fun matches(
        node0: Node,
        node1: Node,
        node2: Node?,
        node3: Node?,
        node4: Node?,
    ): Boolean = false

    override fun mayMatchFirstPair(node0: Node, node1: Node): Boolean = false
    override fun mayMatchFirstNode(node: Node): Boolean = false
}

/** A scoreless one-node dictionary stored in the version-4 asset format. */
interface SystemUnigramDictionary {
    val ruleCount: Int
    val storageBytes: Int

    fun matches(node: Node): Boolean
}

object EmptySystemUnigramDictionary : SystemUnigramDictionary {
    override val ruleCount: Int = 0
    override val storageBytes: Int = 0
    override fun matches(node: Node): Boolean = false
}

/**
 * Reader for JapaneseKeyboard's packed version-3 system n-gram asset.
 *
 * The records are decoded once at load time. This keeps the reader small and makes the exact
 * binary semantics easy to test; the asset currently contains only a few thousand rules.
 */
class PackedSystemNgramDictionary private constructor(bytes: ByteArray) : SystemNgramDictionary {
    private val records = PackedNgramRecords(bytes, NgramEncoding.VERSION)
    private val signatures = records.signatures
    private val keys = HashSet<BinaryKey>(records.ruleCount * 2)
    private val firstNodes = HashSet<PrefixValue>()
    private val firstPairs = HashSet<Pair<PrefixValue, PrefixValue>>()

    override val ruleCount: Int = records.ruleCount
    override val storageBytes: Int = records.storageBytes

    init {
        repeat(records.ruleCount) { recordId ->
            val key = records.decodeRecord(recordId)
            keys += BinaryKey(key)
            val features = decodeFeatures(key)
            require(features.size >= 2) { "Version-3 n-gram record has fewer than two features" }
            firstNodes += features.first()
            firstPairs += features[0] to features[1]
        }
    }

    override fun matches(
        node0: Node,
        node1: Node,
        node2: Node?,
        node3: Node?,
        node4: Node?,
    ): Boolean {
        if (node0.tango == "BOS" || node1.tango == "EOS") return false
        for (signature in signatures) {
            val order = NgramEncoding.order(signature)
            if (order >= 3 && (node2 == null || node2.tango == "EOS")) continue
            if (order >= 4 && (node3 == null || node3.tango == "EOS")) continue
            if (order >= 5 && (node4 == null || node4.tango == "EOS")) continue
            val query = encodeQuery(signature, node0, node1, node2, node3, node4) ?: continue
            if (BinaryKey(query) in keys) return true
        }
        return false
    }

    override fun mayMatchFirstPair(node0: Node, node1: Node): Boolean {
        if (node0.tango == "BOS" || node1.tango == "EOS") return false
        val firstValues = prefixValues(node0)
        val secondValues = prefixValues(node1)
        return firstValues.any { first -> secondValues.any { second -> first to second in firstPairs } }
    }

    override fun mayMatchFirstNode(node: Node): Boolean =
        node.tango != "BOS" && node.tango != "EOS" && prefixValues(node).any { it in firstNodes }

    private fun encodeQuery(
        signature: Int,
        node0: Node,
        node1: Node,
        node2: Node?,
        node3: Node?,
        node4: Node?,
    ): ByteArray? {
        val nodes = arrayOf(node0, node1, node2, node3, node4)
        val output = ByteArrayOutputStream()
        output.write(signature and 0xff)
        output.write((signature ushr 8) and 0xff)
        repeat(NgramEncoding.order(signature)) { index ->
            val node = nodes[index] ?: return null
            when (NgramEncoding.kindAt(signature, index)) {
                NgramEncoding.KIND_WORD -> {
                    val utf8 = node.tango.toByteArray(Charsets.UTF_8)
                    NgramV3.writeUVarint(output, utf8.size)
                    output.write(utf8)
                }
                NgramEncoding.KIND_POS -> {
                    val coarsePos = records.coarsePos(node) ?: return null
                    output.write(coarsePos)
                }
                NgramEncoding.KIND_ANY -> Unit
                else -> return null
            }
        }
        return output.toByteArray()
    }

    private fun decodeFeatures(key: ByteArray): List<PrefixValue> {
        require(key.size >= 2) { "Truncated n-gram record" }
        val signature = (key[0].toInt() and 0xff) or ((key[1].toInt() and 0xff) shl 8)
        var position = 2
        return List(NgramEncoding.order(signature)) {
            when (val kind = NgramEncoding.kindAt(signature, it)) {
                NgramEncoding.KIND_WORD -> {
                    val length = readUVarint(key, position).also { position = it.next }.value
                    require(position + length <= key.size) { "Truncated n-gram word feature" }
                    PrefixValue(kind, key.copyOfRange(position, position + length).toString(Charsets.UTF_8))
                        .also { position += length }
                }
                NgramEncoding.KIND_POS -> {
                    require(position < key.size) { "Truncated n-gram POS feature" }
                    PrefixValue(kind, key[position++].toInt() and 0xff)
                }
                NgramEncoding.KIND_ANY -> PrefixValue(kind, null)
                else -> error("Invalid n-gram feature kind: $kind")
            }
        }
    }

    private fun prefixValues(node: Node): List<PrefixValue> = buildList {
        add(PrefixValue(NgramEncoding.KIND_WORD, node.tango))
        records.coarsePos(node)?.let { add(PrefixValue(NgramEncoding.KIND_POS, it)) }
        add(PrefixValue(NgramEncoding.KIND_ANY, null))
    }

    companion object {
        fun read(bytes: ByteArray): PackedSystemNgramDictionary =
            PackedSystemNgramDictionary(bytes.copyOf())

        fun fromFile(file: File): PackedSystemNgramDictionary = read(file.readBytes())
    }
}

/** Reader for the separate version-4 literal unigram asset. */
class PackedSystemUnigramDictionary private constructor(bytes: ByteArray) : SystemUnigramDictionary {
    private val records = PackedNgramRecords(bytes, NgramEncoding.UNIGRAM_VERSION)
    private val words = HashSet<String>(records.ruleCount * 2)

    override val ruleCount: Int = records.ruleCount
    override val storageBytes: Int = records.storageBytes

    init {
        repeat(records.ruleCount) { recordId ->
            val key = records.decodeRecord(recordId)
            words += decodeWord(key)
        }
    }

    override fun matches(node: Node): Boolean =
        node.tango != "BOS" && node.tango != "EOS" && node.tango in words

    private fun decodeWord(key: ByteArray): String {
        require(key.size >= 2) { "Truncated unigram record" }
        val signature = (key[0].toInt() and 0xff) or ((key[1].toInt() and 0xff) shl 8)
        require(NgramEncoding.order(signature) == 1) { "Unigram record is not one node" }
        require(NgramEncoding.kindAt(signature, 0) == NgramEncoding.KIND_WORD) {
            "Unigram record is not a literal word"
        }
        val length = readUVarint(key, 2)
        require(length.next + length.value == key.size) { "Malformed unigram record" }
        return key.copyOfRange(length.next, key.size).toString(Charsets.UTF_8)
    }

    companion object {
        fun read(bytes: ByteArray): PackedSystemUnigramDictionary =
            PackedSystemUnigramDictionary(bytes.copyOf())

        fun fromFile(file: File): PackedSystemUnigramDictionary = read(file.readBytes())
    }
}

private data class PrefixValue(val kind: Int, val value: Any?)

private class BinaryKey(private val bytes: ByteArray) {
    override fun equals(other: Any?): Boolean = other is BinaryKey && bytes.contentEquals(other.bytes)
    override fun hashCode(): Int = bytes.contentHashCode()
}

private data class Varint(val value: Int, val next: Int)

private fun readUVarint(source: ByteArray, start: Int): Varint {
    var position = start
    var shift = 0
    var value = 0
    while (true) {
        require(position < source.size && shift <= 28) { "Malformed n-gram varint" }
        val byte = source[position++].toInt() and 0xff
        value = value or ((byte and 0x7f) shl shift)
        if (byte and 0x80 == 0) return Varint(value, position)
        shift += 7
    }
}

/** Shared compressed-record decoder for the v3 and v4 readers. */
private class PackedNgramRecords(
    private val bytes: ByteArray,
    expectedVersion: Int,
) {
    private val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    val ruleCount: Int = buffer.getInt(8)
    val storageBytes: Int = bytes.size
    private val contextCount = buffer.getInt(12)
    private val signatureCount = buffer.getInt(20)
    private val maxKeyBytes = buffer.getInt(24)
    private val blockSize = buffer.getInt(28)
    private val contextsOffset = buffer.getInt(36)
    private val blockOffsetsOffset = buffer.getInt(48)
    private val recordsOffset = buffer.getInt(52)

    val signatures: IntArray = IntArray(signatureCount) { index ->
        buffer.getInt(NgramEncoding.HEADER_SIZE + index * 4)
    }

    init {
        SystemNgramBinaryReader(bytes).verify()
        require(buffer.getInt(4) == expectedVersion) {
            "Expected n-gram version $expectedVersion, got ${buffer.getInt(4)}"
        }
        require(ruleCount > 0) { "N-gram dictionary has no rules" }
        require(blockSize > 0 && maxKeyBytes > 0) { "Invalid n-gram record metadata" }
    }

    fun coarsePos(node: Node): Int? {
        val contextId = node.l.toInt()
        return if (contextId in 0 until contextCount) {
            bytes[contextsOffset + contextId].toInt() and 0xff
        } else {
            null
        }
    }

    fun decodeRecord(recordId: Int): ByteArray {
        require(recordId in 0 until ruleCount) { "Invalid n-gram record ID: $recordId" }
        val block = recordId / blockSize
        val withinBlock = recordId % blockSize
        var position = recordsOffset + buffer.getInt(blockOffsetsOffset + block * 4)
        val first = readUVarint(bytes, position)
        var length = first.value
        position = first.next
        require(length <= maxKeyBytes && position + length <= bytes.size) { "Malformed n-gram record" }
        var key = ByteArray(length)
        bytes.copyInto(key, 0, position, position + length)
        position += length

        repeat(withinBlock) {
            val prefix = readUVarint(bytes, position)
            position = prefix.next
            val suffix = readUVarint(bytes, position)
            position = suffix.next
            length = prefix.value + suffix.value
            require(
                prefix.value <= key.size && length <= maxKeyBytes && position + suffix.value <= bytes.size,
            ) {
                "Malformed compressed n-gram record"
            }
            val nextKey = ByteArray(length)
            key.copyInto(nextKey, 0, 0, prefix.value)
            bytes.copyInto(nextKey, prefix.value, position, position + suffix.value)
            position += suffix.value
            key = nextKey
        }
        return key
    }
}
