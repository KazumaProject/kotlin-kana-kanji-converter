package reading_correction

import com.kazumaproject.reading_correction.ReadingCorrectionBuilder
import kotlin.test.BeforeTest
import kotlin.test.Test

class ReadingCorrectionBuilderTest {

    private var readingCorrectionBuilder: ReadingCorrectionBuilder? = null

    @BeforeTest
    fun setUp() {
        readingCorrectionBuilder = ReadingCorrectionBuilder()
    }

    @Test
    fun convertEmoticonDataToDictionaryList() {
        readingCorrectionBuilder?.apply {
            val dictionaries = this.parseReadingCorrectionTSV("src/main/bin/reading_correction.tsv")
            println("reading_correction size ${dictionaries.size}")
            println("${dictionaries.subList(0, 10)}")
        }
    }

}