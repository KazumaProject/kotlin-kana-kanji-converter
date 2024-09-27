package emoticon

import com.kazumaproject.emoticon.EmoticonDictionaryBuilder
import kotlin.test.BeforeTest
import kotlin.test.Test

class EmoticonDictionaryBuilderTest {

    private var emoticonDictionaryBuilder: EmoticonDictionaryBuilder? = null

    @BeforeTest
    fun setUp() {
        emoticonDictionaryBuilder = EmoticonDictionaryBuilder()
    }

    @Test
    fun convertEmoticonDataToDictionaryList() {
        emoticonDictionaryBuilder?.apply {
            val dictionaries = convertEmoticonDataToDictionaryList("src/main/bin/emoticon.tsv")
            println("emoticon size ${dictionaries.size}")
            println("${dictionaries.subList(0, 10)}")
        }
    }
}