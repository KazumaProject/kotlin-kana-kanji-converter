package com.kazumaproject.ngram

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.TreeMap
import java.util.zip.CRC32

data class NgramBuildReport(
    val ruleCount: Int,
    val posClassCount: Int,
    val signatureCount: Int,
    val stateCount: Int,
    val edgeCount: Int,
    val bytes: Int,
)

object SystemNgramBinaryBuilder {
    private class TrieNode {
        var terminal: Boolean = false
        val edges = TreeMap<Int, TrieNode>()
    }

    private data class StateKey(val terminal: Boolean, val edges: List<Pair<Int, Int>>)
    private data class CanonicalState(val terminal: Boolean, val edges: List<Pair<Int, Int>>)

    fun build(rules: List<NgramRule>, idDef: File, output: File): NgramBuildReport {
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

        val root = TrieNode()
        val signatures = sortedSetOf<Int>()
        rules.sortedBy(::canonicalRule).forEach { rule ->
            val signature = NgramEncoding.signature(rule.features)
            signatures += signature
            val tokens = buildList {
                add(NgramEncoding.SIGNATURE_BASE + signature)
                rule.features.forEach { feature ->
                    when (feature) {
                        is NgramFeature.Word -> {
                            add(NgramEncoding.WORD_START)
                            feature.value.forEach { add(it.code) }
                            add(NgramEncoding.WORD_END)
                        }
                        is NgramFeature.Pos -> add(
                            NgramEncoding.POS_BASE + requireNotNull(posIdByName[feature.value]),
                        )
                        NgramFeature.Any -> Unit
                    }
                }
            }
            var node = root
            tokens.forEach { token -> node = node.edges.getOrPut(token, ::TrieNode) }
            node.terminal = true
        }

        val states = mutableListOf<CanonicalState>()
        val stateIds = HashMap<StateKey, Int>()
        fun intern(node: TrieNode): Int {
            val edges = node.edges.map { (label, child) -> label to intern(child) }
            val key = StateKey(node.terminal, edges)
            return stateIds.getOrPut(key) {
                states.add(CanonicalState(node.terminal, edges))
                states.lastIndex
            }
        }
        val rootState = intern(root)
        val edgeCount = states.sumOf { it.edges.size }
        val signaturesOffset = NgramEncoding.HEADER_SIZE
        val contextsOffset = signaturesOffset + signatures.size * Int.SIZE_BYTES
        val statesOffset = align4(contextsOffset + contextClasses.size)
        val edgesOffset = statesOffset + states.size * NgramEncoding.STATE_SIZE
        val fileSize = edgesOffset + edgeCount * NgramEncoding.EDGE_SIZE
        val bytes = ByteArray(fileSize)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        buffer.putInt(0, NgramEncoding.MAGIC)
        buffer.putInt(4, NgramEncoding.VERSION)
        buffer.putInt(8, rules.size)
        buffer.putInt(12, rootState)
        buffer.putInt(16, states.size)
        buffer.putInt(20, edgeCount)
        buffer.putInt(24, signatures.size)
        buffer.putInt(28, contextClasses.size)
        buffer.putInt(32, posNames.size)
        buffer.putInt(36, signaturesOffset)
        buffer.putInt(40, contextsOffset)
        buffer.putInt(44, statesOffset)
        buffer.putInt(48, edgesOffset)
        buffer.putInt(52, fileSize)
        signatures.forEachIndexed { index, signature -> buffer.putInt(signaturesOffset + index * 4, signature) }
        contextClasses.copyInto(bytes, contextsOffset)
        var edgeIndex = 0
        states.forEachIndexed { stateId, state ->
            val stateOffset = statesOffset + stateId * NgramEncoding.STATE_SIZE
            buffer.putInt(stateOffset, edgeIndex)
            buffer.putShort(stateOffset + 4, state.edges.size.toShort())
            buffer.put(stateOffset + 6, if (state.terminal) 1 else 0)
            state.edges.forEach { (label, target) ->
                val edgeOffset = edgesOffset + edgeIndex * NgramEncoding.EDGE_SIZE
                buffer.putInt(edgeOffset, label)
                buffer.putInt(edgeOffset + 4, target)
                edgeIndex++
            }
        }
        val crc = CRC32().apply { update(bytes, NgramEncoding.HEADER_SIZE, bytes.size - NgramEncoding.HEADER_SIZE) }
        buffer.putInt(56, crc.value.toInt())
        output.parentFile.mkdirs()
        output.writeBytes(bytes)
        SystemNgramBinaryReader(bytes).verify()
        return NgramBuildReport(rules.size, posNames.size, signatures.size, states.size, edgeCount, bytes.size)
    }

    private fun parseIdDef(file: File): List<String> {
        require(file.isFile) { "Missing id.def: ${file.path}" }
        return file.readLines().mapIndexed { index, line ->
            val split = line.indexOfFirst(Char::isWhitespace)
            require(split > 0) { "Invalid id.def line ${index + 1}: $line" }
            val id = line.substring(0, split).toInt()
            require(id == index) { "Non-contiguous id.def at line ${index + 1}: $id" }
            line.substring(split + 1)
        }
    }

    private fun canonicalRule(rule: NgramRule): String = rule.features.joinToString("|") {
        when (it) {
            is NgramFeature.Word -> "W:${it.value}"
            is NgramFeature.Pos -> "P:${it.value}"
            NgramFeature.Any -> "*"
        }
    }

    private fun align4(value: Int): Int = (value + 3) and -4
}

class SystemNgramBinaryReader(private val bytes: ByteArray) {
    private val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)

    fun verify() {
        require(bytes.size >= NgramEncoding.HEADER_SIZE) { "Truncated n-gram header" }
        require(buffer.getInt(0) == NgramEncoding.MAGIC) { "Invalid n-gram magic" }
        require(buffer.getInt(4) == NgramEncoding.VERSION) { "Unsupported n-gram version" }
        require(buffer.getInt(52) == bytes.size) { "Invalid n-gram file size" }
        val crc = CRC32().apply { update(bytes, NgramEncoding.HEADER_SIZE, bytes.size - NgramEncoding.HEADER_SIZE) }
        require(buffer.getInt(56).toUInt().toLong() == crc.value) { "Invalid n-gram checksum" }
        val stateCount = buffer.getInt(16)
        val edgeCount = buffer.getInt(20)
        val root = buffer.getInt(12)
        require(root in 0 until stateCount)
        val statesOffset = buffer.getInt(44)
        val edgesOffset = buffer.getInt(48)
        require(statesOffset >= NgramEncoding.HEADER_SIZE)
        require(edgesOffset == statesOffset + stateCount * NgramEncoding.STATE_SIZE)
        require(edgesOffset + edgeCount * NgramEncoding.EDGE_SIZE == bytes.size)
        repeat(stateCount) { state ->
            val offset = statesOffset + state * NgramEncoding.STATE_SIZE
            val first = buffer.getInt(offset)
            val count = buffer.getShort(offset + 4).toInt() and 0xffff
            require(first >= 0 && first + count <= edgeCount)
            var previous = Int.MIN_VALUE
            repeat(count) { local ->
                val edge = edgesOffset + (first + local) * NgramEncoding.EDGE_SIZE
                val label = buffer.getInt(edge)
                require(label > previous) { "Unsorted edge labels in state $state" }
                previous = label
                require(buffer.getInt(edge + 4) in 0 until stateCount)
            }
        }
    }
}
