package emoji

import com.kazumaproject.emoji.EmojiDictionaryBuilder
import kotlin.test.BeforeTest
import kotlin.test.Test

class EmojiDictionaryBuilderTest {

    private var emojiDictionaryBuilder: EmojiDictionaryBuilder? = null

    @BeforeTest
    fun setUp() {
        emojiDictionaryBuilder = EmojiDictionaryBuilder()
    }

    @Test
    fun convertEmojiDataToDictionaryList() {
        emojiDictionaryBuilder?.apply {
            val dictionaries = convertEmojiDataToDictionaryList("src/main/bin/emoji_data.tsv")
            println("emoji size ${dictionaries.size}")
            println("${dictionaries.subList(0,10)}")
        }
    }
}