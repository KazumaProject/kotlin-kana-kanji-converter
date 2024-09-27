package symbol

import com.kazumaproject.symbol.SymbolDictionaryBuilder
import kotlin.test.BeforeTest
import kotlin.test.Test

class SymbolDictionaryBuilderTest {

    private var symbolDictionaryBuilder: SymbolDictionaryBuilder? = null

    @BeforeTest
    fun setUp() {
        symbolDictionaryBuilder = SymbolDictionaryBuilder()
    }

    @Test
    fun convertSymbolDataToDictionaryList() {
        symbolDictionaryBuilder?.apply {
            val dictionaries = convertSymbolDataToDictionaryList("src/main/bin/symbol.tsv")
            println("symbol size ${dictionaries.size}")
            println("${dictionaries.subList(0, 10)}")
        }

    }
}