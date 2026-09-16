package louds

import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.english.EnglishLOUDS
import com.kazumaproject.english.EnglishLOUDSConverter
import com.kazumaproject.english.prefix.EnglishNodeTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.util.BitSet
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LOUDSWithTermIdExactMatchTest {

    @Test
    fun commonLookupRequiresTerminalNode() {
        val tree = PrefixTreeWithTermId().apply {
            insert("car")
            insert("cart")
        }
        val converted = ConverterWithTermId().convert(tree.root).apply {
            convertListToBitSet()
        }
        val louds = LOUDSWithTermId(
            converted.LBS,
            converted.labels,
            converted.isLeaf,
            converted.termIds.toIntArray(),
        )

        assertExactLookupContract(
            lbs = louds.LBS,
            isLeaf = louds.isLeaf,
            getNodeIndex = louds::getNodeIndex,
            getTermId = louds::getTermId,
            getLetter = louds::getLetter,
        )
    }

    @Test
    fun englishLookupRequiresTerminalNode() {
        val tree = EnglishNodeTree().apply {
            insert("car", 10)
            insert("cart", 20)
        }
        val converted = EnglishLOUDSConverter().convert(tree.root).apply {
            convertListToBitSet()
        }
        val louds = EnglishLOUDS(
            converted.LBS,
            converted.labels,
            converted.isLeaf,
            converted.costList.toShortArray(),
        )

        assertExactLookupContract(
            lbs = louds.LBS,
            isLeaf = louds.isLeaf,
            getNodeIndex = louds::getNodeIndex,
            getTermId = { louds.getTermId(it).toInt() },
            getLetter = louds::getLetter,
        )
    }

    private fun assertExactLookupContract(
        lbs: BitSet,
        isLeaf: BitSet,
        getNodeIndex: (String) -> Int,
        getTermId: (Int) -> Int,
        getLetter: (Int) -> String,
    ) {
        val exactNode = getNodeIndex("car")
        assertTrue(exactNode > 0)
        assertEquals("car", getLetter(exactNode))
        assertTrue(getTermId(exactNode) > 0)

        listOf("", "c", "ca", "cab").forEach { input ->
            assertEquals(-1, getNodeIndex(input), input)
        }

        val internalNode = (2 until lbs.size()).first { nodeIndex ->
            lbs[nodeIndex] && !isLeaf[nodeIndex] && getLetter(nodeIndex) == "ca"
        }
        listOf(-1, internalNode, lbs.size()).forEach { nodeIndex ->
            assertEquals(-1, getTermId(nodeIndex), "nodeIndex=$nodeIndex")
        }
    }
}
