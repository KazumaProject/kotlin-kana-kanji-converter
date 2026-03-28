package com.kazumaproject.bitset

import java.util.BitSet

class SuccinctBitVector(
    private val bitSet: BitSet,
) {
    private val size = bitSet.size()
    private val bigBlockRanks: IntArray
    private val smallBlockRanks: IntArray
    private val totalOnes: Int

    init {
        val bigBlockCount = (size + BIG_BLOCK_SIZE - 1) / BIG_BLOCK_SIZE
        val smallBlockCount = bigBlockCount * SMALL_BLOCKS_PER_BIG_BLOCK

        bigBlockRanks = IntArray(bigBlockCount.coerceAtLeast(1))
        smallBlockRanks = IntArray(smallBlockCount.coerceAtLeast(1))

        var ones = 0
        for (bigIndex in 0 until bigBlockCount) {
            bigBlockRanks[bigIndex] = ones

            val bigStart = bigIndex * BIG_BLOCK_SIZE
            for (smallIndex in 0 until SMALL_BLOCKS_PER_BIG_BLOCK) {
                val globalSmallIndex = bigIndex * SMALL_BLOCKS_PER_BIG_BLOCK + smallIndex
                val smallStart = bigStart + smallIndex * SMALL_BLOCK_SIZE
                smallBlockRanks[globalSmallIndex] = ones - bigBlockRanks[bigIndex]

                if (smallStart >= size) {
                    continue
                }

                val smallEndExclusive = minOf(smallStart + SMALL_BLOCK_SIZE, size)
                for (pos in smallStart until smallEndExclusive) {
                    if (bitSet[pos]) {
                        ones++
                    }
                }
            }
        }

        totalOnes = ones
    }

    fun rank1(index: Int): Int {
        if (index < 0) return 0
        if (index >= size) return totalOnes
        if (size == 0) return 0

        val bigIndex = index / BIG_BLOCK_SIZE
        val offsetInBig = index % BIG_BLOCK_SIZE
        val smallIndex = offsetInBig / SMALL_BLOCK_SIZE
        val offsetInSmall = offsetInBig % SMALL_BLOCK_SIZE
        val globalSmallIndex = bigIndex * SMALL_BLOCKS_PER_BIG_BLOCK + smallIndex

        var rank = bigBlockRanks[bigIndex] + smallBlockRanks[globalSmallIndex]
        val smallStart = bigIndex * BIG_BLOCK_SIZE + smallIndex * SMALL_BLOCK_SIZE
        for (offset in 0..offsetInSmall) {
            val pos = smallStart + offset
            if (pos >= size) {
                break
            }
            if (bitSet[pos]) {
                rank++
            }
        }
        return rank
    }

    fun rank0(index: Int): Int {
        if (index < 0) return 0
        if (index >= size) return size - totalOnes
        return index + 1 - rank1(index)
    }

    fun select1(nodeId: Int): Int {
        if (nodeId < 1 || nodeId > totalOnes || size == 0) {
            return -1
        }

        var low = 0
        var high = bigBlockRanks.lastIndex
        var bigBlock = 0
        while (low <= high) {
            val mid = (low + high) ushr 1
            if (bigBlockRanks[mid] < nodeId) {
                bigBlock = mid
                low = mid + 1
            } else {
                high = mid - 1
            }
        }

        val localTarget = nodeId - bigBlockRanks[bigBlock]
        val baseSmallIndex = bigBlock * SMALL_BLOCKS_PER_BIG_BLOCK
        val smallBlocksInThisBig = minOf(
            SMALL_BLOCKS_PER_BIG_BLOCK,
            maxOf(0, smallBlockRanks.size - baseSmallIndex),
        )

        var smallBlock = 0
        while (smallBlock < smallBlocksInThisBig - 1) {
            val nextIndex = baseSmallIndex + smallBlock + 1
            if (smallBlockRanks[nextIndex] < localTarget) {
                smallBlock++
            } else {
                break
            }
        }

        val globalSmallIndex = baseSmallIndex + smallBlock
        val offsetInSmallBlock = localTarget - smallBlockRanks[globalSmallIndex]
        val smallStart = bigBlock * BIG_BLOCK_SIZE + smallBlock * SMALL_BLOCK_SIZE

        var count = 0
        for (offset in 0 until SMALL_BLOCK_SIZE) {
            val pos = smallStart + offset
            if (pos >= size) {
                break
            }
            if (bitSet[pos]) {
                count++
                if (count == offsetInSmallBlock) {
                    return pos
                }
            }
        }
        return -1
    }

    fun select0(nodeId: Int): Int {
        val totalZeros = size - totalOnes
        if (nodeId < 1 || nodeId > totalZeros || size == 0) {
            return -1
        }

        var low = 0
        var high = bigBlockRanks.lastIndex
        var bigBlock = 0
        while (low <= high) {
            val mid = (low + high) ushr 1
            val blockStart = mid * BIG_BLOCK_SIZE
            val zerosBefore = blockStart - bigBlockRanks[mid]
            if (zerosBefore < nodeId) {
                bigBlock = mid
                low = mid + 1
            } else {
                high = mid - 1
            }
        }

        val zerosBeforeBlock = bigBlock * BIG_BLOCK_SIZE - bigBlockRanks[bigBlock]
        val localTarget = nodeId - zerosBeforeBlock
        val baseSmallIndex = bigBlock * SMALL_BLOCKS_PER_BIG_BLOCK
        val smallBlocksInThisBig = minOf(
            SMALL_BLOCKS_PER_BIG_BLOCK,
            maxOf(0, smallBlockRanks.size - baseSmallIndex),
        )

        var smallBlock = 0
        while (smallBlock < smallBlocksInThisBig - 1) {
            val nextSmall = smallBlock + 1
            val nextGlobal = baseSmallIndex + nextSmall
            val onesBeforeNextSmall = smallBlockRanks[nextGlobal]
            val bitsBeforeNextSmall = nextSmall * SMALL_BLOCK_SIZE
            val nextZeros = bitsBeforeNextSmall - onesBeforeNextSmall

            if (nextZeros < localTarget) {
                smallBlock++
            } else {
                break
            }
        }

        val globalSmallIndex = baseSmallIndex + smallBlock
        val onesBeforeSmall = smallBlockRanks[globalSmallIndex]
        val bitsBeforeSmall = smallBlock * SMALL_BLOCK_SIZE
        val zerosBeforeSmall = bitsBeforeSmall - onesBeforeSmall
        val offsetInSmallBlock = localTarget - zerosBeforeSmall
        val smallStart = bigBlock * BIG_BLOCK_SIZE + smallBlock * SMALL_BLOCK_SIZE

        var count = 0
        for (offset in 0 until SMALL_BLOCK_SIZE) {
            val pos = smallStart + offset
            if (pos >= size) {
                break
            }
            if (!bitSet[pos]) {
                count++
                if (count == offsetInSmallBlock) {
                    return pos
                }
            }
        }
        return -1
    }

    companion object {
        private const val BIG_BLOCK_SIZE = 256
        private const val SMALL_BLOCK_SIZE = 8
        private const val SMALL_BLOCKS_PER_BIG_BLOCK = BIG_BLOCK_SIZE / SMALL_BLOCK_SIZE
    }
}
