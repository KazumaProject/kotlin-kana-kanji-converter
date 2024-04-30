package connection_id

import com.kazumaproject.connection_id.ConnectionIdBuilder
import java.io.FileOutputStream
import java.io.ObjectOutputStream
import kotlin.test.Test

/** 2662 **/
class ConnectionIdTest {

    @Test
    fun `Test to build octree with connection_single_column_txt`(){

        val lines = this::class.java.getResourceAsStream("/connection_single_column.txt")
            ?.bufferedReader()
            ?.readLines()

        val connectionIdBuilder = ConnectionIdBuilder()
        val objectOutput = ObjectOutputStream(FileOutputStream("./src/test/resources/connectionId.dat"))
        lines?.let { l ->
            connectionIdBuilder.build(objectOutput,l.map { it.toShort() })
        }
    }

}