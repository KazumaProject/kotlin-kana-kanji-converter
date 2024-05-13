package com.kazumaproject.dictionary

import com.kazumaproject.*
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.bitset.rank1
import com.kazumaproject.bitset.select0
import com.kazumaproject.connection_id.deflate
import com.kazumaproject.connection_id.inflate
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.dictionary.models.TokenEntry
import java.io.*
import java.util.*

class TokenArray {
    private var posTableIndexList: MutableList<Short> = arrayListOf()
    private var wordCostList: MutableList<Short> = arrayListOf()
    private var nodeIdList: MutableList<Int> = arrayListOf()
    private var bitListTemp: MutableList<Boolean> = arrayListOf()
    private var bitvector: BitSet = BitSet()
    var posTable: List<Pair<Short, Short>> = listOf()
    
    fun getListDictionaryByYomiTermId(
        nodeId: Int,
    ): List<TokenEntry> {
        val b = bitvector.rank1(bitvector.select0(nodeId))
        val c = bitvector.rank1(bitvector.select0(nodeId + 1))
        val tempList2 = mutableListOf<TokenEntry>()
        for (i in b..< c){
            tempList2.add(
                TokenEntry(
                    posTableIndex = posTableIndexList[i],
                    wordCost = wordCostList[i],
                    nodeId = nodeIdList[i],
                )
            )
        }
        return tempList2
    }

    fun buildJunctionArray(
        dictionaries: MutableList<Dictionary>,
        tangoTrie: LOUDS,
        out: ObjectOutput,
        mode: Int
    ){
        val posTableWithIndex = readPOSTableWithIndex(mode)
        dictionaries.sortedBy { it.yomi.length } .groupBy { it.yomi }.onEachIndexed{ index, entry ->
            bitListTemp.add(false)

            entry.value.forEach { dictionary ->
                val key = Pair(dictionary.leftId, dictionary.rightId)
                val posIndex = posTableWithIndex[key]
                posIndex?.let {
                    println("build token array:$index ${entry.key} ${dictionary.tango}")
                    val posTableIndex = it.toShort()
                    bitListTemp.add(true)
                    posTableIndexList.add(posTableIndex)
                    wordCostList.add(dictionary.cost)
                    nodeIdList.add(if (dictionary.yomi == dictionary.tango || entry.key.hiraToKata() == dictionary.tango) -1 else tangoTrie.getNodeIndex(dictionary.tango))
                }
            }
        }
        writeExternal(out)
    }

    private fun writeExternal(
        out: ObjectOutput
    ){
        try {
            out.apply {
                writeInt(posTableIndexList.toByteArrayFromListShort().size)
                writeInt(wordCostList.toByteArrayFromListShort().size)
                writeInt(nodeIdList.toByteArray().size)

                writeObject(posTableIndexList.toByteArrayFromListShort().deflate())
                writeObject(wordCostList.toByteArrayFromListShort().deflate())
                writeObject(nodeIdList.toByteArray().deflate())
                writeObject(bitListTemp.toBitSet())

                flush()
                close()
            }
        }catch (e: IOException){
            println(e.stackTraceToString())
        }
    }

    fun readExternal(objectInput: ObjectInput): TokenArray {
        objectInput.apply {
            try {
                val posTableIndexListSize = readInt()
                val wordCostListSize = readInt()
                val nodeIdListSize = readInt()

                posTableIndexList = (readObject() as ByteArray).inflate(posTableIndexListSize).byteArrayToShortList().toMutableList()
                wordCostList = (readObject() as ByteArray).inflate(wordCostListSize).byteArrayToShortList().toMutableList()
                nodeIdList = (readObject() as ByteArray).inflate(nodeIdListSize).toListInt().toMutableList()
                bitvector = readObject() as BitSet
                close()
            }catch (e: Exception){
                println(e.stackTraceToString())
            }
        }
        return TokenArray()
    }

    /**
     *
     * @param fileList dictionary00 ~ dictionary09
     * @param mode file out dist 0:test else:main
     *
     **/
    fun buildPOSTable(
        fileList: List<String>,
        mode: Int
    ){
        val tempMap: MutableMap<Pair<Short,Short>,Int> = mutableMapOf()
        fileList.forEach {
            val line = this::class.java.getResourceAsStream(it)
                ?.bufferedReader()
                ?.readLines()
            line?.forEach { str ->
                str.apply {
                    val leftId = split("\\t".toRegex())[1]
                    val rightId = split("\\t".toRegex())[2]
                    if (tempMap[Pair(leftId.toShort(),rightId.toShort())] == null){
                        tempMap[Pair(leftId.toShort(),rightId.toShort())] = 0
                    }else{
                        tempMap[Pair(leftId.toShort(),rightId.toShort())] = (tempMap[Pair(leftId.toShort(),rightId.toShort())]!!) + 1
                    }
                }
            }
        }

        val result = tempMap.toList().sortedByDescending { (_, value) -> value }.toMap()
        val objectOutput = if (mode == 0){
            ObjectOutputStream(FileOutputStream("./src/test/resources/pos_table.dat"))
        }else {
            ObjectOutputStream(FileOutputStream("./src/main/resources/pos_table.dat"))
        }
        val objectToWrite = result.keys.toList()
        try {
            objectOutput.apply {
                writeObject(objectToWrite)
                flush()
                close()
            }
        }catch (e: Exception){
            println(e.stackTraceToString())
        }
    }

    /**
     *
     * @param fileList dictionary00 ~ dictionary09
     * @param mode file out dist 0:test else:main
     *
     **/
    fun buildPOSTableWithIndex(
        fileList: List<String>,
        mode: Int
    ){
        val tempMap: MutableMap<Pair<Short,Short>,Int> = mutableMapOf()
        fileList.forEach {
            val line = this::class.java.getResourceAsStream(it)
                ?.bufferedReader()
                ?.readLines()
            line?.forEach { str ->
                str.apply {
                    val leftId = split("\\t".toRegex())[1]
                    val rightId = split("\\t".toRegex())[2]
                    if (tempMap[Pair(leftId.toShort(),rightId.toShort())] == null){
                        tempMap[Pair(leftId.toShort(),rightId.toShort())] = 0
                    }else{
                        tempMap[Pair(leftId.toShort(),rightId.toShort())] = (tempMap[Pair(leftId.toShort(),rightId.toShort())]!!) + 1
                    }
                }
            }
        }

        val result = tempMap.toList().sortedByDescending { (_, value) -> value }.toMap()
        val objectOutput = if (mode == 0){
            ObjectOutputStream(FileOutputStream("./src/test/resources/pos_table_for_build.dat"))
        }else{
            ObjectOutputStream(FileOutputStream("./src/main/resources/pos_table_for_build.dat"))
        }
        val mapToSave = result.keys.toList().mapIndexed { index, pair -> pair to index  }.toMap()
        try {
            objectOutput.apply {
                writeObject(mapToSave)
                flush()
                close()
            }
        }catch (e: Exception){
            println(e.stackTraceToString())
        }
    }

    /**
     *
     * @param mode 0:test else:main
     *
     **/
    fun readPOSTable(mode: Int) {
        val objectInput = if (mode == 0){
            ObjectInputStream(FileInputStream("./src/test/resources/pos_table.dat"))
        }else{
            ObjectInputStream(FileInputStream("./src/main/resources/pos_table.dat"))
        }
        var a: List<Pair<Short,Short>>
        objectInput.apply {
            a = (readObject() as List<Pair<Short,Short>>)
        }
        posTable = a
    }
    /**
     *
     * @param mode 0:test else:main
     *
     **/
    fun readPOSTableWithIndex(mode: Int): Map<Pair<Short, Short>, Int> {
        val objectInput = if (mode == 0){
            ObjectInputStream(FileInputStream("./src/test/resources/pos_table_for_build.dat"))
        }else{
            ObjectInputStream(FileInputStream("./src/main/resources/pos_table_for_build.dat"))
        }
        var a:  Map<Pair<Short, Short>, Int>
        objectInput.apply {
            a = (readObject() as Map<Pair<Short, Short>, Int>)
        }
        return a
    }

}