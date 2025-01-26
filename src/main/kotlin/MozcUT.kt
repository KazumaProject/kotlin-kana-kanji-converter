package com.kazumaproject

import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import com.kazumaproject.reading_correction.ReadingCorrectionBuilder
import java.io.*
import java.util.zip.ZipInputStream

fun main() {
    buildDictionaryForPersonNames()
    buildDictionaryForPlaces()
    buildDictionaryForWiki()
}

private fun buildDictionaryForPersonNames() {
    println("start build person names dictionary")
    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    val readingCorrectionBuilder = ReadingCorrectionBuilder()

    val dictionaryList = readingCorrectionBuilder.parseMozcUTDictionary("src/main/bin/names.txt")
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))

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
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/yomi_person_names.dat")))
    val objectOutputTango =
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/tango_person_names.dat")))

    yomiLOUDSTemp.writeExternalNotCompress(objectOutputYomi)
    tangoLOUDSTemp.writeExternalNotCompress(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi_person_names.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango_person_names.dat"))

    LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    val tangoLOUDS: LOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    val tokenArrayTemp = TokenArray()
    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token_person_names.dat"))
    tokenArrayTemp.buildTokenArray(dictionaryList, tangoLOUDS, objectOutput, 1)
    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token_person_names.dat"))
    val tokenArray = TokenArray()
    tokenArray.readExternalNotCompress(objectInput)
    tokenArray.readPOSTable(1)
}

private fun buildDictionaryForPlaces() {
    println("start build places dictionary")

    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    val readingCorrectionBuilder = ReadingCorrectionBuilder()

    val dictionaryList = readingCorrectionBuilder.parseMozcUTDictionaryCompressedDictionary(
        readTextFromZip(
            filePath = "src/main/bin/place.txt.zip",
            fileName = "place.txt"
        )
    )
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))

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
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/yomi_places.dat")))
    val objectOutputTango =
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/tango_places.dat")))

    yomiLOUDSTemp.writeExternalNotCompress(objectOutputYomi)
    tangoLOUDSTemp.writeExternalNotCompress(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi_places.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango_places.dat"))

    LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    val tangoLOUDS: LOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    val tokenArrayTemp = TokenArray()
    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token_places.dat"))
    tokenArrayTemp.buildTokenArray(dictionaryList, tangoLOUDS, objectOutput, 1)
    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token_places.dat"))
    val tokenArray = TokenArray()
    tokenArray.readExternalNotCompress(objectInput)
    tokenArray.readPOSTable(1)
}

private fun buildDictionaryForWiki() {
    println("start build wiki dictionary")

    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    val readingCorrectionBuilder = ReadingCorrectionBuilder()

    val dictionaryList = readingCorrectionBuilder.parseMozcUTDictionaryCompressedDictionary(
        readTextFromZip(
            filePath = "src/main/bin/wiki.txt.zip",
            fileName = "wiki.txt"
        )
    )
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))

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
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/yomi_wiki.dat")))
    val objectOutputTango =
        ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/tango_wiki.dat")))

    yomiLOUDSTemp.writeExternalNotCompress(objectOutputYomi)
    tangoLOUDSTemp.writeExternalNotCompress(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi_wiki.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango_wiki.dat"))

    LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    val tangoLOUDS: LOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    val tokenArrayTemp = TokenArray()
    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token_wiki.dat"))
    tokenArrayTemp.buildTokenArray(dictionaryList, tangoLOUDS, objectOutput, 1)
    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token_wiki.dat"))
    val tokenArray = TokenArray()
    tokenArray.readExternalNotCompress(objectInput)
    tokenArray.readPOSTable(1)
}

fun readTextFromZip(filePath: String, fileName: String): InputStream {
    val zipFile = File(filePath)
    val zipInputStream = ZipInputStream(BufferedInputStream(FileInputStream(zipFile)))

    var entry = zipInputStream.nextEntry
    while (entry != null) {
        if (!entry.isDirectory && entry.name == fileName) {
            return zipInputStream
        }
        entry = zipInputStream.nextEntry
    }

    throw FileNotFoundException("$fileName not found in $filePath")
}
