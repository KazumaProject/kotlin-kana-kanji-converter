package com.kazumaproject.ngram.system

import java.util.TreeMap

internal class MutableIntTrieNode {
    val children: TreeMap<Int, MutableIntTrieNode> = TreeMap()
    var terminal: Boolean = false
}

internal class BitArray private constructor(
    val bitLength: Int,
    val words: LongArray,
) {
    private val rankDirectory = IntArray((words.size + RANK_WORDS - 1) / RANK_WORDS + 1)
    private val select0Samples: IntArray

    init {
        var ones = 0
        for (wordIndex in words.indices) {
            if (wordIndex % RANK_WORDS == 0) rankDirectory[wordIndex / RANK_WORDS] = ones
            ones += java.lang.Long.bitCount(words[wordIndex])
        }
        rankDirectory[rankDirectory.lastIndex] = ones

        val zeroCount = bitLength - rank1(bitLength)
        val samples = IntArray((zeroCount + SELECT_ZERO_STEP - 1) / SELECT_ZERO_STEP)
        var zeroIndex = 0
        for (bit in 0 until bitLength) {
            if (!get(bit)) {
                if (zeroIndex % SELECT_ZERO_STEP == 0) samples[zeroIndex / SELECT_ZERO_STEP] = bit
                zeroIndex++
            }
        }
        select0Samples = samples
    }

    fun get(index: Int): Boolean = index in 0 until bitLength &&
        ((words[index ushr 6] ushr (index and 63)) and 1L) != 0L

    /** Number of one bits in [0, endExclusive). */
    fun rank1(endExclusive: Int): Int {
        if (endExclusive <= 0) return 0
        val end = endExclusive.coerceAtMost(bitLength)
        val fullWords = end ushr 6
        val directoryBlock = fullWords / RANK_WORDS
        var result = rankDirectory[directoryBlock]
        var wordIndex = directoryBlock * RANK_WORDS
        while (wordIndex < fullWords) {
            result += java.lang.Long.bitCount(words[wordIndex])
            wordIndex++
        }
        val remaining = end and 63
        if (remaining != 0 && fullWords < words.size) {
            result += java.lang.Long.bitCount(words[fullWords] and ((1L shl remaining) - 1L))
        }
        return result
    }

    fun select0(zeroIndex: Int): Int {
        require(zeroIndex >= 0)
        val sampleIndex = zeroIndex / SELECT_ZERO_STEP
        require(sampleIndex < select0Samples.size) { "zero index outside bit vector: $zeroIndex" }
        var bit = select0Samples[sampleIndex]
        var currentZero = sampleIndex * SELECT_ZERO_STEP
        while (currentZero < zeroIndex) {
            bit++
            while (bit < bitLength && get(bit)) bit++
            currentZero++
        }
        return bit
    }

    fun estimatedHeapBytes(): Long =
        16L + words.size * 8L + 16L + rankDirectory.size * 4L + 16L + select0Samples.size * 4L

    companion object {
        private const val RANK_WORDS = 8
        private const val SELECT_ZERO_STEP = 64

        fun fromWords(bitLength: Int, words: LongArray): BitArray {
            require(bitLength >= 0)
            require(words.size == (bitLength + 63) / 64)
            return BitArray(bitLength, words)
        }

        fun build(bits: List<Boolean>): BitArray {
            val words = LongArray((bits.size + 63) / 64)
            bits.forEachIndexed { index, value ->
                if (value) words[index ushr 6] = words[index ushr 6] or (1L shl (index and 63))
            }
            return BitArray(bits.size, words)
        }
    }
}

internal data class IntLouds(
    val topology: BitArray,
    val labels: IntArray,
    val terminals: BitArray,
) {
    val nodeCount: Int get() = labels.size + 1

    fun transition(nodeId: Int, label: Int): Int {
        if (nodeId !in 0 until nodeCount) return -1
        val startBit = if (nodeId == 0) 0 else topology.select0(nodeId - 1) + 1
        val endBit = topology.select0(nodeId)
        val degree = endBit - startBit
        if (degree <= 0) return -1
        val firstChildId = topology.rank1(startBit) + 1
        var low = firstChildId
        var high = firstChildId + degree - 1
        while (low <= high) {
            val middle = (low + high) ushr 1
            val middleLabel = labels[middle - 1]
            when {
                middleLabel < label -> low = middle + 1
                middleLabel > label -> high = middle - 1
                else -> return middle
            }
        }
        return -1
    }

    fun isTerminal(nodeId: Int): Boolean = terminals.get(nodeId)

    fun estimatedHeapBytes(): Long =
        24L + topology.estimatedHeapBytes() + terminals.estimatedHeapBytes() + 16L + labels.size * 4L

    companion object {
        fun build(root: MutableIntTrieNode): IntLouds {
            val nodes = mutableListOf<MutableIntTrieNode>()
            val labels = mutableListOf<Int>()
            val queue = ArrayDeque<MutableIntTrieNode>()
            queue.add(root)
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                nodes += node
                node.children.forEach { (label, child) ->
                    labels += label
                    queue.add(child)
                }
            }
            val topologyBits = ArrayList<Boolean>(nodes.size * 2)
            nodes.forEach { node ->
                repeat(node.children.size) { topologyBits += true }
                topologyBits += false
            }
            return IntLouds(
                topology = BitArray.build(topologyBits),
                labels = labels.toIntArray(),
                terminals = BitArray.build(nodes.map { it.terminal }),
            )
        }
    }
}

internal data class ByteLouds(
    val topology: BitArray,
    val labels: ByteArray,
    val terminals: BitArray,
) {
    val nodeCount: Int get() = labels.size + 1

    fun transition(nodeId: Int, unsignedLabel: Int): Int {
        val startBit = if (nodeId == 0) 0 else topology.select0(nodeId - 1) + 1
        val endBit = topology.select0(nodeId)
        val degree = endBit - startBit
        if (degree <= 0) return -1
        val firstChildId = topology.rank1(startBit) + 1
        var low = firstChildId
        var high = firstChildId + degree - 1
        while (low <= high) {
            val middle = (low + high) ushr 1
            val middleLabel = labels[middle - 1].toInt() and 0xff
            when {
                middleLabel < unsignedLabel -> low = middle + 1
                middleLabel > unsignedLabel -> high = middle - 1
                else -> return middle
            }
        }
        return -1
    }

    fun find(bytes: ByteArray): Int {
        var node = 0
        for (byte in bytes) {
            node = transition(node, byte.toInt() and 0xff)
            if (node < 0) return 0
        }
        if (!terminals.get(node)) return 0
        return terminals.rank1(node + 1)
    }

    fun estimatedHeapBytes(): Long =
        24L + topology.estimatedHeapBytes() + terminals.estimatedHeapBytes() + 16L + labels.size

    companion object {
        fun build(words: Collection<String>): ByteLouds {
            val root = MutableIntTrieNode()
            words.sorted().forEach { word ->
                var node = root
                word.toByteArray(Charsets.UTF_8).forEach { byte ->
                    node = node.children.getOrPut(byte.toInt() and 0xff) { MutableIntTrieNode() }
                }
                node.terminal = true
            }
            val louds = IntLouds.build(root)
            return ByteLouds(louds.topology, ByteArray(louds.labels.size) { louds.labels[it].toByte() }, louds.terminals)
        }
    }
}
