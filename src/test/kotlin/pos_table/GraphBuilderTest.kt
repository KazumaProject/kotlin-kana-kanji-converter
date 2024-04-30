package pos_table

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.graph.GraphBuilder
import com.kazumaproject.viterbi.FindPath
import java.io.FileInputStream
import java.io.ObjectInputStream
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.time.measureTime

class GraphBuilderTest {

    private lateinit var graphBuilder: GraphBuilder
    private lateinit var yomiTrie: LOUDSWithTermId
    private lateinit var tangoTrie: LOUDS
    private lateinit var connectionIds: List<Short>
    private lateinit var findPath: FindPath

    @BeforeTest
    fun setUp() {
        graphBuilder = GraphBuilder()
    }

    @Test
    fun `Build Graph Test`() {

        val objectInputYomi = ObjectInputStream(FileInputStream("src/test/resources/yomi.dat"))
        val objectInputTango = ObjectInputStream(FileInputStream("src/test/resources/tango.dat"))
        val objectInputTokenArray = ObjectInputStream(FileInputStream("src/test/resources/token.dat"))
        val objectInputConnectionId = ObjectInputStream(FileInputStream("src/test/resources/connectionIds.dat"))

        val tokenArray = TokenArray()

        val yomiLoadingTime = measureTime {
            yomiTrie = LOUDSWithTermId().readExternal(objectInputYomi)
        }
        val tangoLoadingTime = measureTime {
            tangoTrie = LOUDS().readExternal(objectInputTango)
        }
        val tokenArrayLoadingTime = measureTime {
            tokenArray.readExternal(objectInputTokenArray)
        }
        tokenArray.readPOSTable(0)

        val connectionIdsLoadingTime = measureTime {
            connectionIds = ConnectionIdBuilder().read(objectInputConnectionId)
        }

        val query = "わたしのなまえはなかのです"

        val graph = graphBuilder.constructGraph(
            query,
            yomiTrie,
            tangoTrie,
            tokenArray,
        )

        println("loading time yomi.dat: $yomiLoadingTime")
        println("loading time tango.dat: $tangoLoadingTime")
        println("loading token tango.dat: $tokenArrayLoadingTime")
        println("loading connection ids: $connectionIdsLoadingTime")

        findPath = FindPath()

        val resultTime = measureTime {
            val result = findPath.backwardAStar(graph,query.length, connectionIds,8)
            println(result + "\n")
            result.forEach {
                println(it)
            }
        }

        println("a* algorithm query time: $resultTime")

    }

}