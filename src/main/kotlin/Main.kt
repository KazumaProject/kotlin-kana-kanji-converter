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
import com.kazumaproject.Constants.WORDS
import com.kazumaproject.Constants.ZENKANKU_LIST
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.emoji.EmojiDictionaryBuilder
import com.kazumaproject.emoticon.EmoticonDictionaryBuilder
import com.kazumaproject.reading_correction.ReadingCorrectionBuilder
import com.kazumaproject.symbol.SymbolDictionaryBuilder
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
        (dictionaryList +
                DIC_LIST + CUSTOM_LIST +
                NAME_LIST + FIXED_LIST +
                DIFFICULT_LIST + SYMBOL_LIST +
                NAME_MUSIC_LIST + NAME_IT_LIST +
                VERB_LIST + DOMAIN + ERA + PLACE +
                WORDS + ZENKANKU_LIST + ADDS_NEW_WORDS + PHISIC_NOUN_LIST
                + FIGHT_NAME + FOOD_NAME + ENTERTAIMENT_NAME + RESCORE_WORDS
                )
            .groupBy { it.yomi }
            .toSortedMap(compareBy({ it.length }, { it }))

    println("finalList size: ${finalList.size}")

    buildConnectionIds()
    buildPOSTable(finalList)
    buildTriesAndTokenArray(finalList)
    buildDictionaryForSingleKanji()
    buildDictionaryForEmoji()
    buildDictionaryForEmoticon()
    buildDictionaryForSymbol()
    buildDictionaryForReadingCorrection()
    buildDictionaryForKotowaza()
}

private fun buildPOSTable(finalList: SortedMap<String, List<Dictionary>>) {
    val tokenArray = TokenArray()
    tokenArray.buildPOSTable(finalList, 1)
    tokenArray.buildPOSTableWithIndex(finalList, 1)
}

private fun buildTriesAndTokenArray(finalList: SortedMap<String, List<Dictionary>>) {
    buildAndWriteDictionaryArtifacts(
        dictionaryList = finalList,
        yomiOutputPath = "./src/main/resources/yomi.dat",
        tangoOutputPath = "./src/main/resources/tango.dat",
        tokenOutputPath = "./src/main/resources/token.dat",
        mode = 1,
        skipKanaOnlyTango = true,
    )
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

private fun buildDictionaryForSingleKanji() {
    val dicUtils = DicUtils()

    val dictionaryList = dicUtils.getSingleKanjiListDictionary("/single_kanji.tsv")
        .sortedBy { it.yomi }
        .sortedBy { it.yomi.length }
        .groupBy { it.yomi }
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList.toSortedMap(compareBy({ it.length }, { it })),
        yomiOutputPath = "./src/main/resources/yomi_singleKanji.dat",
        tangoOutputPath = "./src/main/resources/tango_singleKanji.dat",
        tokenOutputPath = "./src/main/resources/token_singleKanji.dat",
    )
}

private fun buildDictionaryForEmoji() {
    val emojiDictionaryBuilder = EmojiDictionaryBuilder()

    val dictionaryList = emojiDictionaryBuilder.convertEmojiDataToDictionaryList("src/main/bin/emoji_data.tsv")
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_emoji.dat",
        tangoOutputPath = "./src/main/resources/tango_emoji.dat",
        tokenOutputPath = "./src/main/resources/token_emoji.dat",
    )
}

private fun buildDictionaryForEmoticon() {
    val emoticonDictionaryBuilder = EmoticonDictionaryBuilder()

    val dictionaryList = emoticonDictionaryBuilder.convertEmoticonDataToDictionaryList("src/main/bin/emoticon.tsv")
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_emoticon.dat",
        tangoOutputPath = "./src/main/resources/tango_emoticon.dat",
        tokenOutputPath = "./src/main/resources/token_emoticon.dat",
    )
}

private fun buildDictionaryForSymbol() {
    val symbolDictionaryBuilder = SymbolDictionaryBuilder()

    val dictionaryList = symbolDictionaryBuilder.convertSymbolDataToDictionaryList("src/main/bin/symbol.tsv")
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_symbol.dat",
        tangoOutputPath = "./src/main/resources/tango_symbol.dat",
        tokenOutputPath = "./src/main/resources/token_symbol.dat",
    )
}

private fun buildDictionaryForReadingCorrection() {
    val readingCorrectionBuilder = ReadingCorrectionBuilder()

    val dictionaryList = readingCorrectionBuilder.parseReadingCorrectionTSV("src/main/bin/reading_correction.tsv")
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_reading_correction.dat",
        tangoOutputPath = "./src/main/resources/tango_reading_correction.dat",
        tokenOutputPath = "./src/main/resources/token_reading_correction.dat",
    )
}

private fun buildDictionaryForKotowaza() {
    val readingCorrectionBuilder = ReadingCorrectionBuilder()

    val dictionaryList = readingCorrectionBuilder.parseKotowazaTSV("src/main/bin/kotowaza.tsv")
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_kotowaza.dat",
        tangoOutputPath = "./src/main/resources/tango_kotowaza.dat",
        tokenOutputPath = "./src/main/resources/token_kotowaza.dat",
    )
}
