package com.kazumaproject.ngram

import java.util.ArrayDeque
import kotlin.math.ceil

class TwoBitArray private constructor(
    val size: Int,
    private val bytes: ByteArray,
) {
    fun get(index: Int): Int {
        require(index in 0 until size) { "2-bit index out of bounds: index=$index size=$size" }
        val bitIndex = index * 2
        val byteIndex = bitIndex ushr 3
        val shift = bitIndex and 7
        return ((bytes[byteIndex].toInt() ushr shift) and 0x03)
    }

    fun toByteArray(): ByteArray = bytes.copyOf()

    fun toIntArray(): IntArray = IntArray(size) { get(it) }

    companion object {
        fun fromIntArray(values: IntArray): TwoBitArray {
            val bytes = ByteArray((values.size * 2 + 7) / 8)
            values.forEachIndexed { index, value ->
                require(value in 0..3) { "2-bit value must be 0..3: $value" }
                val bitIndex = index * 2
                val byteIndex = bitIndex ushr 3
                val shift = bitIndex and 7
                bytes[byteIndex] = (bytes[byteIndex].toInt() or (value shl shift)).toByte()
            }
            return TwoBitArray(values.size, bytes)
        }

        fun fromByteArray(size: Int, bytes: ByteArray): TwoBitArray {
            require(bytes.size == (size * 2 + 7) / 8) {
                "Invalid 2-bit byte size: size=$size bytes=${bytes.size}"
            }
            return TwoBitArray(size, bytes.copyOf())
        }
    }
}

class RankBitVector(
    val bitCount: Int,
    private val bitBytes: ByteArray,
    val rankLarge: IntArray,
    val rankSmall: ShortArray,
) {
    fun get(index: Int): Boolean {
        if (index !in 0 until bitCount) {
            return false
        }
        return ((bitBytes[index ushr 3].toInt() ushr (index and 7)) and 1) != 0
    }

    fun rank1(index: Int): Int {
        if (bitCount == 0 || index < 0) {
            return 0
        }
        val clamped = index.coerceAtMost(bitCount - 1)
        val smallIndex = clamped ushr 6
        val largeIndex = smallIndex ushr 3
        val smallBlockStart = smallIndex shl 6
        var result = rankLarge[largeIndex] + (rankSmall[smallIndex].toInt() and 0xffff)
        var bit = smallBlockStart
        while (bit <= clamped) {
            if (get(bit)) {
                result += 1
            }
            bit += 1
        }
        return result
    }

    fun toBitByteArray(): ByteArray = bitBytes.copyOf()

    companion object {
        fun fromBooleans(bits: BooleanArray): RankBitVector {
            val bytes = ByteArray((bits.size + 7) / 8)
            bits.forEachIndexed { index, value ->
                if (value) {
                    bytes[index ushr 3] = (bytes[index ushr 3].toInt() or (1 shl (index and 7))).toByte()
                }
            }
            return fromByteArray(bits.size, bytes)
        }

        fun fromByteArray(bitCount: Int, bitBytes: ByteArray): RankBitVector {
            if (bitCount == 0) {
                return RankBitVector(0, ByteArray(0), IntArray(0), ShortArray(0))
            }
            val expectedByteCount = (bitCount + 7) / 8
            require(bitBytes.size == expectedByteCount) {
                "Invalid bitvector byte size: bitCount=$bitCount bytes=${bitBytes.size}"
            }
            val smallCount = (bitCount + 63) / 64
            val largeCount = (smallCount + 7) / 8
            val large = IntArray(largeCount)
            val small = ShortArray(smallCount)
            var total = 0
            for (smallIndex in 0 until smallCount) {
                val largeIndex = smallIndex ushr 3
                if ((smallIndex and 7) == 0) {
                    large[largeIndex] = total
                }
                small[smallIndex] = (total - large[largeIndex]).toShort()
                val start = smallIndex shl 6
                val endExclusive = minOf(start + 64, bitCount)
                for (bit in start until endExclusive) {
                    if (((bitBytes[bit ushr 3].toInt() ushr (bit and 7)) and 1) != 0) {
                        total += 1
                    }
                }
            }
            return RankBitVector(bitCount, bitBytes.copyOf(), large, small)
        }
    }
}

data class BdzSectionBuild(
    val order: Int,
    val entryCount: Int,
    val vertexCount: Int,
    val retryCount: Int,
    val seed0: Long,
    val seed1: Long,
    val seed2: Long,
    val g: TwoBitArray,
    val usedVertices: RankBitVector,
    val keyArrays: List<LongArray>,
) {
    val binaryPayloadByteSize: Long
        get() = g.toByteArray().size.toLong() +
                usedVertices.toBitByteArray().size +
                usedVertices.rankLarge.size.toLong() * Int.SIZE_BYTES +
                usedVertices.rankSmall.size.toLong() * Short.SIZE_BYTES +
                keyArrays.sumOf { it.size.toLong() * Long.SIZE_BYTES }
}

class BdzMphfBuilder(
    private val maxRetries: Int = 10_000,
) {
    fun build(order: Int, inputEntries: List<NgramKeySequence>): BdzSectionBuild {
        require(order in 1..NGRAM_SECTION_COUNT) { "order must be 1..$NGRAM_SECTION_COUNT: $order" }
        val entries = inputEntries
            .filter { it.order == order }
            .sorted()
            .dedupeSorted()
        if (entries.isEmpty()) {
            return emptySection(order)
        }

        repeat(maxRetries) { retry ->
            val vertexCount = vertexCountFor(entries.size, retry)
            val seed0 = BdzHash.seed(order, retry, 0)
            val seed1 = BdzHash.seed(order, retry, 1)
            val seed2 = BdzHash.seed(order, retry, 2)

            val edgeV0 = IntArray(entries.size)
            val edgeV1 = IntArray(entries.size)
            val edgeV2 = IntArray(entries.size)
            entries.forEachIndexed { index, entry ->
                edgeV0[index] = BdzHash.vertex0(entry.order, entry.keys, vertexCount, seed0)
                edgeV1[index] = BdzHash.vertex1(entry.order, entry.keys, vertexCount, seed1, edgeV0[index])
                edgeV2[index] = BdzHash.vertex2(entry.order, entry.keys, vertexCount, seed2, edgeV0[index], edgeV1[index])
            }

            peel(vertexCount, edgeV0, edgeV1, edgeV2)?.let { peelResult ->
                val gValues = assignG(vertexCount, edgeV0, edgeV1, edgeV2, peelResult)
                val used = BooleanArray(vertexCount)
                peelResult.peelVertices.forEach { used[it] = true }
                val rank = RankBitVector.fromBooleans(used)
                val keyArrays = List(order) { LongArray(entries.size) }
                val occupied = BooleanArray(entries.size)
                var valid = true
                entries.forEach { entry ->
                    val index = BdzRuntime.index(
                        order = order,
                        a = entry.keys[0],
                        b = entry.keys.getOrElse(1) { 0L },
                        c = entry.keys.getOrElse(2) { 0L },
                        d = entry.keys.getOrElse(3) { 0L },
                        e = entry.keys.getOrElse(4) { 0L },
                        vertexCount = vertexCount,
                        seed0 = seed0,
                        seed1 = seed1,
                        seed2 = seed2,
                        g = TwoBitArray.fromIntArray(gValues),
                        usedVertices = rank,
                    )
                    if (index !in entries.indices || occupied[index]) {
                        valid = false
                        return@forEach
                    }
                    occupied[index] = true
                    for (keyIndex in 0 until order) {
                        keyArrays[keyIndex][index] = entry.keys[keyIndex]
                    }
                }
                if (valid && occupied.all { it }) {
                    return BdzSectionBuild(
                        order = order,
                        entryCount = entries.size,
                        vertexCount = vertexCount,
                        retryCount = retry,
                        seed0 = seed0,
                        seed1 = seed1,
                        seed2 = seed2,
                        g = TwoBitArray.fromIntArray(gValues),
                        usedVertices = rank,
                        keyArrays = keyArrays,
                    )
                }
            }
        }
        error("Failed to build BDZ MPHF: order=$order entries=${entries.size} retries=$maxRetries")
    }

    private fun vertexCountFor(entryCount: Int, retry: Int): Int {
        val base = ceil(entryCount * 1.30).toInt()
        return maxOf(3, base + retry / 128)
    }

    private fun peel(
        vertexCount: Int,
        edgeV0: IntArray,
        edgeV1: IntArray,
        edgeV2: IntArray,
    ): PeelResult? {
        val edgeCount = edgeV0.size
        val degree = IntArray(vertexCount)
        val xorEdge = IntArray(vertexCount)
        for (edge in 0 until edgeCount) {
            val a = edgeV0[edge]
            val b = edgeV1[edge]
            val c = edgeV2[edge]
            degree[a] += 1
            degree[b] += 1
            degree[c] += 1
            xorEdge[a] = xorEdge[a] xor edge
            xorEdge[b] = xorEdge[b] xor edge
            xorEdge[c] = xorEdge[c] xor edge
        }

        val queue = ArrayDeque<Int>()
        for (vertex in 0 until vertexCount) {
            if (degree[vertex] == 1) {
                queue.add(vertex)
            }
        }

        val removed = BooleanArray(edgeCount)
        val peelEdges = IntArray(edgeCount)
        val peelVertices = IntArray(edgeCount)
        var peelCount = 0
        while (!queue.isEmpty()) {
            val vertex = queue.removeFirst()
            if (degree[vertex] != 1) {
                continue
            }
            val edge = xorEdge[vertex]
            if (edge !in 0 until edgeCount || removed[edge]) {
                continue
            }
            removed[edge] = true
            peelEdges[peelCount] = edge
            peelVertices[peelCount] = vertex
            peelCount += 1

            fun removeFrom(v: Int) {
                degree[v] -= 1
                xorEdge[v] = xorEdge[v] xor edge
                if (degree[v] == 1) {
                    queue.add(v)
                }
            }

            removeFrom(edgeV0[edge])
            removeFrom(edgeV1[edge])
            removeFrom(edgeV2[edge])
        }

        if (peelCount != edgeCount) {
            return null
        }
        return PeelResult(peelEdges, peelVertices)
    }

    private fun assignG(
        vertexCount: Int,
        edgeV0: IntArray,
        edgeV1: IntArray,
        edgeV2: IntArray,
        peelResult: PeelResult,
    ): IntArray {
        val g = IntArray(vertexCount)
        for (index in peelResult.peelEdges.indices.reversed()) {
            val edge = peelResult.peelEdges[index]
            val selectedVertex = peelResult.peelVertices[index]
            val v0 = edgeV0[edge]
            val v1 = edgeV1[edge]
            val v2 = edgeV2[edge]
            val selectedLocal = when (selectedVertex) {
                v0 -> 0
                v1 -> 1
                v2 -> 2
                else -> error("Selected vertex is not part of edge")
            }
            val sumOther = when (selectedLocal) {
                0 -> g[v1] + g[v2]
                1 -> g[v0] + g[v2]
                else -> g[v0] + g[v1]
            }
            g[selectedVertex] = floorMod3(selectedLocal - sumOther)
        }
        return g
    }

    private fun emptySection(order: Int): BdzSectionBuild {
        return BdzSectionBuild(
            order = order,
            entryCount = 0,
            vertexCount = 0,
            retryCount = 0,
            seed0 = 0L,
            seed1 = 0L,
            seed2 = 0L,
            g = TwoBitArray.fromIntArray(IntArray(0)),
            usedVertices = RankBitVector.fromBooleans(BooleanArray(0)),
            keyArrays = List(order) { LongArray(0) },
        )
    }

    private fun List<NgramKeySequence>.dedupeSorted(): List<NgramKeySequence> {
        val result = mutableListOf<NgramKeySequence>()
        forEach { entry ->
            if (result.lastOrNull() != entry) {
                result += entry
            }
        }
        return result
    }

    private data class PeelResult(
        val peelEdges: IntArray,
        val peelVertices: IntArray,
    )
}

object BdzRuntime {
    fun index(
        order: Int,
        a: Long,
        b: Long,
        c: Long,
        d: Long,
        e: Long,
        vertexCount: Int,
        seed0: Long,
        seed1: Long,
        seed2: Long,
        g: TwoBitArray,
        usedVertices: RankBitVector,
    ): Int {
        if (vertexCount == 0) {
            return -1
        }
        val v0 = BdzHash.vertex0(order, a, b, c, d, e, vertexCount, seed0)
        val v1 = BdzHash.vertex1(order, a, b, c, d, e, vertexCount, seed1, v0)
        val v2 = BdzHash.vertex2(order, a, b, c, d, e, vertexCount, seed2, v0, v1)
        val local = (g.get(v0) + g.get(v1) + g.get(v2)) % 3
        val selectedVertex = when (local) {
            0 -> v0
            1 -> v1
            else -> v2
        }
        if (!usedVertices.get(selectedVertex)) {
            return -1
        }
        return usedVertices.rank1(selectedVertex) - 1
    }
}

object BdzHash {
    fun seed(order: Int, retry: Int, channel: Int): Long {
        return mix(0x4e47503100000000L xor (order.toLong() shl 40) xor (retry.toLong() shl 8) xor channel.toLong())
    }

    fun vertex0(order: Int, keys: LongArray, vertexCount: Int, seed0: Long): Int =
        vertex0(order, keys[0], keys.getOrElse(1) { 0L }, keys.getOrElse(2) { 0L }, keys.getOrElse(3) { 0L }, keys.getOrElse(4) { 0L }, vertexCount, seed0)

    fun vertex1(order: Int, keys: LongArray, vertexCount: Int, seed1: Long, v0: Int): Int =
        vertex1(order, keys[0], keys.getOrElse(1) { 0L }, keys.getOrElse(2) { 0L }, keys.getOrElse(3) { 0L }, keys.getOrElse(4) { 0L }, vertexCount, seed1, v0)

    fun vertex2(order: Int, keys: LongArray, vertexCount: Int, seed2: Long, v0: Int, v1: Int): Int =
        vertex2(order, keys[0], keys.getOrElse(1) { 0L }, keys.getOrElse(2) { 0L }, keys.getOrElse(3) { 0L }, keys.getOrElse(4) { 0L }, vertexCount, seed2, v0, v1)

    fun vertex0(order: Int, a: Long, b: Long, c: Long, d: Long, e: Long, vertexCount: Int, seed0: Long): Int {
        return reduce(hashKeys(seed0, order, a, b, c, d, e), vertexCount)
    }

    fun vertex1(order: Int, a: Long, b: Long, c: Long, d: Long, e: Long, vertexCount: Int, seed1: Long, v0: Int): Int {
        var bump = 0L
        while (true) {
            val value = reduce(hashKeys(seed1 + bump * GOLDEN_GAMMA, order, a, b, c, d, e), vertexCount)
            if (value != v0) {
                return value
            }
            bump += 1
            if (bump > 64) {
                return firstDistinct(vertexCount, v0)
            }
        }
    }

    fun vertex2(order: Int, a: Long, b: Long, c: Long, d: Long, e: Long, vertexCount: Int, seed2: Long, v0: Int, v1: Int): Int {
        var bump = 0L
        while (true) {
            val value = reduce(hashKeys(seed2 + bump * GOLDEN_GAMMA, order, a, b, c, d, e), vertexCount)
            if (value != v0 && value != v1) {
                return value
            }
            bump += 1
            if (bump > 64) {
                return firstDistinct(vertexCount, v0, v1)
            }
        }
    }

    private fun firstDistinct(vertexCount: Int, vararg used: Int): Int {
        for (candidate in 0 until vertexCount) {
            if (used.none { it == candidate }) {
                return candidate
            }
        }
        error("vertexCount must be at least 3")
    }

    private fun hashKeys(seed: Long, order: Int, a: Long, b: Long, c: Long, d: Long, e: Long): Long {
        var value = mix(seed xor order.toLong())
        value = mix(value xor a)
        if (order >= 2) value = mix(value xor b)
        if (order >= 3) value = mix(value xor c)
        if (order >= 4) value = mix(value xor d)
        if (order >= 5) value = mix(value xor e)
        return mix(value xor (order.toLong() * GOLDEN_GAMMA))
    }

    private fun reduce(value: Long, modulo: Int): Int {
        require(modulo > 0) { "modulo must be positive" }
        return ((value and Long.MAX_VALUE) % modulo.toLong()).toInt()
    }

    private fun mix(input: Long): Long {
        var z = input + GOLDEN_GAMMA
        z = (z xor (z ushr 30)) * MIX_1
        z = (z xor (z ushr 27)) * MIX_2
        return z xor (z ushr 31)
    }

    private const val GOLDEN_GAMMA = -7046029254386353131L
    private const val MIX_1 = -4658895280553007687L
    private const val MIX_2 = -7723592293110705685L
}

private fun floorMod3(value: Int): Int {
    val mod = value % 3
    return if (mod < 0) mod + 3 else mod
}
