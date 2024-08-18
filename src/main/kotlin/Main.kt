package com.kazumaproject


import com.kazumaproject.Constants.CUSTOM_LIST
import com.kazumaproject.Constants.DIC_LIST
import com.kazumaproject.Constants.DIFFICULT_LIST
import com.kazumaproject.Constants.FIXED_LIST
import com.kazumaproject.Constants.NAME_IT_LIST
import com.kazumaproject.Constants.NAME_LIST
import com.kazumaproject.Constants.NAME_MUSIC_LIST
import com.kazumaproject.Constants.PROVERB_LIST
import com.kazumaproject.Constants.SYMBOL_LIST
import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.io.*
import kotlin.math.sqrt
import kotlin.time.measureTime

fun main() {
    buildTriesAndTokenArray()
    //buildPOSTable()
    //buildConnectionIds()
    //buildDictionaryForSingleKanji()
}

private fun buildPOSTable(){
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
        "/domain.txt",
        "/era.txt"
    )
    val tokenArray = TokenArray()
    tokenArray.buildPOSTable(fileList,1)
    tokenArray.buildPOSTableWithIndex(fileList,1)
}

private fun buildTriesAndTokenArray(){

    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    val dicUtils = DicUtils()

    val mode = 3

    val list = when(mode){
        0 -> listOf("/dictionary_small.txt")
        1 -> listOf("/dictionary_medium.txt")
        2 -> listOf("/dictionary00.txt")
        else -> listOf(
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
        )
    }

    val dictionaryList = dicUtils.getListDictionary(list,).toMutableList()

    val finalList = dictionaryList.apply {
        addAll(DIC_LIST)
        addAll(CUSTOM_LIST)
        addAll(NAME_LIST)
        addAll(FIXED_LIST)
        addAll(DIFFICULT_LIST)
        addAll(SYMBOL_LIST)
        addAll(NAME_MUSIC_LIST)
        addAll(NAME_IT_LIST)
        addAll(PROVERB_LIST)
    }
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))

    finalList
        .forEach { entry ->
            yomiTree.insert(entry.key)
            entry.value.forEach {
                if (it.yomi != it.tango && it.yomi.hiraToKata() != it.tango) {
                    tangoTree.insert(it.tango)
                    println("insert to tango tree: ${it.tango}")
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

    var yomiLOUDS: LOUDSWithTermId
    var tangoLOUDS: LOUDS

    val yomiLOUDSReadTime = measureTime {
        yomiLOUDS = LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    }
    val tangoLOUDSReadTime = measureTime {
        tangoLOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    }

    val tokenArrayTemp = TokenArray()

    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token.dat"))

    val timeBuildTokenArray = measureTime {
        tokenArrayTemp.buildTokenArray(finalList,tangoLOUDS,objectOutput,1)
    }

    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token.dat"))
    val tokenArray = TokenArray()

    val tokenArrayReadTime = measureTime {
        tokenArray.readExternalNotCompress(objectInput)
    }

    tokenArray.readPOSTable(1)

    println("loading time of token.dat: $tokenArrayReadTime")
    println("build time of Token.dat: $timeBuildTokenArray")
    println("load time of yomi.dat $yomiLOUDSReadTime")
    println("load time of tango.dat $tangoLOUDSReadTime")
}

private fun loadTermIdsTxt(){
    val time = measureTime {
        val a = File("./src/main/resources/termIds.txt").bufferedReader().readLines().map { it.toInt() }
        println("${a.size}")
    }
    println("$time")
}

private fun buildConnectionIds(){

    val lines = object {}::class.java.getResourceAsStream("/connection_single_column.txt")
        ?.bufferedReader()
        ?.readLines()

    val connectionIdBuilder = ConnectionIdBuilder()
    lines?.let { l ->
        connectionIdBuilder.writeShortArrayAsBytes(
            l.map { it.toShort() }.toShortArray(),
            "./src/main/resources/connectionId.dat",
        )
    }

    val time = measureTime {
        val read = connectionIdBuilder.readShortArrayFromBytes("./src/main/resources/connectionId.dat")
        println("${read.size} ${sqrt(read.size.toDouble())}")
    }
    println("$time")
}

private fun buildDictionaryForSingleKanji(){
    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    val dicUtils = DicUtils()

    val dictionaryList = dicUtils.getSingleKanjiListDictionary("/single_kanji.tsv")
        .sortedBy { it.yomi }
        .sortedBy{ it.yomi.length }
        .groupBy { it.yomi }

    dictionaryList
        .forEach { entry ->
            yomiTree.insert(entry.key)
            println("insert to yomi tree: ${entry.key}")
            entry.value.forEach {
                tangoTree.insert(it.tango)
                println("insert to tango tree: ${it.tango}")
            }
        }

    val yomiLOUDSTemp = ConverterWithTermId().convert(yomiTree.root)
    val tangoLOUDSTemp = Converter().convert(tangoTree.root)
    yomiLOUDSTemp.convertListToBitSet()
    tangoLOUDSTemp.convertListToBitSet()

    val objectOutputYomi = ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/yomi_singleKanji.dat")))
    val objectOutputTango = ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/tango_singleKanji.dat")))

    yomiLOUDSTemp.writeExternalNotCompress(objectOutputYomi)
    tangoLOUDSTemp.writeExternalNotCompress(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi_singleKanji.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango_singleKanji.dat"))

    var yomiLOUDS: LOUDSWithTermId
    var tangoLOUDS: LOUDS

    val yomiLOUDSReadTime = measureTime {
        yomiLOUDS = LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
    }
    val tangoLOUDSReadTime = measureTime {
        tangoLOUDS = LOUDS().readExternalNotCompress(objectInputTango)
    }

    val tokenArrayTemp = TokenArray()

    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token_singleKanji.dat"))

    val timeBuildTokenArray = measureTime {
        tokenArrayTemp.buildTokenArray(dictionaryList,tangoLOUDS,objectOutput,1)
    }

    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token_singleKanji.dat"))
    val tokenArray = TokenArray()

    val tokenArrayReadTime = measureTime {
        tokenArray.readExternalNotCompress(objectInput)
    }

    tokenArray.readPOSTable(1)

    println("loading time of token.dat: $tokenArrayReadTime")
    println("build time of Token.dat: $timeBuildTokenArray")
    println("load time of yomi.dat $yomiLOUDSReadTime")
    println("load time of tango.dat $tangoLOUDSReadTime")
}
