package com.kazumaproject


import com.kazumaproject.Constants.CUSTOM_LIST
import com.kazumaproject.Constants.DIC_LIST
import com.kazumaproject.Constants.DIFFICULT_LIST
import com.kazumaproject.Constants.FIXED_LIST
import com.kazumaproject.Constants.NAME_LIST
import com.kazumaproject.Constants.SYMBOL_LIST
import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.io.*
import kotlin.time.measureTime

fun main() {
    buildTriesAndTokenArray()
    //buildConnectionIdSparseArray()
    //buildPOSTable()
    //testBestPath()
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
    }
        .groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))

    finalList
        .forEach { entry ->
            yomiTree.insert(entry.key)
            if (entry.key.length == 1) {
                println("insert to yomi tree: ${entry.key}")
            }
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

private fun buildConnectionIdSparseArray(){
    val lines = object {}::class.java.getResourceAsStream("/connection_single_column.txt")
        ?.bufferedReader()
        ?.readLines()

    val connectionIdBuilder = ConnectionIdBuilder()

    val objectOutput = ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/connectionIds.dat")))
    lines?.let { l ->
        connectionIdBuilder.build(objectOutput,l.map { it.toShort() })
    }

    val objectInput = ObjectInputStream(BufferedInputStream(FileInputStream("./src/main/resources/connectionIds.dat")))
    val time = measureTime {
        val a = ConnectionIdBuilder().read(objectInput)
        println("a ${a.size}")

    }
    println("$time")
}

private fun testBestPath(){
    val kanaKanjiEngine = KanaKanjiEngine()
    kanaKanjiEngine.buildEngine()

    val word1 = "とべないぶた"
    val word2 = "わたしのなまえはなかのです"
    val word3 = "ここではきものをぬぐ"

    val time1 = measureTime {
        kanaKanjiEngine.viterbiAlgorithm(word2)
    }

    val time2 = measureTime {
        kanaKanjiEngine.nBestPath(word2,5)
    }

    val result1BestPath = kanaKanjiEngine.viterbiAlgorithm(word1)
    val result2BestPath = kanaKanjiEngine.viterbiAlgorithm(word2)
    val result3BestPath = kanaKanjiEngine.viterbiAlgorithm(word3)

    val result1NBest = kanaKanjiEngine.nBestPath(word1,5)
    val result2NBest = kanaKanjiEngine.nBestPath(word2,5)
    val result3NBest = kanaKanjiEngine.nBestPath(word3,5)

    println("Viterbi $word1 =>=> $result1BestPath")
    println("Viterbi $word2 =>=> $result2BestPath")
    println("Viterbi $word3 =>=> $result3BestPath")

    println("nBestPath $word1 =>=> $result1NBest")
    println("nBestPath $word2 =>=> $result2NBest")
    println("nBestPath $word3 =>=> $result3NBest")

    println("time to find shortest path $word2: $time1")
    println("time to find nBest path $word2: $time2")
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
        println("${read.size}")
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
