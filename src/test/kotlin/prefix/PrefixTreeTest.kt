package prefix


import com.kazumaproject.Constants.DIC_LIST
import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.dictionary.models.TokenEntryConverted
import com.kazumaproject.hiraToKata
import com.kazumaproject.isHiraganaOrKatakana
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import com.kazumaproject.toBooleanList
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.measureTime

class PrefixTreeTest {

    private lateinit var tree: PrefixTree

    @BeforeTest
    fun setUp() {
        tree = PrefixTree()
    }

    @AfterTest
    fun after() {

    }

    @Test
    fun insert() {
        tree.insert("cat")
        tree.insert("door")
        tree.insert("cats")

        println("${tree.root}")

        val result1 = tree.root.getChildren('c')?.getChildren('a')?.getChildren('t')?.isWord

        assertEquals(true, result1)

        val result2 = tree.root.getChildren('c')?.c
        assertEquals('c', result2)

        val result3 = tree.root.getChildren('c')?.id
        assertEquals(0, result3)

        val result4 = tree.root.getChildren('c')?.getChildren('a')?.id
        assertEquals(1, result4)

        val result5 = tree.root.getChildren('c')?.getChildren('a')?.getChildren('t')?.id
        assertEquals(2, result5)

        val result6 = tree.root.getChildren('c')?.getChildren('a')?.c
        assertEquals('a', result6)

        val result7 = tree.root.getChildren('c')?.getChildren('a')?.getChildren('t')?.getChildren('s')?.c
        assertEquals('s', result7)

        val result8 = tree.root.getChildren('c')?.getChildren('a')?.getChildren('t')?.getChildren('s')?.getChildren('a')
        assertEquals(null, result8)
    }

    @Test
    fun `Test find method`() {
        tree.apply {
            insert("相変わらず")
            insert("愛である")
            insert("開いてる")
            insert("愛のことば")
            insert("愛と勇気")
        }
        println("${tree.find("愛と勇気")}")
    }


    @Test
    fun `read text file from resources`() {
        val lines = this::class.java.getResourceAsStream("/dictionary00.txt")
            ?.bufferedReader()
            ?.readLines()

        lines?.let { line ->
            line.forEach {
                println(it)
                val tango = it.split("\\s".toRegex())[4]
                tree.insert(tango)
            }
        }

        println("root children size: ${tree.root.getChildrenSize()}")

        val louds = Converter().convert(tree.root)
        louds.convertListToBitSet()

        val word = "揺れによる"
        val word2 = "出来難"

        val nodeIndex = louds.getNodeIndex(word)
        val letterFromNodeIndex = louds.getLetter(nodeIndex)

        val nodeIndex2 = louds.getNodeIndex(word2)
        val letterFromNodeIndex2 = louds.getLetter(nodeIndex2)

        println("$nodeIndex $letterFromNodeIndex")
        println("$nodeIndex2 $letterFromNodeIndex2")
    }

    @Test
    fun `LOUDS test`() {
        val list = listOf("an", "i", "of", "one", "our", "out")
        list.forEach {
            tree.insert(it)
        }

        val louds = Converter().convert(tree.root)
        louds.convertListToBitSet()

        println("${louds.labels}")
        println("${louds.isLeaf}")

        val word = "one"

        println("${louds.getLetter(louds.getNodeIndex(word))}")

    }

    @Test
    fun `Test write binary file`() {
        val list = listOf("an", "i", "of", "one", "our", "out")
        list.forEach {
            tree.insert(it)
        }
        val louds = Converter().convert(tree.root)
        louds.convertListToBitSet()
        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/test.dat"))
        louds.writeExternal(objectOutput)

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/test.dat"))
        val louds2 = louds.readExternal(objectInput)

        val word = "one"

        println("${louds2.getLetter(1)}")
    }

    @Test
    fun `Test write binary file 2`() {

        val list = listOf(
            "/dictionary_small.txt",
        )

        list.forEach {
            val line = this::class.java.getResourceAsStream(it)
                ?.bufferedReader()
                ?.readLines()

            line?.forEach { str ->
                val yomi = str.split("\\s".toRegex())[0]
                val tango = str.split("\\s".toRegex())[4]
                if (yomi != tango || yomi.hiraToKata() != tango) {
                    println("$it $tango")
                    tree.insert(tango)
                }
            }
        }

        val louds = Converter().convert(tree.root)
        louds.convertListToBitSet()

        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/test.dat"))
        louds.writeExternal(objectOutput)

        val loudsTemp = LOUDS()

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/test.dat"))
        val louds2 = loudsTemp.readExternal(objectInput)

        val word = "揺れによる"

        louds2.apply {
            println("${LBS.toBooleanList().map { if (it) 1 else 0 }}")
            println("$labels")
            println("${isLeaf.toBooleanList().map { if (it) 1 else 0 }}")
            println(getLetter(getNodeIndex(word)))
        }

    }

    @Test
    fun `Test Token Array`() {

        val yomiTree = PrefixTreeWithTermId()
        val tangoTree = PrefixTree()

        val tempList: MutableList<Dictionary> = mutableListOf()

        tempList.addAll(DIC_LIST)

        val mode = 2

        val list = when (mode) {
            0 -> listOf("/dictionary_small.txt")
            1 -> listOf("/dictionary_medium.txt")
            2 -> listOf("/dictionary05.txt")
            else -> listOf("/dictionary05.txt", "/dictionary07.txt")
        }.toMutableList()

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
                        tango = tango
                    )
                    tempList.add(dictionary)
                }
            }
        }

        val finalList = tempList
            .groupBy { it.yomi }
            .toSortedMap(compareBy({ it.length }, { it }))

        for (entry in finalList.entries) {
            yomiTree.insert(entry.key)
            for (dictionary in entry.value) {
                if (!dictionary.tango.isHiraganaOrKatakana()) {
                    tangoTree.insert(dictionary.tango)
                }
            }
        }

        val loudsYomi = ConverterWithTermId().convert(yomiTree.root)
        val loudsTango = Converter().convert(tangoTree.root)
        loudsYomi.convertListToBitSet()
        loudsTango.convertListToBitSet()

        val bufferedOutputStream =
            ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/test/resources/yomi.dat")))
        val bufferedOutputStream2 =
            ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/test/resources/tango.dat")))

        loudsYomi.writeExternalNotCompress(bufferedOutputStream)
        loudsTango.writeExternalNotCompress(bufferedOutputStream2)

        val tokenArray = TokenArray()

        val objectOutput = ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/test/resources/token.dat")))
        tokenArray.buildTokenArray(
            finalList,
            loudsTango, objectOutput, 0
        )

        val objectInput = ObjectInputStream(BufferedInputStream(FileInputStream("./src/test/resources/token.dat")))
        val tokenArrayTemp = TokenArray()

        val readTime = measureTime {
            tokenArrayTemp.readExternalNotCompress(objectInput)
        }

        val objectInputYomi = ObjectInputStream(BufferedInputStream(FileInputStream("./src/test/resources/yomi.dat")))
        val objectInputTango = ObjectInputStream(BufferedInputStream(FileInputStream("./src/test/resources/tango.dat")))
        val yomi = LOUDSWithTermId().readExternalNotCompress(objectInputYomi)
        val tango = LOUDS().readExternalNotCompress(objectInputTango)
        println("time of reading token.dat: $readTime")

        println("yomi: ${yomi.LBS.size()} tango: ${tango.LBS.size()}")

        tokenArray.readPOSTable(0)

        val word = "かぶきちょう"
        val nodeId = yomi.getTermId(loudsYomi.getNodeIndex(word))

        val a = tokenArrayTemp.getListDictionaryByYomiTermId(nodeId).map {
            TokenEntryConverted(
                leftId = tokenArray.leftIds[it.posTableIndex.toInt()],
                rightId = tokenArray.rightIds[it.posTableIndex.toInt()],
                wordCost = it.wordCost,
                tango = when (it.nodeId) {
                    -2 -> word
                    -1 -> word.hiraToKata()
                    else -> loudsTango.getLetter(it.nodeId)
                },
                yomiLength = word.length.toShort()
            )
        }
        println("$a")
    }

    @Test
    fun `create token array`() {
        val tempList: MutableList<Dictionary> = mutableListOf()
        val tempMap: MutableMap<Pair<Short, Short>, Int> = mutableMapOf()

        val list = listOf(
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
                    if (tempMap[Pair(leftId.toShort(), rightId.toShort())] == null) {
                        tempMap[Pair(leftId.toShort(), rightId.toShort())] = 0
                    } else {
                        tempMap[Pair(leftId.toShort(), rightId.toShort())] =
                            (tempMap[Pair(leftId.toShort(), rightId.toShort())]!!) + 1
                    }
                }
            }
        }

        val result = tempMap.toList().sortedByDescending { (_, value) -> value }.toMap()
        val result2 = tempMap.toList().sortedByDescending { (_, value) -> value }.subList(0, 6187).toMap()


        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/pos_table.dat"))
        objectOutput.apply {
            writeObject(result.keys.toList())
            flush()
            close()
        }

        val objectOutput2 = ObjectOutputStream(FileOutputStream("./src/test/resources/pos_table_for_build.dat"))
        val mapToSave = result.keys.toList().mapIndexed { index, pair -> pair to index }.toMap()
        objectOutput2.apply {
            writeObject(mapToSave)
            flush()
            close()
        }

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/pos_table.dat"))
        var a: List<Pair<Short, Short>> = listOf()
        val time = measureTime {
            objectInput.apply {
                a = (readObject() as List<Pair<Short, Short>>)
            }
            println("${a}")
        }
        println("loading time: $time")

        val objectInput2 = ObjectInputStream(FileInputStream("./src/test/resources/pos_table_for_build.dat"))
        var b: Map<Pair<Short, Short>, Int> = mapOf()
        val time2 = measureTime {
            objectInput2.apply {
                b = (readObject() as Map<Pair<Short, Short>, Int>)
            }
            //println("$b")
        }
        println("$time2")
    }

    @Test
    fun `Test Token Entry With POS Table`() {

        val list = listOf(
            "/dictionary_small.txt",
        )

        list.forEach {
            val line = this::class.java.getResourceAsStream(it)
                ?.bufferedReader()
                ?.readLines()

            line?.forEach { str ->
                val yomi = str.split("\\s".toRegex())[0]
                val tango = str.split("\\s".toRegex())[4]
                if (yomi != tango || yomi.hiraToKata() != tango) {
                    println("$it $tango")
                    tree.insert(tango)
                }
            }
        }

        val louds = Converter().convert(tree.root)
        louds.convertListToBitSet()

        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/test.dat"))
        louds.writeExternal(objectOutput)

        val loudsTemp = LOUDS()

        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/test.dat"))
        val louds2 = loudsTemp.readExternal(objectInput)

        val word = "揺れによる"

        println(louds2.getLetter(louds2.getNodeIndex(word)))
        assertEquals(
            expected = word,
            actual = louds2.getLetter(louds2.getNodeIndex(word))
        )


    }

}