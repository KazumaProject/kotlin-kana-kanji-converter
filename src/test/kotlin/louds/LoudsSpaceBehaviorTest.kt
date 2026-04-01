package louds

import com.kazumaproject.Louds.Converter
import com.kazumaproject.prefix.PrefixTree
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LoudsSpaceBehaviorTest {

    @Test
    fun preservesSpaceInLookupAndRestore() {
        val tree = PrefixTree()
        val tangoWithSpace = "foo bar"
        tree.insert(tangoWithSpace)

        val louds = Converter().convert(tree.root).apply {
            convertListToBitSet()
        }

        val nodeIndex = louds.getNodeIndex(tangoWithSpace)
        assertTrue(nodeIndex >= 0, "Word with space should be searchable in LOUDS")
        assertEquals(tangoWithSpace, louds.getLetter(nodeIndex))
    }

    @Test
    fun doesNotMatchWhenSpaceIsRemoved() {
        val tree = PrefixTree()
        tree.insert("foo bar")

        val louds = Converter().convert(tree.root).apply {
            convertListToBitSet()
        }

        assertEquals(-1, louds.getNodeIndex("foobar"))
        print(louds.getLetter(louds.getNodeIndex("foo bar")))
    }
}
