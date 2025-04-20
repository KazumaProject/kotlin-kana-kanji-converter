package english

import com.kazumaproject.english.EnglishLOUDS
import com.kazumaproject.english.EnglishLOUDSConverter
import com.kazumaproject.english.prefix.EnglishNodeTree
import java.io.*
import kotlin.test.Test

class EnglishLOUDSTest {

    @Test
    fun buildEnglishLOUDS() {
        val filePath = "/wikitext103_unigrams_with_cost.txt"
        val wordPairs: List<Pair<String, Int>> =
            object {}::class.java.getResourceAsStream(filePath)?.bufferedReader()?.useLines { lines ->
                lines.map { it.trim().split(Regex("\\s+")) }
                    .filter { it.size == 2 }
                    .map { (word, count) -> word to count.toInt() }
                    .toList()
            } ?: emptyList()

        println("${wordPairs.size}")

        val englsihTree = EnglishNodeTree()
        wordPairs.forEach {
            if (it.first == "on") {
                println("insert: ${it.first} ${it.second}")
            }
            englsihTree.insert(it.first, it.second)
        }
        println("${wordPairs.take(50)}")
        val englishLOUDSTemp = EnglishLOUDSConverter().convert(englsihTree.root)
        englishLOUDSTemp.convertListToBitSet()
        val objectOutputEnglish =
            ObjectOutputStream(BufferedOutputStream(FileOutputStream("./src/main/resources/english.dat")))
        englishLOUDSTemp.writeExternal(objectOutputEnglish)
        val objectInputEnglish = ObjectInputStream(FileInputStream("./src/main/resources/english.dat"))
        val louds = EnglishLOUDS().readExternal(objectInputEnglish)
        println(louds.commonPrefixSearch("on").map {
            it + " " + louds.getTermId(louds.getNodeIndex(it))
        })
    }

}
