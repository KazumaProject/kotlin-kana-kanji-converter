package com.kazumaproject.fid

import com.kazumaproject.addToPrevious
import com.kazumaproject.cumulativeSum
import com.kazumaproject.toBitSet
import com.kazumaproject.toBooleanList
import java.util.*
import kotlin.math.log

class FullyIndexedDictionary(private val bitSet: BitSet) {

    private lateinit var L: List<BitSet>
    private lateinit var S: List<List<List<Boolean>>>
    private lateinit var LCount: List<Int>
    private lateinit var SCount: List<Int>
    private var lgn: Int = 0

    fun createAuxData(){
        val bigBlocksSizeTemp = log(bitSet.size().toDouble(),(2).toDouble())
        val l = bigBlocksSizeTemp * bigBlocksSizeTemp
        val s = (bigBlocksSizeTemp / 2)
        val bigBlocks = bitSet.toBooleanList().chunked(l.toInt()).map { it.toBitSet() }
        val bigBlockCount = cumulativeSum(listOf(0) + bitSet.toBooleanList().chunked(l.toInt()).map { it.count { a -> a } })

        val smallBlocks = bitSet.toBooleanList().chunked(l.toInt()).map { it.chunked(s.toInt()) }
        val smallBlocksCount = addToPrevious(listOf(0) + bitSet.toBooleanList().chunked(s.toInt()).map { it.count { a -> a } },s.toInt())

        println("bitset: ${bitSet.size()}")
        println("bigBlocksSizeTemp: $bigBlocksSizeTemp")
        println("l: $l")
        println("s: $s")

        println("$bigBlocks")
        println("${smallBlocks}")

        println("$bigBlockCount")
        println("$smallBlocksCount")
        println("a a ${smallBlocksCount[28]}")

        L = bigBlocks
        S = smallBlocks
        LCount = bigBlockCount
        SCount = smallBlocksCount
        lgn = bigBlocksSizeTemp.toInt()

    }

    fun rank1(index: Int){
        val l = index / (lgn * lgn)
        val s = index / (lgn / 2)
        val first = LCount[l]
        val second = SCount[s]
        val third = S[s].zip(listOf(true,true,false,false)){ o, m -> o.map { it && m } }.flatten()

        println("$first $second")
        println("$third")
        println("$l $s")
        println("rank1: ${first + second + third.count { it }}")
    }

}