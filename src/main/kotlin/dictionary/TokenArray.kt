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
    var posTable: List<Pair<Short,Short>> = listOf()
    var leftIds: List<Short> = listOf()
    var rightIds: List<Short> = listOf()

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

    fun buildTokenArray(
        dictionaries: Map<String, List<Dictionary>>,
        tangoTrie: LOUDS,
        out: ObjectOutput,
        mode: Int
    ) {
        val posTableWithIndex = readPOSTableWithIndex(mode)

        dictionaries.forEach { (key, dictionaryList) ->
            bitListTemp.add(false)
            dictionaryList.forEach { dictionary ->
                val posIndex = posTableWithIndex[Pair(dictionary.leftId, dictionary.rightId)]
                posIndex?.let { pos ->
                    println("build token array: ${dictionaries.keys.indexOf(key)} $key ${dictionary.tango}")
                    bitListTemp.add(true)
                    posTableIndexList.add(pos.toShort())

                    val wordCost = when(dictionary.tango){
                        "労働組合" -> 3500
                        "飼い" -> 1767
                        "解体" -> 5455
                        "同組合" -> 4500
                        "鹿" -> 3450
                        else -> dictionary.cost
                    }
                    wordCostList.add(wordCost)

                    val nodeId = when {
                        dictionary.yomi == dictionary.tango -> -2
                        key.hiraToKata() == dictionary.tango -> -1
                        else -> tangoTrie.getNodeIndex(dictionary.tango)
                    }
                    nodeIdList.add(nodeId)
                }
            }
        }

        writeExternalNotCompress(out)
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
        nodeIdList.writeToTxt("nodeIds.txt")
        return TokenArray()
    }

    private fun writeExternalNotCompress(
        out: ObjectOutput
    ){
        try {
            out.apply {
                writeObject(posTableIndexList.toShortArray())
                writeObject(wordCostList.toShortArray())
                writeObject(nodeIdList.toIntArray())
                writeObject(bitListTemp.toBitSet())
                flush()
                close()
            }
        }catch (e: IOException){
            println(e.stackTraceToString())
        }
    }

    fun readExternalNotCompress(objectInput: ObjectInput): TokenArray {
        objectInput.apply {
            try {
                posTableIndexList = (readObject() as ShortArray).toMutableList()
                wordCostList = (readObject() as ShortArray).toMutableList()
                nodeIdList = (readObject() as IntArray).toMutableList()
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

        val leftIds2 = mutableListOf<Short>()
        val rightIds2 = mutableListOf<Short>()

        result.forEach {
            leftIds2.add(it.key.first)
            rightIds2.add(it.key.second)
        }

        println("result: ${result.map { it.key }.subList(0,20)} ${result.size}")
        println("left ids: ${leftIds2.subList(0,20)} ${leftIds2.size}")
        println("right ids: ${rightIds2.subList(0,20)} ${rightIds2.size}")

        val objectOutput = if (mode == 0){
            ObjectOutputStream(FileOutputStream("./src/test/resources/pos_table.dat"))
        }else {
            ObjectOutputStream(FileOutputStream("./src/main/resources/pos_table.dat"))
        }
        try {
            objectOutput.apply {
                writeObject(leftIds2.toShortArray())
                writeObject(rightIds2.toShortArray())
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
            ObjectInputStream(BufferedInputStream(FileInputStream("./src/test/resources/pos_table.dat")))
        }else{
            ObjectInputStream(BufferedInputStream(FileInputStream("./src/main/resources/pos_table.dat")))
        }
        objectInput.apply {
            leftIds = (readObject() as ShortArray).toList()
            rightIds = (readObject() as ShortArray).toList()
        }
    }
    /**
     *
     * @param mode 0:test else:main
     *
     **/
    private fun readPOSTableWithIndex(mode: Int): Map<Pair<Short, Short>, Int> {
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