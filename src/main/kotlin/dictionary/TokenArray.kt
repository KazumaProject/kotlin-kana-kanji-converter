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
    private var posTableIndexList: ShortArray = shortArrayOf()
    private var wordCostList: ShortArray = shortArrayOf()
    private var nodeIdList: IntArray = intArrayOf()
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
        yomiTermIdResolver: ((String) -> Int)? = null,
    ) {

        val posTableWithIndex = readPOSTableWithIndex(mode, posTableForBuildPath)
        val orderedEntries = orderDictionaryEntries(dictionaries, yomiTermIdResolver)
        val entryCount = orderedEntries.sumOf { it.value.size }
        val posTableIndexBuilder = ShortArray(entryCount)
        val wordCostBuilder = ShortArray(entryCount)
        val nodeIdBuilder = IntArray(entryCount)
        val bitvectorBuilder = BitSet()
        var tokenIndex = 0
        var bitIndex = 0

        for ((key, dictionaryList) in orderedEntries) {
            bitIndex += 1
            for (dictionary in dictionaryList) {
                bitvectorBuilder.set(bitIndex)
                bitIndex += 1
                val posIndex = posTableWithIndex.getValue(Pair(dictionary.leftId, dictionary.rightId))
                posTableIndexBuilder[tokenIndex] = posIndex.toShort()
                wordCostBuilder[tokenIndex] = dictionary.cost
                val nodeId = getNodeIdForDictionary(dictionary, tangoTrie, key)
                nodeIdBuilder[tokenIndex] = nodeId
                tokenIndex += 1
            }
        }

        posTableIndexList = posTableIndexBuilder
        wordCostList = wordCostBuilder
        nodeIdList = nodeIdBuilder
        bitvector = bitvectorBuilder
        writeExternalNotCompress(out)
    }

    private fun orderDictionaryEntries(
        dictionaries: Map<String, List<Dictionary>>,
        yomiTermIdResolver: ((String) -> Int)?,
    ): List<Map.Entry<String, List<Dictionary>>> {
        val entries = dictionaries.entries.toList()
        if (yomiTermIdResolver == null) return entries

        val entriesWithTermIds = entries.map { entry ->
            val termId = yomiTermIdResolver(entry.key)
            require(termId > 0) {
                "Invalid yomi term id: yomi=${entry.key}, termId=$termId"
            }
            entry to termId
        }.sortedBy { it.second }

        entriesWithTermIds.forEachIndexed { index, (_, termId) ->
            require(termId == index + 1) {
                "Yomi term ids must be contiguous and 1-based: expected=${index + 1}, actual=$termId"
            }
        }

        return entriesWithTermIds.map { it.first }
    }

    private fun getNodeIdForDictionary(
        dictionary: Dictionary,
        tangoTrie: LOUDS,
        key: String // 使わない（判定には不要）
    ): Int {
        val t = dictionary.tango

        // まず「かなだけ」かどうかを判定（あなたの Pure 系ユーティリティを採用）
        return when {
            key == t -> HIRAGANA_SENTINEL
            t.isHiraganaOnlyPure() -> HIRAGANA_SENTINEL
            t.isKatakanaOnlyPure() -> KATAKANA_SENTINEL
            else -> {
                val normalized = Normalizer.normalize(t, Normalizer.Form.NFC)
                tangoTrie.getNodeIndex(normalized)
            }
        }
    }

    private fun writeExternal(
        out: ObjectOutput
    ) {
        try {
            out.apply {
                val posTableIndexBytes = posTableIndexList.toByteArray()
                val wordCostBytes = wordCostList.toByteArray()
                val nodeIdBytes = nodeIdList.toByteArray()
                writeInt(posTableIndexBytes.size)
                writeInt(wordCostBytes.size)
                writeInt(nodeIdBytes.size)

                writeObject(posTableIndexBytes.deflate())
                writeObject(wordCostBytes.deflate())
                writeObject(nodeIdBytes.deflate())
                writeObject(bitvector)

                flush()
                close()
            }
        } catch (e: IOException) {
            println(e.stackTraceToString())
        }
    }

    fun readExternal(objectInput: ObjectInput): TokenArray {
        objectInput.apply {
            try {
                val posTableIndexListSize = readInt()
                val wordCostListSize = readInt()
                val nodeIdListSize = readInt()

                posTableIndexList =
                    (readObject() as ByteArray).inflate(posTableIndexListSize).toShortArray()
                wordCostList =
                    (readObject() as ByteArray).inflate(wordCostListSize).toShortArray()
                nodeIdList = (readObject() as ByteArray).inflate(nodeIdListSize).toListInt().toIntArray()
                bitvector = readObject() as BitSet
                requireConsistentArraySizes()
                rebuildCache()
                close()
            } catch (e: Exception) {
                println(e.stackTraceToString())
            }
        }
        return this
    }

    private fun writeExternalNotCompress(
        out: ObjectOutput
    ) {
        try {
            out.apply {
                writeObject(posTableIndexList)
                writeObject(wordCostList)
                writeObject(encodeNodeIds(nodeIdList))
                writeObject(bitvector)
                flush()
                close()
            }
        } catch (e: IOException) {
            println(e.stackTraceToString())
        }
    }

    fun readExternalNotCompress(objectInput: ObjectInput): TokenArray {
        objectInput.apply {
            try {
                posTableIndexList = readObject() as ShortArray
                wordCostList = readObject() as ShortArray
                val nodeIdsObject = readObject()
                nodeIdList = when (nodeIdsObject) {
                    is IntArray -> nodeIdsObject
                    is ByteArray -> decodeNodeIds(nodeIdsObject, posTableIndexList.size)
                    else -> error("Unsupported nodeIdList payload: ${nodeIdsObject::class.qualifiedName}")
                }
                bitvector = readObject() as BitSet
                requireConsistentArraySizes()
                rebuildCache()
                close()
            } catch (e: Exception) {
                println(e.stackTraceToString())
            }
        }
        return this
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
            println(e.stackTraceToString())
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
            println(e.stackTraceToString())
        }
    }

    /**
     *
     * @param mode 0:test else:main
     *
     **/
    fun readPOSTable(mode: Int) {
        val objectInput = ObjectInputStream(BufferedInputStream(FileInputStream(defaultPosTablePath(mode))))
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
    private fun readPOSTableWithIndex(
        mode: Int,
        inputPath: String? = null,
    ): Map<Pair<Short, Short>, Int> {
        val objectInput = ObjectInputStream(FileInputStream(inputPath ?: defaultPosTableForBuildPath(mode)))
        var a: Map<Pair<Short, Short>, Int>
        objectInput.apply {
            a = (readObject() as Map<Pair<Short, Short>, Int>)
        }
        return a
    }

    private fun postingsSuccinct(): SuccinctBitVector {
        return postingsSuccinct ?: SuccinctBitVector(bitvector).also { postingsSuccinct = it }
    }

    private fun rebuildCache() {
        postingsSuccinct = SuccinctBitVector(bitvector)
    }

    private fun requireConsistentArraySizes() {
        require(posTableIndexList.size == wordCostList.size && wordCostList.size == nodeIdList.size) {
            "Invalid token array sizes: posTableIndex=${posTableIndexList.size}, " +
                    "wordCost=${wordCostList.size}, nodeId=${nodeIdList.size}"
        }
    }

    companion object {
        private const val HIRAGANA_SENTINEL = -2
        private const val KATAKANA_SENTINEL = -1
        private const val HIRAGANA_NODE_CODE = 0
        private const val KATAKANA_NODE_CODE = 1
        private const val NODE_ID_OFFSET = 2

        private fun encodeNodeIds(nodeIds: IntArray): ByteArray {
            val out = ByteArrayOutputStream(nodeIds.size)
            nodeIds.forEach { nodeId ->
                val encoded = when (nodeId) {
                    HIRAGANA_SENTINEL -> HIRAGANA_NODE_CODE
                    KATAKANA_SENTINEL -> KATAKANA_NODE_CODE
                    else -> {
                        require(nodeId >= 0) { "Unsupported negative node id: $nodeId" }
                        nodeId + NODE_ID_OFFSET
                    }
                }
                writeUnsignedVarInt(out, encoded)
            }
            return out.toByteArray()
        }

        private fun decodeNodeIds(bytes: ByteArray, expectedCount: Int): IntArray {
            val decoded = IntArray(expectedCount)
            var index = 0
            var offset = 0
            while (offset < bytes.size) {
                require(index < expectedCount) {
                    "Too many node ids in payload: expected=$expectedCount"
                }
                var shift = 0
                var value = 0
                while (true) {
                    require(offset < bytes.size) { "Truncated node id varint payload" }
                    val byteValue = bytes[offset].toInt() and 0xFF
                    offset += 1
                    value = value or ((byteValue and 0x7F) shl shift)
                    if ((byteValue and 0x80) == 0) break
                    shift += 7
                    require(shift <= 28) { "Node id varint is too large" }
                }
                decoded[index] = when (value) {
                    HIRAGANA_NODE_CODE -> HIRAGANA_SENTINEL
                    KATAKANA_NODE_CODE -> KATAKANA_SENTINEL
                    else -> value - NODE_ID_OFFSET
                }
                index += 1
            }
            require(index == expectedCount) {
                "Too few node ids in payload: expected=$expectedCount, actual=$index"
            }
            return decoded
        }

        private fun writeUnsignedVarInt(out: ByteArrayOutputStream, value: Int) {
            var current = value
            while ((current and 0x7F.inv()) != 0) {
                out.write((current and 0x7F) or 0x80)
                current = current ushr 7
            }
            out.write(current)
        }

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
