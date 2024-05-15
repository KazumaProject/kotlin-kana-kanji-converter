package single_kanji

import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.single_kanji.SingleKanjiBuilder
import kotlin.math.sin
import kotlin.test.Test

class SingleKanjiTest {
    @Test
    fun `Test build single kanji`(){
        val list = listOf("/dictionary00.txt")
        val dicUtils = DicUtils()
        val a = dicUtils.getListDictionary(list,"/single_kanji.tsv")
        println("${a.groupBy { it.yomi }["こな"]}")
    }

}