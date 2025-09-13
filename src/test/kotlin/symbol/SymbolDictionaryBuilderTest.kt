package symbol

import com.kazumaproject.symbol.SymbolDictionaryBuilder
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class SymbolDictionaryBuilderTest {

    private var symbolDictionaryBuilder: SymbolDictionaryBuilder? = null

    @BeforeEach
    fun setUp() {
        symbolDictionaryBuilder = SymbolDictionaryBuilder()
    }

    @Test
    fun convertSymbolDataToDictionaryList() {
        symbolDictionaryBuilder?.apply {
            val dictionaries = convertSymbolDataToDictionaryList("src/main/bin/symbol.tsv")
            println("symbol size ${dictionaries.size}")
            println("${dictionaries.subList(0, 10)}")
            println("${dictionaries.filter { it.tango == "\"" }}")
            println("${dictionaries.filter { it.tango == "\'" }}")
            println("${dictionaries.filter { it.tango == "”" }}")
            println("${dictionaries.filter { it.tango == "ヱ" }}")
        }

    }
}
