package dictionary

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.dictionary.models.TokenEntryConverted
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.io.FileInputStream
import java.io.ObjectInputStream
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.time.measureTime

class DictionaryBuildTest {
    private lateinit var tangoTree: PrefixTree
    private lateinit var yomiTree: PrefixTreeWithTermId
    @BeforeTest
    fun setUp() {
        tangoTree = PrefixTree()
        yomiTree = PrefixTreeWithTermId()
    }

    @AfterTest
    fun after(){

    }

    /**
     *
     *
     *
     * **/
    @Test
    fun `build dictionary files`(){
        val mode = 2
        val tempList: MutableList<Dictionary> = mutableListOf()

        val list = when(mode){
            0 -> listOf("/dictionary_small.txt")
            1 -> listOf("/dictionary_medium.txt")
            2 -> listOf("/dictionary00.txt")
            else -> listOf("/dictionary00.txt","/dictionary01.txt")
        }


//        val dicUtils = DicUtils()
//        dicUtils.getListDictionary(list,"/single_kanji.tsv").forEach {
//            tempList.add(it)
//        }
//
//        tempList.sortedBy { it.yomi.length } .groupBy { it.yomi }.forEach { entry ->
//            yomiTree.insert(entry.key)
//            println("insert to yomi tree: ${entry.key}")
//            entry.value.forEach {
//                if (it.yomi != it.tango && it.yomi.hiraToKata() != it.tango){
//                    tangoTree.insert(it.tango)
//                    println("insert to tango tree: ${it.tango}")
//                }
//            }
//        }
//
//        val yomiLOUDSTemp = ConverterWithTermId().convert(yomiTree.root)
//        val tangoLOUDSTemp = Converter().convert(tangoTree.root)
//        yomiLOUDSTemp.convertListToBitSet()
//        tangoLOUDSTemp.convertListToBitSet()
//
//        val objectOutputYomi = ObjectOutputStream(FileOutputStream("./src/test/resources/yomi.dat"))
//        val objectOutputTango = ObjectOutputStream(FileOutputStream("./src/test/resources/tango.dat"))
//
//        yomiLOUDSTemp.writeExternal(objectOutputYomi)
//        tangoLOUDSTemp.writeExternal(objectOutputTango)

        val objectInputYomi = ObjectInputStream(FileInputStream("./src/test/resources/yomi.dat"))
        val objectInputTango = ObjectInputStream(FileInputStream("./src/test/resources/tango.dat"))

        var yomiLOUDS: LOUDSWithTermId
        var tangoLOUDS: LOUDS

        val yomiLOUDSReadTime = measureTime {
            yomiLOUDS = LOUDSWithTermId().readExternal(objectInputYomi)
        }
        val tangoLOUDSReadTime = measureTime {
            tangoLOUDS = LOUDS().readExternal(objectInputTango)
        }

//        val tokenArrayTemp = TokenArray()
//        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/token.dat"))
//        tokenArrayTemp.buildJunctionArray(tempList,tangoLOUDS,objectOutput,0)

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/token.dat"))
        val tokenArray = TokenArray()

        val tokenArrayReadTime = measureTime {
            tokenArray.readExternal(objectInput)
        }

        tokenArray.readPOSTable(0)

        val query = "ぶた"
        val test = "私"

        val termId = yomiLOUDS.getTermId(yomiLOUDS.getNodeIndex(query))
        println("expect: ${tangoLOUDS.getNodeIndex(test)}")
        println("expect: ${tangoLOUDS.getLetter(tangoLOUDS.getNodeIndex(test))}")
        println("node index: ${yomiLOUDS.getNodeIndex(query)}")
        println("term id: $termId")
        println("${tempList.groupBy { it.yomi }[query]}")

        val result = tokenArray.getListDictionaryByYomiTermId(termId).map {
            TokenEntryConverted(
                leftId = tokenArray.posTable[it.posTableIndex.toInt()].first,
                rightId = tokenArray.posTable[it.posTableIndex.toInt()].second,
                wordCost = it.wordCost,
                tango = if (it.isSameYomi) "" else tangoLOUDS.getLetter(it.nodeId),
                yomiLength = query.length.toShort()
            )
        }
        println("$result")

        println("loading time of yomi.dat: $yomiLOUDSReadTime ${yomiLOUDS.getNodeIdSize()}")
        println("loading time of tango.dat: $tangoLOUDSReadTime ${tangoLOUDS.getNodeIdSize()}")
        println("loading time of token.dat: $tokenArrayReadTime")

        println("${yomiTree.find(query)?.termId}")

    }

}