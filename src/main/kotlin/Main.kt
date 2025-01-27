package com.kazumaproject

import com.kazumaproject.Constants.ADDS_NEW_WORDS
import com.kazumaproject.Constants.CUSTOM_LIST
import com.kazumaproject.Constants.DIC_LIST
import com.kazumaproject.Constants.DIFFICULT_LIST
import com.kazumaproject.Constants.DOMAIN
import com.kazumaproject.Constants.ENTERTAIMENT_NAME
import com.kazumaproject.Constants.ERA
import com.kazumaproject.Constants.FIGHT_NAME
import com.kazumaproject.Constants.FIXED_LIST
import com.kazumaproject.Constants.FOOD_NAME
import com.kazumaproject.Constants.NAME_IT_LIST
import com.kazumaproject.Constants.NAME_LIST
import com.kazumaproject.Constants.NAME_MUSIC_LIST
import com.kazumaproject.Constants.PHISIC_NOUN_LIST
import com.kazumaproject.Constants.PLACE
import com.kazumaproject.Constants.RESCORE_WORDS
import com.kazumaproject.Constants.SYMBOL_LIST
import com.kazumaproject.Constants.VERB_LIST
import com.kazumaproject.Constants.WORD
import com.kazumaproject.Constants.ZENKANKU_LIST
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
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
        (dictionaryList +
                DIC_LIST + CUSTOM_LIST +
                NAME_LIST + FIXED_LIST +
                DIFFICULT_LIST + SYMBOL_LIST +
                NAME_MUSIC_LIST + NAME_IT_LIST +
                VERB_LIST + DOMAIN + ERA + PLACE +
                WORD + ZENKANKU_LIST + ADDS_NEW_WORDS + PHISIC_NOUN_LIST
                + FIGHT_NAME + FOOD_NAME + ENTERTAIMENT_NAME + RESCORE_WORDS
                )
            .groupBy { it.yomi }
            .toSortedMap(compareBy({ it.length }, { it }))

    println("finalList size: ${finalList.size}")

    buildConnectionIds()
    buildPOSTable(finalList)

}

private fun buildConnectionIds() {
    val lines = object {}::class.java.getResourceAsStream("/connection_single_column.txt")
        ?.bufferedReader()
        ?.readLines()

    val connectionIdBuilder = ConnectionIdBuilder()
    lines?.let { l ->
        // Skip the first line and convert the remaining lines to Short
        val connectionIds = l.drop(1).map { line ->
            line.toShort()
        }.toShortArray()
        println("connectionID size: ${connectionIds.size}")
        connectionIdBuilder.writeShortArrayAsBytes(
            connectionIds,
            "./src/main/resources/connectionId.dat",
        )
    }
}

private fun buildPOSTable(finalList: SortedMap<String, List<Dictionary>>) {
    val tokenArray = TokenArray()
    tokenArray.buildPOSTable(finalList, 1)
    tokenArray.buildPOSTableWithIndex(finalList, 1)
}

