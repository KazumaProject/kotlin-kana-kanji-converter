package com.kazumaproject

import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.dictionary.models.TokenEntryConverted
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import com.kazumaproject.viterbi.FindPath
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import kotlin.time.measureTime

fun main() {
    buildTriesAndTokenArray()
    //buildConnectionIdSparseArray()
    //loadBinaryFiles()
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
    val tempList: MutableList<Dictionary> = mutableListOf()

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

    val dictionaryList = dicUtils.getListDictionary(list)

    dictionaryList.forEach {
        tempList.add(it)
    }

    tempList.sortedBy { it.yomi.length }.groupBy { it.yomi }.forEach { entry ->
        yomiTree.insert(entry.key)
        println("insert to yomi tree: ${entry.key}")
        entry.value.forEach {
            if (it.yomi != it.tango && it.yomi.hiraToKata() != it.tango){
                tangoTree.insert(it.tango)
                println("insert to tango tree: ${it.tango}")
            }
        }
    }

    val yomiLOUDSTemp = ConverterWithTermId().convert(yomiTree.root)
    val tangoLOUDSTemp = Converter().convert(tangoTree.root)
    yomiLOUDSTemp.convertListToBitSet()
    tangoLOUDSTemp.convertListToBitSet()

    val objectOutputYomi = ObjectOutputStream(FileOutputStream("./src/main/resources/yomi.dat"))
    val objectOutputTango = ObjectOutputStream(FileOutputStream("./src/main/resources/tango.dat"))

    yomiLOUDSTemp.writeExternal(objectOutputYomi)
    tangoLOUDSTemp.writeExternal(objectOutputTango)

    val objectInputYomi = ObjectInputStream(FileInputStream("./src/main/resources/yomi.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("./src/main/resources/tango.dat"))

    var yomiLOUDS: LOUDSWithTermId
    var tangoLOUDS: LOUDS

    val yomiLOUDSReadTime = measureTime {
        yomiLOUDS = LOUDSWithTermId().readExternal(objectInputYomi)
    }
    val tangoLOUDSReadTime = measureTime {
        tangoLOUDS = LOUDS().readExternal(objectInputTango)
    }

    val tokenArrayTemp = TokenArray()

    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/token.dat"))
    tokenArrayTemp.buildJunctionArray(tempList,tangoLOUDS,objectOutput,0)

    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/token.dat"))
    val tokenArray = TokenArray()

    val tokenArrayReadTime = measureTime {
        tokenArray.readExternal(objectInput)
    }

    tokenArray.readPOSTable(1)

    val query = "わたし"

    val result = tokenArray.getListDictionaryByYomiTermId(yomiLOUDS.getTermId(yomiLOUDS.getNodeIndex(query))).map {
        TokenEntryConverted(
            leftId = tokenArray.posTable[it.posTableIndex.toInt()].first,
            rightId = tokenArray.posTable[it.posTableIndex.toInt()].second,
            wordCost = it.wordCost,
            tango = if (it.isSameYomi) "" else tangoLOUDS.getLetter(it.nodeId),
            query.length.toShort(),

        )
    }
    println("$result")
    println("$query ${yomiLOUDS.commonPrefixSearch(query)}")

    println("loading time of yomi.dat: $yomiLOUDSReadTime ${yomiLOUDS.getNodeIdSize()}")
    println("loading time of tango.dat: $tangoLOUDSReadTime ${tangoLOUDS.getNodeIdSize()}")
    println("loading time of token.dat: $tokenArrayReadTime")
}

private fun buildConnectionIdSparseArray(){
    val lines = object {}::class.java.getResourceAsStream("/connection_single_column.txt")
        ?.bufferedReader()
        ?.readLines()

    val connectionIdBuilder = ConnectionIdBuilder()

    val objectOutput = ObjectOutputStream(FileOutputStream("./src/main/resources/connectionIds.dat"))
    lines?.let { l ->
        connectionIdBuilder.build(objectOutput,l.map { it.toShort() })
    }

    val objectInput = ObjectInputStream(FileInputStream("./src/main/resources/connectionIds.dat"))
    val time = measureTime {
        val a = ConnectionIdBuilder().read(objectInput)
        println("${a.size}")
    }
    println("$time")
}

fun loadBinaryFiles(){
    var yomiTrie: LOUDSWithTermId
    var tangoTrie: LOUDS
    val graphBuilder = GraphBuilder()
    val connectionIds: List<Short>

    val objectInputYomi = ObjectInputStream(FileInputStream("src/test/resources/yomi.dat"))
    val objectInputTango = ObjectInputStream(FileInputStream("src/test/resources/tango.dat"))
    val objectInputTokenArray = ObjectInputStream(FileInputStream("src/test/resources/token.dat"))
    val objectInputConnectionId = ObjectInputStream(FileInputStream("src/test/resources/connectionIds.dat"))

    val tokenArray = TokenArray()

    val yomiLoadingTime = measureTime {
        yomiTrie = LOUDSWithTermId().readExternal(objectInputYomi)
    }
    val tangoLoadingTime = measureTime {
        tangoTrie = LOUDS().readExternal(objectInputTango)
    }
    val tokenArrayLoadingTime = measureTime {
        tokenArray.readExternal(objectInputTokenArray)
    }
    tokenArray.readPOSTable(0)

    val connectionIdsLoadingTime = measureTime {
        connectionIds = ConnectionIdBuilder().read(objectInputConnectionId)
    }

    val query = "とべないぶた"

    val graph = graphBuilder.constructGraph(
        query,
        yomiTrie,
        tangoTrie,
        tokenArray,
    )

    println("loading time yomi.dat: $yomiLoadingTime")
    println("loading time tango.dat: $tangoLoadingTime")
    println("loading token tango.dat: $tokenArrayLoadingTime")
    println("loading connection ids: $connectionIdsLoadingTime")

    println("${graph.map { it.map { l -> l.map { u -> u.tango } } }}")

    val findPath = FindPath()

    //println(findPath.viterbi(graph,query.length, connectionIds))

    println(findPath.backwardAStar(graph,query.length, connectionIds,1))

}
