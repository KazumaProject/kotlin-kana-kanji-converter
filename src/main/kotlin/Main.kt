package com.kazumaproject

import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.classification.DictionaryFilter
import com.kazumaproject.english.EnglishDictionaryBinaryValidator
import com.kazumaproject.mozc.buildConnectionIdsFromResource
import com.kazumaproject.mozc.validateBundledMozcDictionaryResources
import kotlinx.serialization.json.*
import java.io.*
import java.util.*

fun main() {
    validateBundledMozcDictionaryResources()
    val dictionaryFilter = DictionaryFilter.fromEnvironment()
    val baseline = BaselineDictionaryInputs.filtered(dictionaryFilter)
    val finalList = baseline.getValue("system").groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    val englishDictionaryList = baseline.getValue("english_reading")

    buildConnectionIds()
    val classified = ClassifiedDictionaryData(dictionaryFilter = dictionaryFilter)
    val specialists = ClassifiedDictionaryData(File("src/main/specialist"), expectedCategoryCount = 2, dictionaryFilter = dictionaryFilter)
    val sharedPosInputs = (finalList.values.flatten() + englishDictionaryList + classified.records.values.flatten() + specialists.records.values.flatten())
        .groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildPOSTable(sharedPosInputs)
    buildTriesAndTokenArray(finalList)
    buildEnglishDictionary(englishDictionaryList)
    EnglishDictionaryBinaryValidator.validate(
        englishDictionaryList,
        java.nio.file.Path.of("src/main/resources/yomi_english_reading.dat"),
        java.nio.file.Path.of("src/main/resources/tango_english_reading.dat"),
        java.nio.file.Path.of("src/main/resources/token_english_reading.dat"),
        java.nio.file.Path.of("src/main/resources/pos_table.dat"),
    )
    buildDictionaryForSingleKanji(baseline.getValue("single_kanji"))
    buildDictionaryForEmoji(baseline.getValue("emoji"))
    buildDictionaryForEmoticon(baseline.getValue("emoticon"))
    buildDictionaryForSymbol(baseline.getValue("symbol"))
    buildDictionaryForReadingCorrection(baseline.getValue("reading_correction"))
    buildDictionaryForKotowaza(baseline.getValue("kotowaza"))
    classified.build()
    specialists.build()
    val categoryCounts = (classified.records + specialists.records).mapValues { it.value.size }
    File("build/reports/dictionary-filter/category-counts.json").apply {
        parentFile.mkdirs()
        writeText(buildJsonObject {
            put("filterRevision", dictionaryFilter.revision)
            put("categoryRows", buildJsonObject { categoryCounts.toSortedMap().forEach { (id, count) -> put(id, count) } })
        }.toString() + "\n")
    }
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

private fun buildEnglishDictionary(dictionaryList: List<Dictionary>) {
    val englishDictionary = dictionaryList
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = englishDictionary,
        yomiOutputPath = "./src/main/resources/yomi_english_reading.dat",
        tangoOutputPath = "./src/main/resources/tango_english_reading.dat",
        tokenOutputPath = "./src/main/resources/token_english_reading.dat",
        mode = 1,
        skipKanaOnlyTango = true,
    )
}

private fun buildConnectionIds() {
    buildConnectionIdsFromResource()
}

private fun buildDictionaryForSingleKanji(entries: List<Dictionary>) {
    val dictionaryList = entries.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList.toSortedMap(compareBy({ it.length }, { it })),
        yomiOutputPath = "./src/main/resources/yomi_singleKanji.dat",
        tangoOutputPath = "./src/main/resources/tango_singleKanji.dat",
        tokenOutputPath = "./src/main/resources/token_singleKanji.dat",
    )
}

private fun buildDictionaryForEmoji(entries: List<Dictionary>) {
    val dictionaryList = entries.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_emoji.dat",
        tangoOutputPath = "./src/main/resources/tango_emoji.dat",
        tokenOutputPath = "./src/main/resources/token_emoji.dat",
    )
}

private fun buildDictionaryForEmoticon(entries: List<Dictionary>) {
    val dictionaryList = entries.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_emoticon.dat",
        tangoOutputPath = "./src/main/resources/tango_emoticon.dat",
        tokenOutputPath = "./src/main/resources/token_emoticon.dat",
    )
}

private fun buildDictionaryForSymbol(entries: List<Dictionary>) {
    val dictionaryList = entries.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_symbol.dat",
        tangoOutputPath = "./src/main/resources/tango_symbol.dat",
        tokenOutputPath = "./src/main/resources/token_symbol.dat",
    )
}

private fun buildDictionaryForReadingCorrection(entries: List<Dictionary>) {
    val dictionaryList = entries.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_reading_correction.dat",
        tangoOutputPath = "./src/main/resources/tango_reading_correction.dat",
        tokenOutputPath = "./src/main/resources/token_reading_correction.dat",
    )
}

private fun buildDictionaryForKotowaza(entries: List<Dictionary>) {
    val dictionaryList = entries.groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
    buildAndWriteDictionaryArtifacts(
        dictionaryList = dictionaryList,
        yomiOutputPath = "./src/main/resources/yomi_kotowaza.dat",
        tangoOutputPath = "./src/main/resources/tango_kotowaza.dat",
        tokenOutputPath = "./src/main/resources/token_kotowaza.dat",
    )
}
