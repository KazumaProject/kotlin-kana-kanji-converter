package succinctBitVector

import java.util.BitSet
import kotlin.math.min

class SuccinctBitVector(private val bitSet: BitSet) {
    // Constants: big block size = 256 bits, small block size = 8 bits
    private val bigBlockSize = 256
    private val smallBlockSize = 8
    private val numSmallBlocksPerBig = bigBlockSize / smallBlockSize

    // For each big block, store the cumulative count of 1s at the start of that block
    private val bigBlockRanks: IntArray

    // Within each big block, when divided into small blocks, store the difference in number of 1s from the block start
    private val smallBlockRanks: IntArray

    // Table recording the number of 1 bit (popcount) for each 8-bit value (0–255)
    private val popCountTable: IntArray = IntArray(256)

    // Total number of 1 bit in the entire BitSet
    private val totalOnes: Int

    private val n: Int = bitSet.size()

    init {
        // Build popcount table by computing the number of 1 bit for values 0–255
        for (i in 0 until 256) {
            popCountTable[i] = Integer.bitCount(i)
        }

        val n = bitSet.size()
        val numBigBlocks = (n + bigBlockSize - 1) / bigBlockSize
        bigBlockRanks = IntArray(numBigBlocks)
        val numSmallBlocks = (n + smallBlockSize - 1) / smallBlockSize
        smallBlockRanks = IntArray(numSmallBlocks)

        var rank = 0
        // Compute cumulative counts for each big block
        for (big in 0 until numBigBlocks) {
            val bigStart = big * bigBlockSize
            // Cumulative 1 count at the start of this big block
            bigBlockRanks[big] = rank

            // Divide the big block into small blocks (8 bits each) and compute
            for (small in 0 until numSmallBlocksPerBig) {
                val globalSmallIndex = big * numSmallBlocksPerBig + small
                // Check to avoid going out of bounds
                if (globalSmallIndex >= numSmallBlocks) break
                // Cumulative 1 count within the big block at the start of the small block
                smallBlockRanks[globalSmallIndex] = rank - bigBlockRanks[big]
                val smallStart = bigStart + small * smallBlockSize
                // Scan each bit in the small block to count 1s
                for (j in 0 until smallBlockSize) {
                    val pos = smallStart + j
                    if (pos >= n) break
                    if (bitSet.get(pos)) {
                        rank++
                    }
                }
            }
        }
        totalOnes = rank
    }

    fun size(): Int = n

    /**
     * rank1(index): Returns the number of 1 bit from 0 to index (inclusive)
     */
    fun rank1(index: Int): Int {
        if (index < 0) return 0
        val n = bitSet.size()
        if (index >= n) return totalOnes

        val bigIndex = index / bigBlockSize
        val offsetInBig = index % bigBlockSize
        val smallIndex = offsetInBig / smallBlockSize
        val offsetInSmall = offsetInBig % smallBlockSize

        // Cumulative from big block + difference from small block
        val rankBase =
            bigBlockRanks[bigIndex] + smallBlockRanks[bigIndex * numSmallBlocksPerBig + smallIndex]
        var additional = 0
        val smallBlockStart = bigIndex * bigBlockSize + smallIndex * smallBlockSize
        for (i in 0..offsetInSmall) {
            if (smallBlockStart + i >= n) break
            if (bitSet.get(smallBlockStart + i)) additional++
        }
        return rankBase + additional
    }

    /**
     * rank0(index): Returns the number of 0 bits from 0 to index (inclusive)
     * Can be computed as (index + 1) - rank1(index)
     */
    fun rank0(index: Int): Int {
        if (index < 0) return 0
        val n = bitSet.size()
        if (index >= n) return n - totalOnes
        return (index + 1) - rank1(index)
    }

    /**
     * select1(nodeId): Returns the position of the nodeId-th 1 bit (nodeId is 1-based)
     */
    fun select1(nodeId: Int): Int {
        if (nodeId < 1 || nodeId > totalOnes) return -1

        // Use binary search on big block auxiliary data to find the target big block
        var lo = 0
        var hi = bigBlockRanks.size - 1
        var bigBlock = 0
        while (lo <= hi) {
            val mid = (lo + hi) / 2
            if (bigBlockRanks[mid] < nodeId) {
                bigBlock = mid
                lo = mid + 1
            } else {
                hi = mid - 1
            }
        }
        // The difference from the number of 1s up to the start of the big block is the target within this big block
        val localTarget = nodeId - bigBlockRanks[bigBlock]

        // Linearly search the small blocks within the big block
        val baseSmallIndex = bigBlock * numSmallBlocksPerBig
        var smallBlock = 0
        while (smallBlock < numSmallBlocksPerBig - 1 &&
            smallBlockRanks[baseSmallIndex + smallBlock + 1] < localTarget
        ) {
            smallBlock++
        }

        // Scan the small block bit by bit to find the exact position
        val globalSmallIndex = baseSmallIndex + smallBlock
        val offsetInSmallBlock = localTarget - smallBlockRanks[globalSmallIndex]
        val smallBlockStart = bigBlock * bigBlockSize + smallBlock * smallBlockSize
        var count = 0
        for (i in 0 until smallBlockSize) {
            val pos = smallBlockStart + i
            if (pos >= bitSet.size()) break
            if (bitSet.get(pos)) {
                count++
                if (count == offsetInSmallBlock) {
                    return pos
                }
            }
        }
        return -1 // Should not happen
    }

    /**
     * select0(nodeId): Returns the position of the nodeId-th 0 bit (nodeId is 1-based)
     */
    fun select0(nodeId: Int): Int {
        val n = bitSet.size()
        val totalZeros = n - totalOnes
        if (nodeId < 1 || nodeId > totalZeros) return -1

        // Binary search on big blocks:
        // The number of 0s up to the start of each big block is (bigBlockIndex * bigBlockSize) - bigBlockRanks[bigBlockIndex]
        var lo = 0
        var hi = bigBlockRanks.size - 1
        var bigBlock = 0
        while (lo <= hi) {
            val mid = (lo + hi) / 2
            val zerosBefore = mid * bigBlockSize - bigBlockRanks[mid]
            if (zerosBefore < nodeId) {
                bigBlock = mid
                lo = mid + 1
            } else {
                hi = mid - 1
            }
        }
        val zerosBeforeBlock = bigBlock * bigBlockSize - bigBlockRanks[bigBlock]
        val localTarget = nodeId - zerosBeforeBlock

        // Linearly search small blocks within the big block
        val baseSmallIndex = bigBlock * numSmallBlocksPerBig
        val smallBlocksInThisBig = min(numSmallBlocksPerBig, smallBlockRanks.size - baseSmallIndex)
        var smallBlock = 0
        while (smallBlock < smallBlocksInThisBig - 1) {
            val nextZeros =
                (smallBlock + 1) * smallBlockSize - smallBlockRanks[baseSmallIndex + smallBlock + 1]
            if (nextZeros < localTarget) {
                smallBlock++
            } else {
                break
            }
        }
        val globalSmallIndex = baseSmallIndex + smallBlock
        val zerosBeforeSmall = (smallBlock * smallBlockSize) - smallBlockRanks[globalSmallIndex]
        val offsetInSmallBlock = localTarget - zerosBeforeSmall

        // Scan within the small block bit by bit to locate the desired 0
        val smallBlockStart = bigBlock * bigBlockSize + smallBlock * smallBlockSize
        var count = 0
        for (i in 0 until smallBlockSize) {
            val pos = smallBlockStart + i
            if (pos >= n) break
            if (!bitSet.get(pos)) {
                count++
                if (count == offsetInSmallBlock) {
                    return pos
                }
            }
        }
        return -1 // Should not happen
    }
}
