package com.kazumaproject.dictionary

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.hiraToKata
import java.io.File
import java.io.ObjectInputStream

/** The identity belongs to the loaded pack, never to its serialized tokens. */
data class LoadedDictionary(
    val id: String,
    val yomiTrie: LOUDSWithTermId,
    val tangoTrie: LOUDS,
    val tokenArray: TokenArray,
) {
    fun lookup(reading: String): List<DictionaryMatch> {
        val node = yomiTrie.getNodeIndex(reading)
        if (node < 0) return emptyList()
        val term = yomiTrie.getTermId(node)
        if (term < 0) return emptyList()
        return tokenArray.getListDictionaryByYomiTermId(term).map {
            val index = it.posTableIndex.toInt()
            require(index in tokenArray.leftIds.indices) { "Invalid POS index in $id: $index" }
            DictionaryMatch(id, reading, when (it.nodeId) {
                -2 -> reading
                -1 -> reading.hiraToKata()
                else -> tangoTrie.getLetter(it.nodeId)
            }, tokenArray.leftIds[index].toInt(), tokenArray.rightIds[index].toInt(), it.wordCost.toInt())
        }
    }

    fun readings(): Sequence<String> = sequence {
        var node = yomiTrie.isLeaf.nextSetBit(0)
        while (node >= 0) {
            val value = yomiTrie.getLetter(node)
            if (value.isNotEmpty()) yield(value)
            node = yomiTrie.isLeaf.nextSetBit(node + 1)
        }
    }

    companion object {
        fun load(id: String, directory: File, posTable: File = File(directory, "pos_table.dat")): LoadedDictionary {
            fun input(name: String) = ObjectInputStream(File(directory, name).inputStream().buffered())
            val yomi = input("yomi.dat").use { LOUDSWithTermId().readExternalNotCompress(it) }
            val tango = input("tango.dat").use { LOUDS().readExternalNotCompress(it) }
            val tokens = TokenArray().apply {
                input("token.dat").use { readExternalNotCompress(it) }
                readPOSTable(posTable.path)
            }
            return LoadedDictionary(id, yomi, tango, tokens)
        }
    }
}

data class DictionaryMatch(val dictionary: String, val reading: String, val surface: String, val leftId: Int, val rightId: Int, val cost: Int)
