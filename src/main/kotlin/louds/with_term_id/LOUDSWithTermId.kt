package com.kazumaproject.Louds.with_term_id

import com.kazumaproject.*
import com.kazumaproject.bitset.SuccinctBitVector
import com.kazumaproject.bitset.rank0
import com.kazumaproject.bitset.rank1
import com.kazumaproject.bitset.select0
import com.kazumaproject.bitset.select1
import com.kazumaproject.connection_id.deflate
import com.kazumaproject.connection_id.inflate
import java.io.*
import java.util.*

class LOUDSWithTermId {

    val LBSTemp: MutableList<Boolean> = arrayListOf()
    var LBS: BitSet = BitSet()
    var labels: MutableList<Char> = arrayListOf()
    var termIds: MutableList<Int> = arrayListOf()
    var termIdsSave: IntArray = intArrayOf()
    var isLeaf: BitSet = BitSet()
    val isLeafTemp: MutableList<Boolean> = arrayListOf()
    @Transient
    private var lbsSuccinct: SuccinctBitVector? = null
    @Transient
    private var isLeafSuccinct: SuccinctBitVector? = null

    init {
        LBSTemp.apply {
            add(true)
            add(false)
        }
        labels.apply {
            add(0,' ')
            add(1,' ')
        }
        isLeafTemp.apply {
            add(0,false)
            add(1,false)
        }
    }

    constructor()


    constructor(
        LBS: BitSet,
        labels: MutableList<Char>,
        isLeaf: BitSet,
        termIds: IntArray,
    ){
        this.LBS = LBS
        this.labels = labels
        this.isLeaf = isLeaf
        this.termIdsSave = termIds
        rebuildCache()
    }

    fun convertListToBitSet(){
        LBS = LBSTemp.toBitSet()
        LBSTemp.clear()
        isLeaf = isLeafTemp.toBitSet()
        isLeafTemp.clear()
        rebuildCache()
    }

    fun getLetter(nodeIndex: Int): String {
        val succinct = lbsSuccinct()
        val list = mutableListOf<Char>()
        val firstNodeId = succinct.rank1(nodeIndex)
        val firstChar = labels[firstNodeId]
        list.add(firstChar)
        var parentNodeIndex = succinct.select1(succinct.rank0(nodeIndex))
        while (parentNodeIndex != 0){
            val parentNodeId = succinct.rank1(parentNodeIndex)
            val pair = labels[parentNodeId]
            list.add(pair)
            parentNodeIndex = succinct.select1(succinct.rank0(parentNodeIndex))
            if (parentNodeId == 0) return ""
        }
        return list.toList().reversed().joinToString("")
    }

    fun getLetterByNodeId(nodeId: Int): String {
        val succinct = lbsSuccinct()
        val list = mutableListOf<Char>()
        var parentNodeIndex = succinct.select1(nodeId)
        while (parentNodeIndex != 0){
            val parentNodeId = succinct.rank1(parentNodeIndex)
            val pair = labels[parentNodeId]
            list.add(pair)
            parentNodeIndex = succinct.select1(succinct.rank0(parentNodeIndex))
        }
        return list.toList().reversed().joinToString("")
    }

    fun getNodeIndex(s: String): Int{
        return search(2, s.toCharArray(), 0)
    }

    fun getNodeId(s: String): Int{
        return lbsSuccinct().rank0(getNodeIndex(s))
    }

    fun getTermId(nodeIndex: Int): Int {
        val firstNodeId = isLeafSuccinct().rank1(nodeIndex) - 1
        if (firstNodeId < 0) return -1

        //val firstTermId = termIds[firstNodeId]
        val firstTermId = termIdsSave[firstNodeId]
        return firstTermId
    }

    private fun firstChild(pos: Int): Int {
        val succinct = lbsSuccinct()
        val y = succinct.select0(succinct.rank1(pos)) + 1
        return if (y < 0 || !LBS[y]) -1 else y
    }

    private fun traverse(pos: Int, c: Char): Int {
        val succinct = lbsSuccinct()
        var childPos = firstChild(pos)
        if (childPos == -1) return -1
        while (LBS[childPos]){
            if (c == labels[succinct.rank1(childPos)]) {
                return childPos
            }
            childPos += 1
        }
        return -1
    }

    fun commonPrefixSearch(str: String): List<String> {
        val succinct = lbsSuccinct()
        val resultTemp: MutableList<Char> = mutableListOf()
        val result: MutableList<String> = mutableListOf()
        var n = 0
        str.forEachIndexed { _, c ->
            n = traverse(n, c)
            val index = succinct.rank1(n)
            if (n == -1) return@forEachIndexed
            if (index >= labels.size) return result
            resultTemp.add(labels[index])
            if (isLeaf[n]){
                val tempStr = resultTemp.joinToString("")
                if (result.size >= 1){
                    val resultStr = result[0] + tempStr
                    result.add(resultStr)
                }else {
                    result.add(tempStr)
                    resultTemp.clear()
                }
            }
        }
        return result.toList()
    }

    private fun search(index: Int, chars: CharArray, wordOffset: Int): Int {
        val succinct = lbsSuccinct()
        var index2 = index
        var wordOffset2 = wordOffset
        var charIndex = succinct.rank1(index2)
        while (LBS[index2]) {
            if (chars[wordOffset2] == labels[charIndex]) {
                if (isLeaf[index2] && wordOffset2 + 1 == chars.size) {
                    return index2
                } else if (wordOffset2 + 1 == chars.size) {
                    return index2
                }
                return search(succinct.select0(charIndex) + 1, chars, ++wordOffset2)
            } else {
                index2++
            }
            charIndex++
        }
        return -1
    }

    private fun lbsSuccinct(): SuccinctBitVector {
        return lbsSuccinct ?: SuccinctBitVector(LBS).also { lbsSuccinct = it }
    }

    private fun isLeafSuccinct(): SuccinctBitVector {
        return isLeafSuccinct ?: SuccinctBitVector(isLeaf).also { isLeafSuccinct = it }
    }

    private fun rebuildCache() {
        lbsSuccinct = SuccinctBitVector(LBS)
        isLeafSuccinct = SuccinctBitVector(isLeaf)
    }

    fun writeExternal(out: ObjectOutput){
        try {
            out.apply {
                writeInt(labels.toByteArrayFromListChar().size)
                writeInt(termIds.toByteArray().size)

                writeObject(LBS)
                writeObject(isLeaf)
                writeObject(labels.toByteArrayFromListChar().deflate())
                writeObject(termIds.toByteArray().deflate())
                flush()
                close()
            }
        }catch (e: IOException){
            println(e.stackTraceToString())
        }
    }

    fun readExternal(objectInput: ObjectInput): LOUDSWithTermId {
        objectInput.apply {
            try {
                val labelsSize = objectInput.readInt()
                val termIdSize = objectInput.readInt()
                LBS = objectInput.readObject() as BitSet
                isLeaf = objectInput.readObject() as BitSet
                labels = (objectInput.readObject() as ByteArray).inflate(labelsSize).toListChar()
                termIds = (objectInput.readObject() as ByteArray).inflate(termIdSize).toListInt().toMutableList()
                rebuildCache()
                close()
            }catch (e: Exception){
                println(e.stackTraceToString())
            }
        }
        return LOUDSWithTermId()
    }

    fun writeExternalNotCompress(out: ObjectOutput){
        try {
            out.apply {
                writeObject(LBS)
                writeObject(isLeaf)
                writeObject(labels.toCharArray())
                writeObject(termIds.toIntArray())
                flush()
                close()
            }
        }catch (e: IOException){
            println(e.stackTraceToString())
        }
    }

    fun readExternalNotCompress(objectInput: ObjectInput): LOUDSWithTermId {
        objectInput.apply {
            try {
                LBS = objectInput.readObject() as BitSet
                isLeaf = objectInput.readObject() as BitSet
                labels = (objectInput.readObject() as CharArray).toMutableList()
                termIdsSave = (objectInput.readObject() as IntArray)
                rebuildCache()
                close()
            }catch (e: Exception){
                println(e.stackTraceToString())
            }
        }
        return LOUDSWithTermId(LBS, labels, isLeaf, termIdsSave)
    }

}
