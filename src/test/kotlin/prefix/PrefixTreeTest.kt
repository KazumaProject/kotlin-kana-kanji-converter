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
    
}