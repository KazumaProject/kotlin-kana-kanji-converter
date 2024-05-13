package prefix

import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.bitset.rank1
import com.kazumaproject.bitset.select0
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import com.kazumaproject.toBooleanList
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.time.measureTime

class PrefixTreeWithTermIdTest {

    private lateinit var tree: PrefixTreeWithTermId
    @BeforeTest
    fun setUp() {
        tree = PrefixTreeWithTermId()
    }

    @AfterTest
    fun after(){

    }

    @Test
    fun `Test find method`(){
        tree.apply {
            insert("相変わらず")
            insert("愛である")
            insert("開いてる")
            insert("愛のことば")
            insert("愛と勇気")
        }
        println("${tree.find("愛と勇気")?.termId}")
    }

    @Test
    fun `Test read text file from resources`(){

        val mode = 1
        val tempList: MutableList<Dictionary> = mutableListOf()

        val list = when(mode){
            0 -> listOf("/dictionary_small.txt")
            1 -> listOf("/dictionary_medium.txt")
            2 -> listOf("/dictionary00.txt")
            else -> listOf("/dictionary00.txt","/dictionary01.txt")
        }

        list.forEach {
            val line = this::class.java.getResourceAsStream(it)
                ?.bufferedReader()
                ?.readLines()

            line?.forEach { str ->
                str.apply {
                    val yomi = split("\\t".toRegex())[0]
                    val leftId = split("\\t".toRegex())[1]
                    val rightId = split("\\t".toRegex())[2]
                    val cost = split("\\t".toRegex())[3]
                    val tango = split("\\t".toRegex())[4]
                    val dictionary = Dictionary(
                        yomi = yomi,
                        leftId = leftId.toShort(),
                        rightId = rightId.toShort(),
                        cost = cost.toShort(),
                        tango = tango,
                    )
                    tempList.add(dictionary)
                    println("insert ${dictionary.yomi} ${dictionary.tango}")
                }
            }
        }

        tempList.groupBy { it.yomi }.forEach { entry ->
            tree.insert(entry.key)
        }

        val loudsYomiTemp = ConverterWithTermId().convert(tree.root)
        loudsYomiTemp.convertListToBitSet()

        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/yomi.dat"))
        loudsYomiTemp.writeExternal(objectOutput)

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/yomi.dat"))
        var loudsYomi: LOUDSWithTermId
        val time = measureTime {
            loudsYomi = LOUDSWithTermId().readExternal(objectInput)
        }

        val word1 = "あいあんと"
        val word2 = "あいかわらず"
        val word3 = "あいくる"
        val error = "あいあ"

        val query = word1

        loudsYomi.apply {
            println("get letters: ${getNodeIndex(query)} ${getLetter(getNodeIndex(query))}")
            println("node id: ${getNodeId(query)}")
            println("term id: ${getTermId(getNodeIndex(query))}")

            println("common prefix search: ${commonPrefixSearch(query)}")


            if (mode == 0){
                println("${LBS.toBooleanList().map { if (it) 1 else 0 }}")
                println("$labels")

                println("${isLeaf.toBooleanList().map { if (it) 1 else 0 }}")
                println("$termIds")
            }
        }

        println("time: $time")

    }

    @Test
    fun `Test get child`(){

       val list = listOf(
           "an",
           "i",
           "of",
           "one",
           "our",
           "out",
           "outlet",
           "ou",
       )

        list.forEach {
            tree.insert(it)
        }

        val loudsYomiTemp = ConverterWithTermId().convert(tree.root)
        loudsYomiTemp.convertListToBitSet()

        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/yomi.dat"))
        loudsYomiTemp.writeExternal(objectOutput)

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/yomi.dat"))
        var loudsYomi: LOUDSWithTermId
        val time = measureTime {
            loudsYomi = LOUDSWithTermId().readExternal(objectInput)
        }

        loudsYomi.apply {
            println("${commonPrefixSearch("outlet")}")

            println("${LBS.toBooleanList().map { if (it) 1 else 0 }}")
            println("$labels")

            println("${isLeaf.toBooleanList().map { if (it) 1 else 0 }}")
            println("$termIds")
            println("${getNodeIndex("o")}")
            println("${LBS.select0(LBS.rank1(getNodeIndex("o"))) + 1}")
            println("${LBS.rank1(LBS.select0(LBS.rank1(getNodeIndex("o"))) + 1)}")
        }

        println("time: $time")

    }

    @Test
    fun `Test Common Prefix Search`(){
        val list = listOf(
            "関西",
            "国際",
            "国際空港",
            "関西国際空港"
        )
        list.forEach {
            tree.insert(it)
        }
        val loudsYomi = ConverterWithTermId().convert(tree.root)
        loudsYomi.convertListToBitSet()

        println("${loudsYomi.commonPrefixSearch("関西国際空港")}")

    }

}