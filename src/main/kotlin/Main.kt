package com.kazumaproject

import com.kazumaproject.Constants.CUSTOM_LIST
import com.kazumaproject.Constants.DIC_LIST
import com.kazumaproject.Constants.DIFFICULT_LIST
import com.kazumaproject.Constants.DOMAIN
import com.kazumaproject.Constants.ERA
import com.kazumaproject.Constants.FIXED_LIST
import com.kazumaproject.Constants.NAME_IT_LIST
import com.kazumaproject.Constants.NAME_LIST
import com.kazumaproject.Constants.NAME_MUSIC_LIST
import com.kazumaproject.Constants.PLACE
import com.kazumaproject.Constants.PROVERB_LIST
import com.kazumaproject.Constants.SYMBOL_LIST
import com.kazumaproject.Constants.WORD
import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.io.*
import java.util.*

fun main() {
    val fileList: List<String> = listOf(
        "/dictionary00.txt",
        "/dictionary01.txt",
        "/dictionary02.txt",
        "/dictionary03.txt",
        "/dictionary04.txt",
        "/dictionary05.txt",
        "/dictionary06.txt",
        "/dictionary07.txt",
        "/dictionary08.txt",
        "/dictionary09.txt",
        "/suffix.txt",
    )
    val dicUtils = DicUtils()
    val dictionaryList = dicUtils.getListDictionary(fileList).toMutableList()
    val finalList =
        (dictionaryList + DIC_LIST + CUSTOM_LIST + NAME_LIST + FIXED_LIST + DIFFICULT_LIST + SYMBOL_LIST + NAME_MUSIC_LIST + NAME_IT_LIST + PROVERB_LIST + DOMAIN + ERA + PLACE + WORD)
            .groupBy { it.yomi }
            .toSortedMap(compareBy({ it.length }, { it }))

    buildConnectionIds()
    buildPOSTable(finalList)
    buildTriesAndTokenArray(finalList)
    buildDictionaryForSingleKanji()
}

private fun buildPOSTable(finalList: SortedMap<String, List<Dictionary>>) {
    val tokenArray = TokenArray()
    tokenArray.buildPOSTable(finalList, 1)
    tokenArray.buildPOSTableWithIndex(finalList, 1)
}

private fun buildTriesAndTokenArray(finalList: SortedMap<String, List<Dictionary>>) {

    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    for (entry in finalList.entries) {
        yomiTree.insert(entry.key)
        for (dictionary in entry.value) {
            if (!dictionary.tango.isHiraganaOrKatakana()) {
                tangoTree.insert(dictionary.tango)
            }
        }
    }

    val yomiLOUDSTemp = ConverterWithTermId().convert(yomiTree.root)
    val tangoLOUDSTemp = Converter().convert(tangoTree.root)
    yomiLOUDSTemp.convertListToBitSet()
    tangoLOUDSTemp.convertListToBitSet()

    val objectOutputYomi = ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/yomi.dat")))
    val objectOutputTango = ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/tango.dat")))

    yomiLOUDSTemp.writeExternalNotCompress(objectOutputYomi)
    tangoLOUDSTemp.writeExternalNotCompress(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango.dat"))

    LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    val tangoLOUDS: LOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    val tokenArrayTemp = TokenArray()
    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token.dat"))
    tokenArrayTemp.buildTokenArray(finalList, tangoLOUDS, objectOutput, 1)
    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token.dat"))
    val tokenArray = TokenArray()
    tokenArray.readExternalNotCompress(objectInput)
    tokenArray.readPOSTable(1)
}

private fun buildConnectionIds() {
    val lines = object {}::class.java.getResourceAsStream("/connection_single_column.txt")
        ?.bufferedReader()
        ?.readLines()

    val connectionIdBuilder = ConnectionIdBuilder()
    lines?.let { l ->
        // Skip the first line and convert the remaining lines to Short
        val connectionIds = l.drop(1).mapNotNull { line ->
            line.toShortOrNull() // Safely converts to Short, returns null if conversion fails
        }.toShortArray()

        connectionIdBuilder.writeShortArrayAsBytes(
            connectionIds,
            "./src/main/resources/connectionId.dat",
        )
    }
}

private fun buildDictionaryForSingleKanji() {
    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    val dicUtils = DicUtils()

    val dictionaryList = dicUtils.getSingleKanjiListDictionary("/single_kanji.tsv")
        .sortedBy { it.yomi }
        .sortedBy { it.yomi.length }
        .groupBy { it.yomi }

    dictionaryList
        .forEach { entry ->
            yomiTree.insert(entry.key)
            entry.value.forEach {
                tangoTree.insert(it.tango)
            }
        }

    val yomiLOUDSTemp = ConverterWithTermId().convert(yomiTree.root)
    val tangoLOUDSTemp = Converter().convert(tangoTree.root)
    yomiLOUDSTemp.convertListToBitSet()
    tangoLOUDSTemp.convertListToBitSet()

    val objectOutputYomi =
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/yomi_singleKanji.dat")))
    val objectOutputTango =
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/tango_singleKanji.dat")))

    yomiLOUDSTemp.writeExternalNotCompress(objectOutputYomi)
    tangoLOUDSTemp.writeExternalNotCompress(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi_singleKanji.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango_singleKanji.dat"))

    LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    val tangoLOUDS: LOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    val tokenArrayTemp = TokenArray()
    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token_singleKanji.dat"))
    tokenArrayTemp.buildTokenArray(dictionaryList, tangoLOUDS, objectOutput, 1)
    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token_singleKanji.dat"))
    val tokenArray = TokenArray()
    tokenArray.readExternalNotCompress(objectInput)
    tokenArray.readPOSTable(1)
}
