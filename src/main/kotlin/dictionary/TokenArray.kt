package com.kazumaproject.dictionary

import com.kazumaproject.*
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.bitset.SuccinctBitVector
import com.kazumaproject.bitset.rank1
import com.kazumaproject.bitset.select0
import com.kazumaproject.connection_id.deflate
import com.kazumaproject.connection_id.inflate
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.dictionary.models.TokenEntry
import java.io.*
import java.text.Normalizer
import java.util.*

class TokenArray {
    private var posTableIndexList: MutableList<Short> = arrayListOf()
    private var wordCostList: MutableList<Short> = arrayListOf()
    private var nodeIdList: MutableList<Int> = arrayListOf()
    private var bitListTemp: MutableList<Boolean> = arrayListOf()
    private var bitvector: BitSet = BitSet()
    @Transient
    private var postingsSuccinct: SuccinctBitVector? = null
    var posTable: List<Pair<Short, Short>> = listOf()
    var leftIds: List<Short> = listOf()
    var rightIds: List<Short> = listOf()

    fun getListDictionaryByYomiTermId(
        nodeId: Int,
    ): List<TokenEntry> {
        val succinct = postingsSuccinct()
        val b = succinct.rank1(succinct.select0(nodeId))
        val c = succinct.rank1(succinct.select0(nodeId + 1))
        val tempList2 = mutableListOf<TokenEntry>()
        for (i in b..<c) {
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
        mode: Int,
        posTableForBuildPath: String? = null,
    ) {

        val posTableWithIndex = readPOSTableWithIndex(mode, posTableForBuildPath)
        for ((key, dictionaryList) in dictionaries) {
            bitListTemp.add(false)
            for (dictionary in dictionaryList) {
                bitListTemp.add(true)
                val posIndex = posTableWithIndex.getValue(Pair(dictionary.leftId, dictionary.rightId))
                posTableIndexList.add(posIndex.toShort())
                wordCostList.add(dictionary.cost)
                val nodeId = getNodeIdForDictionary(dictionary, tangoTrie, key)
                nodeIdList.add(nodeId)
            }
        }
        writeExternalNotCompress(out)
    }

    private val HIRAGANA_SENTINEL = -2
    private val KATAKANA_SENTINEL = -1

    private fun getNodeIdForDictionary(
        dictionary: Dictionary,
        tangoTrie: LOUDS,
        key: String
    ): Int {
        val surface = Normalizer.normalize(dictionary.tango, Normalizer.Form.NFC)
        return when (surface) {
            key -> HIRAGANA_SENTINEL
            key.hiraToKata() -> KATAKANA_SENTINEL
            else -> tangoTrie.getNodeIndex(surface).also {
                require(it >= 0) { "Surface missing from dictionary trie: $surface ($key)" }
            }
        }
    }

    private fun writeExternal(
        out: ObjectOutput
    ) {
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
        } catch (e: IOException) {
            throw IllegalStateException("Token serialization failed", e)
        }
    }

    fun readExternal(objectInput: ObjectInput): TokenArray {
        objectInput.apply {
            try {
                val posTableIndexListSize = readInt()
                val wordCostListSize = readInt()
                val nodeIdListSize = readInt()

                posTableIndexList =
                    (readObject() as ByteArray).inflate(posTableIndexListSize).byteArrayToShortList().toMutableList()
                wordCostList =
                    (readObject() as ByteArray).inflate(wordCostListSize).byteArrayToShortList().toMutableList()
                nodeIdList = (readObject() as ByteArray).inflate(nodeIdListSize).toListInt().toMutableList()
                bitvector = readObject() as BitSet
                rebuildCache()
                close()
            } catch (e: Exception) {
                throw IllegalStateException("Token serialization failed", e)
            }
        }
        return TokenArray()
    }

    private fun writeExternalNotCompress(
        out: ObjectOutput
    ) {
        try {
            out.apply {
                writeObject(posTableIndexList.toShortArray())
                writeObject(wordCostList.toShortArray())
                writeObject(nodeIdList.toIntArray())
                writeObject(bitListTemp.toBitSet())
                flush()
                close()
            }
        } catch (e: IOException) {
            throw IllegalStateException("Token serialization failed", e)
        }
    }

    fun readExternalNotCompress(objectInput: ObjectInput): TokenArray {
        objectInput.apply {
            try {
                posTableIndexList = (readObject() as ShortArray).toMutableList()
                wordCostList = (readObject() as ShortArray).toMutableList()
                nodeIdList = (readObject() as IntArray).toMutableList()
                bitvector = readObject() as BitSet
                rebuildCache()
                close()
            } catch (e: Exception) {
                throw IllegalStateException("Token serialization failed", e)
            }
        }
        return TokenArray()
    }

    /**
     *
     * @param fileMap dictionary00 ~ dictionary09
     * @param mode file out dist 0:test else:main
     *
     **/
    fun buildPOSTable(
        fileMap: SortedMap<String, List<Dictionary>>,
        mode: Int,
        outputPath: String = defaultPosTablePath(mode),
    ) {
        val tempMap: MutableMap<Pair<Short, Short>, Int> = mutableMapOf()
        var counter = 0 // This will track the incremented values for new pairs

        // Iterate through the map
        fileMap.forEach { (_, dictionaryList) ->
            dictionaryList.forEach { dictionary ->
                val key = Pair(dictionary.leftId, dictionary.rightId)

                // Only assign a value if the key is not already present
                if (key !in tempMap) {
                    tempMap[key] = counter
                    counter++ // Increment the counter only for new pairs
                }
            }
        }

        // Sort the result by value in descending order (optional)
        val result = tempMap.toList().sortedByDescending { (_, value) -> value }.toMap()

        // Separate the left and right IDs into two lists
        val leftIds2 = result.keys.map { it.first }.toShortArray()
        val rightIds2 = result.keys.map { it.second }.toShortArray()

        // Define the output file path based on mode
        // Write the results to the appropriate file using try-with-resources
        try {
            ObjectOutputStream(FileOutputStream(outputPath)).use { objectOutput ->
                objectOutput.writeObject(leftIds2)
                objectOutput.writeObject(rightIds2)
            }
        } catch (e: Exception) {
            throw IllegalStateException("Token serialization failed", e)
        }
    }

    /**
     *
     * @param fileMap dictionary00 ~ dictionary09
     * @param mode file out dist 0:test else:main
     *
     **/
    fun buildPOSTableWithIndex(
        fileMap: SortedMap<String, List<Dictionary>>,
        mode: Int,
        outputPath: String = defaultPosTableForBuildPath(mode),
    ) {
        val tempMap: MutableMap<Pair<Short, Short>, Int> = mutableMapOf()
        var counter = 0 // Initialize a counter to track unique indices

        // Iterate through the map
        fileMap.forEach { (_, dictionaryList) ->
            dictionaryList.forEach { dictionary ->
                val key = Pair(dictionary.leftId, dictionary.rightId)

                // Assign a unique value only if the key is not already present
                if (key !in tempMap) {
                    tempMap[key] = counter
                    counter++ // Increment the counter for new pairs
                }
            }
        }

        // Sort the result by value in descending order (optional)
        val result = tempMap.toList().sortedByDescending { (_, value) -> value }.toMap()

        // Define the output file path based on mode
        // Create a map with index for each pair
        val mapToSave = result.keys.toList().mapIndexed { index, pair -> pair to index }.toMap()

        // Use try-with-resources to ensure file is closed automatically
        try {
            ObjectOutputStream(FileOutputStream(outputPath)).use { objectOutput ->
                objectOutput.writeObject(mapToSave)
            }
        } catch (e: Exception) {
            throw IllegalStateException("Token serialization failed", e)
        }
    }

    /**
     *
     * @param mode 0:test else:main
     *
     **/
    fun readPOSTable(mode: Int) = readPOSTable(defaultPosTablePath(mode))

    fun readPOSTable(path: String) {
        ObjectInputStream(BufferedInputStream(FileInputStream(path))).use {
            leftIds = (it.readObject() as ShortArray).toList()
            rightIds = (it.readObject() as ShortArray).toList()
            require(leftIds.size == rightIds.size) { "Mismatched POS arrays: $path" }
        }
    }

    /**
     *
     * @param mode 0:test else:main
     *
     **/
    private fun readPOSTableWithIndex(
        mode: Int,
        inputPath: String? = null,
    ): Map<Pair<Short, Short>, Int> {
        ObjectInputStream(FileInputStream(inputPath ?: defaultPosTableForBuildPath(mode))).use {
            @Suppress("UNCHECKED_CAST")
            return it.readObject() as Map<Pair<Short, Short>, Int>
        }
    }

    private fun postingsSuccinct(): SuccinctBitVector {
        return postingsSuccinct ?: SuccinctBitVector(bitvector).also { postingsSuccinct = it }
    }

    private fun rebuildCache() {
        postingsSuccinct = SuccinctBitVector(bitvector)
    }

    companion object {
        private fun defaultPosTablePath(mode: Int): String {
            return if (mode == 0) {
                "./src/test/resources/pos_table.dat"
            } else {
                "./src/main/resources/pos_table.dat"
            }
        }

        private fun defaultPosTableForBuildPath(mode: Int): String {
            return if (mode == 0) {
                "./src/test/resources/pos_table_for_build.dat"
            } else {
                "./src/main/resources/pos_table_for_build.dat"
            }
        }
    }

}
