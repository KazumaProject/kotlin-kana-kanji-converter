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
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.classification.DictionaryFilter
import com.kazumaproject.emoji.EmojiDictionaryBuilder
import com.kazumaproject.emoticon.EmoticonDictionaryBuilder
import com.kazumaproject.english.EnglishDictionarySource
import com.kazumaproject.reading_correction.ReadingCorrectionBuilder
import com.kazumaproject.symbol.SymbolDictionaryBuilder
import java.io.File

/** The exact inputs selected by Main, shared with the specialist duplicate inventory. */
internal object BaselineDictionaryInputs {
    fun system(): List<Dictionary> {
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
        val dictionaryList = dicUtils.getListDictionary(fileList)
        val atokUnigramDictionaryList = dicUtils.getListDictionary(listOf("/atok-unigram-dictionary.txt"))
        val baseDictionaryList =
            (dictionaryList +
                    DIC_LIST + CUSTOM_LIST +
                    NAME_LIST + FIXED_LIST +
                    DIFFICULT_LIST + SYMBOL_LIST +
                    NAME_MUSIC_LIST + NAME_IT_LIST +
                    VERB_LIST + DOMAIN + ERA + PLACE +
                    WORDS + ZENKANKU_LIST + ADDS_NEW_WORDS + PHISIC_NOUN_LIST
                    + FIGHT_NAME + FOOD_NAME + ENTERTAIMENT_NAME + RESCORE_WORDS
                    )
        val existingPairs = baseDictionaryList.asSequence()
            .map { it.yomi to it.tango }
            .toHashSet()
        val atokUnigramMissing = atokUnigramDictionaryList.filter { (it.yomi to it.tango) !in existingPairs }
        val finalList =
            (baseDictionaryList + atokUnigramMissing)
                .groupBy { it.yomi }
                .toSortedMap(compareBy({ it.length }, { it }))

        println("finalList size: ${finalList.size}")
        println(
            "ATOK unigram dictionary: source=${atokUnigramDictionaryList.size}, " +
                    "alreadyPresent=${atokUnigramDictionaryList.size - atokUnigramMissing.size}, " +
                    "added=${atokUnigramMissing.size}",
        )
        return finalList.values.flatten()
    }

    fun load(classifiedDirectory: File = File("src/main/classification")): Map<String, List<Dictionary>> = linkedMapOf<String, List<Dictionary>>().apply {
        put("system", system())
        put("english_reading", EnglishDictionarySource.loadResources(
            contextId = IdDefConstants.`名詞,一般,*,*,*,*,*`.toInt()).runtimeEntries)
        put("single_kanji", DicUtils().getSingleKanjiListDictionary("/single_kanji.tsv"))
        put("emoji", EmojiDictionaryBuilder().convertEmojiDataToDictionaryList("src/main/bin/emoji_data.tsv"))
        put("emoticon", EmoticonDictionaryBuilder().convertEmoticonDataToDictionaryList("src/main/bin/emoticon.tsv"))
        put("symbol", SymbolDictionaryBuilder().convertSymbolDataToDictionaryList("src/main/bin/symbol.tsv"))
        put("reading_correction", ReadingCorrectionBuilder().parseReadingCorrectionTSV("src/main/bin/reading_correction.tsv"))
        put("kotowaza", ReadingCorrectionBuilder().parseKotowazaTSV("src/main/bin/kotowaza.tsv"))
        ClassifiedDictionaryData(classifiedDirectory, dictionaryFilter = DictionaryFilter.empty()).records.forEach { (id, entries) -> put("categories/$id", entries.toList()) }
    }

    fun filtered(filter: DictionaryFilter, classifiedDirectory: File = File("src/main/classification")): Map<String, List<Dictionary>> =
        load(classifiedDirectory).mapValues { (source, entries) ->
            filter.filterRecords(entries, skipKanaOnlyTango = source == "system" || source == "english_reading")
        }
}
