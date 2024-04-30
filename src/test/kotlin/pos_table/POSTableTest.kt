package pos_table

import com.kazumaproject.dictionary.TokenArray
import java.io.FileInputStream
import java.io.ObjectInputStream
import kotlin.test.BeforeTest
import kotlin.test.Test

class POSTableTest {

    private lateinit var tokenArray: TokenArray

    @BeforeTest
    fun setUp() {
        tokenArray = TokenArray()
    }

    @Test
    fun `Build pos_table`(){
        val fileList = listOf(
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
            "/suffix.txt",
            "/domain.txt",
            "/era.txt"
        )
        tokenArray.buildPOSTable(
            fileList,0
        )
        tokenArray.buildPOSTableWithIndex(
            fileList,0
        )
    }

    @Test
    fun `Load pos_table`(){
        val objectInput = ObjectInputStream(FileInputStream("./src/test/resources/pos_table.dat"))
        val pos_table = objectInput.readObject() as List<Pair<Short, Short>>
        println("$pos_table")
    }
}