package com.kazumaproject.ngram.system

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.text.Normalizer
import java.util.zip.CRC32

class SystemNgramDictionary internal constructor(
    private val words: ByteLouds,
    private val patterns: IntLouds,
    private val posClassByLeftId: ByteArray,
    val ruleCount: Int,
    val maxOrder: Int,
) {
    val wordCount: Int get() = words.terminals.rank1(words.terminals.bitLength)
    val wordTrieNodeCount: Int get() = words.nodeCount
    val patternTrieNodeCount: Int get() = patterns.nodeCount

    fun findWordId(surface: String): Int =
        words.find(Normalizer.normalize(surface, Normalizer.Form.NFC).toByteArray(Charsets.UTF_8))

    fun posClassForLeftId(leftId: Int): SystemNgramPosClass =
        if (leftId in posClassByLeftId.indices) {
            SystemNgramPosClass.fromBinaryId(posClassByLeftId[leftId].toInt() and 0xff)
        } else {
            SystemNgramPosClass.UNKNOWN
        }

    fun matches(tokens: List<SystemNgramQueryToken>): Boolean {
        if (tokens.size !in SYSTEM_NGRAM_MIN_ORDER..maxOrder) return false
        val wordIds = IntArray(tokens.size) { findWordId(tokens[it].surface) }
        val posIds = IntArray(tokens.size) { tokens[it].posClass.binaryId }
        return newMatcher().matchesEncoded(wordIds, posIds)
    }

    fun newMatcher(): Matcher = Matcher(this)

    class Matcher internal constructor(private val dictionary: SystemNgramDictionary) {
        private var active = IntArray(INITIAL_ACTIVE_STATES)
        private var next = IntArray(INITIAL_ACTIVE_STATES)

        /** Returns true when a registered pattern is a prefix of the supplied 2..maxOrder window. */
        fun matchesEncoded(wordIds: IntArray, posClassIds: IntArray): Boolean {
            require(wordIds.size == posClassIds.size)
            if (wordIds.size < SYSTEM_NGRAM_MIN_ORDER) return false
            val limit = minOf(wordIds.size, dictionary.maxOrder)
            var activeSize = 1
            active[0] = 0

            for (index in 0 until limit) {
                if (next.size < activeSize * MAX_LABEL_ALTERNATIVES) {
                    next = next.copyOf((activeSize * MAX_LABEL_ALTERNATIVES).coerceAtMost(MAX_THEORETICAL_ACTIVE_STATES))
                }
                var nextSize = 0
                for (activeIndex in 0 until activeSize) {
                    val state = active[activeIndex]
                    val wordId = wordIds[index]
                    if (wordId > 0) {
                        nextSize = addTransition(next, nextSize, dictionary.patterns.transition(state, wordLabel(wordId)))
                    }
                    val posId = posClassIds[index]
                    if (posId > 0) {
                        nextSize = addTransition(next, nextSize, dictionary.patterns.transition(state, posLabel(posId)))
                        if (posId == SystemNgramPosClass.PROPER_NOUN.binaryId) {
                            nextSize = addTransition(
                                next,
                                nextSize,
                                dictionary.patterns.transition(state, posLabel(SystemNgramPosClass.NOUN.binaryId)),
                            )
                        }
                    }
                    nextSize = addTransition(next, nextSize, dictionary.patterns.transition(state, ANY_LABEL))
                }
                if (nextSize == 0) return false
                if (index + 1 >= SYSTEM_NGRAM_MIN_ORDER) {
                    for (stateIndex in 0 until nextSize) {
                        if (dictionary.patterns.isTerminal(next[stateIndex])) return true
                    }
                }
                val swap = active
                active = next
                next = swap
                activeSize = nextSize
            }
            return false
        }

        private fun addTransition(states: IntArray, size: Int, state: Int): Int {
            if (state < 0) return size
            for (index in 0 until size) if (states[index] == state) return size
            check(size < states.size) { "System N-gram matcher capacity invariant failed" }
            states[size] = state
            return size + 1
        }

        companion object {
            private const val INITIAL_ACTIVE_STATES = 16
            private const val MAX_LABEL_ALTERNATIVES = 4
            private const val MAX_THEORETICAL_ACTIVE_STATES = 1024
            const val ESTIMATED_HEAP_BYTES = 48L + 2L * (16L + INITIAL_ACTIVE_STATES * 4L)
        }
    }

    fun estimatedHeapBytes(): Long =
        40L + words.estimatedHeapBytes() + patterns.estimatedHeapBytes() + 16L + posClassByLeftId.size

    fun writeTo(file: File) {
        val payloadBuffer = ByteArrayOutputStream()
        DataOutputStream(payloadBuffer).use { output ->
            output.writeInt(maxOrder)
            output.writeInt(ruleCount)
            writeByteLouds(output, words)
            writeIntLouds(output, patterns)
            output.writeInt(posClassByLeftId.size)
            output.write(posClassByLeftId)
        }
        val payload = payloadBuffer.toByteArray()
        val crc = CRC32().apply { update(payload) }.value.toInt()
        file.parentFile.mkdirs()
        DataOutputStream(file.outputStream().buffered()).use { output ->
            output.writeInt(MAGIC)
            output.writeInt(FORMAT_VERSION)
            output.writeInt(payload.size)
            output.writeInt(crc)
            output.write(payload)
        }
    }

    companion object {
        private const val MAGIC = 0x534E4752 // SNGR
        const val FORMAT_VERSION = 1
        private const val LABEL_TYPE_WORD = 0
        private const val LABEL_TYPE_POS = 1
        private const val LABEL_TYPE_ANY = 2
        private const val ANY_LABEL = LABEL_TYPE_ANY

        internal fun wordLabel(wordId: Int): Int = (wordId shl 2) or LABEL_TYPE_WORD
        internal fun posLabel(posId: Int): Int = (posId shl 2) or LABEL_TYPE_POS

        fun readFrom(file: File): SystemNgramDictionary = DataInputStream(file.inputStream().buffered()).use { input ->
            require(input.readInt() == MAGIC) { "Invalid system N-gram dictionary magic: ${file.path}" }
            val version = input.readInt()
            require(version == FORMAT_VERSION) { "Unsupported system N-gram dictionary version: $version" }
            val payloadSize = input.readInt()
            require(payloadSize in 1..MAX_FILE_BYTES) { "Invalid system N-gram payload size: $payloadSize" }
            val expectedCrc = input.readInt()
            val payload = ByteArray(payloadSize)
            input.readFully(payload)
            require(input.read() == -1) { "Trailing bytes in system N-gram dictionary: ${file.path}" }
            val actualCrc = CRC32().apply { update(payload) }.value.toInt()
            require(actualCrc == expectedCrc) { "System N-gram dictionary CRC mismatch: ${file.path}" }
            DataInputStream(ByteArrayInputStream(payload)).use { payloadInput ->
                val maxOrder = payloadInput.readInt()
                val ruleCount = payloadInput.readInt()
                require(maxOrder in SYSTEM_NGRAM_MIN_ORDER..SYSTEM_NGRAM_MAX_ORDER)
                require(ruleCount > 0)
                val words = readByteLouds(payloadInput)
                val patterns = readIntLouds(payloadInput)
                require(patterns.terminals.rank1(patterns.terminals.bitLength) == ruleCount) {
                    "System N-gram terminal count does not match rule count"
                }
                val posSize = payloadInput.readInt()
                require(posSize in 1..MAX_POS_TABLE_SIZE)
                val posTable = ByteArray(posSize)
                payloadInput.readFully(posTable)
                require(posTable.all { (it.toInt() and 0xff) <= SystemNgramPosClass.OTHER.binaryId }) {
                    "System N-gram dictionary contains an unknown POS class ID"
                }
                require(payloadInput.read() == -1) { "Trailing bytes in system N-gram payload" }
                SystemNgramDictionary(words, patterns, posTable, ruleCount, maxOrder)
            }
        }

        internal fun build(rules: List<SystemNgramRule>, posClassByLeftId: ByteArray): SystemNgramDictionary {
            val surfaces = rules.flatMap { rule ->
                rule.elements.mapNotNull { (it as? SystemNgramElement.Word)?.surface }
            }.toSortedSet()
            val wordTrie = ByteLouds.build(surfaces)
            val root = MutableIntTrieNode()
            rules.sortedBy { SystemNgramRuleParser.canonicalPattern(it.elements) }.forEach { rule ->
                var node = root
                rule.elements.forEach { element ->
                    val label = when (element) {
                        is SystemNgramElement.Word -> {
                            val wordId = wordTrie.find(element.surface.toByteArray(Charsets.UTF_8))
                            check(wordId > 0)
                            wordLabel(wordId)
                        }
                        is SystemNgramElement.Pos -> posLabel(element.posClass.binaryId)
                        SystemNgramElement.Any -> ANY_LABEL
                    }
                    node = node.children.getOrPut(label) { MutableIntTrieNode() }
                }
                check(!node.terminal) { "Duplicate compiled system N-gram pattern at ${rule.sourceFile}:${rule.sourceLine}" }
                node.terminal = true
            }
            return SystemNgramDictionary(
                words = wordTrie,
                patterns = IntLouds.build(root),
                posClassByLeftId = posClassByLeftId.copyOf(),
                ruleCount = rules.size,
                maxOrder = rules.maxOf { it.elements.size },
            )
        }

        private fun writeBits(output: DataOutputStream, bits: BitArray) {
            output.writeInt(bits.bitLength)
            output.writeInt(bits.words.size)
            bits.words.forEach(output::writeLong)
        }

        private fun readBits(input: DataInputStream): BitArray {
            val bitLength = input.readInt()
            val wordCount = input.readInt()
            require(bitLength in 1..MAX_BITS)
            require(wordCount == (bitLength + 63) / 64)
            return BitArray.fromWords(bitLength, LongArray(wordCount) { input.readLong() })
        }

        private fun writeByteLouds(output: DataOutputStream, louds: ByteLouds) {
            writeBits(output, louds.topology)
            output.writeInt(louds.labels.size)
            output.write(louds.labels)
            writeBits(output, louds.terminals)
        }

        private fun readByteLouds(input: DataInputStream): ByteLouds {
            val topology = readBits(input)
            val labelSize = input.readInt()
            require(labelSize in 0..MAX_NODES)
            val labels = ByteArray(labelSize)
            input.readFully(labels)
            val terminals = readBits(input)
            require(terminals.bitLength == labels.size + 1)
            require(topology.bitLength == labels.size * 2 + 1)
            require(topology.rank1(topology.bitLength) == labels.size)
            return ByteLouds(topology, labels, terminals)
        }

        private fun writeIntLouds(output: DataOutputStream, louds: IntLouds) {
            writeBits(output, louds.topology)
            output.writeInt(louds.labels.size)
            louds.labels.forEach(output::writeInt)
            writeBits(output, louds.terminals)
        }

        private fun readIntLouds(input: DataInputStream): IntLouds {
            val topology = readBits(input)
            val labelSize = input.readInt()
            require(labelSize in 1..MAX_NODES)
            val labels = IntArray(labelSize) { input.readInt() }
            val terminals = readBits(input)
            require(terminals.bitLength == labels.size + 1)
            require(topology.bitLength == labels.size * 2 + 1)
            require(topology.rank1(topology.bitLength) == labels.size)
            return IntLouds(topology, labels, terminals)
        }

        private const val MAX_FILE_BYTES = 512 * 1024 * 1024
        private const val MAX_BITS = 500_000_000
        private const val MAX_NODES = 100_000_000
        private const val MAX_POS_TABLE_SIZE = 100_000
    }
}

private const val ANY_LABEL = 2
private fun wordLabel(wordId: Int): Int = wordId shl 2
private fun posLabel(posId: Int): Int = (posId shl 2) or 1
