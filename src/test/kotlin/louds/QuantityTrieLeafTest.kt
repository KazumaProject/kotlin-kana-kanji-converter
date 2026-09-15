package louds

import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.util.BitSet
import kotlin.test.*

class QuantityTrieLeafTest {
    @Test fun compactLeafCannotLinkBackToRoot() {
        val tree = PrefixTreeWithTermId()
        val words = (0 until 32).map { ('あ'.code + it).toChar().toString() }
        words.forEach { tree.insert(it) }
        val original = ConverterWithTermId().convert(tree.root).apply { convertListToBitSet() }
        val compact = LOUDSWithTermId(BitSet.valueOf(original.LBS.toLongArray()), original.labels, original.isLeaf, original.termIdsSave)
        val firstChild = compact.javaClass.getDeclaredMethod("firstChild", Int::class.javaPrimitiveType).apply { isAccessible = true }
        words.forEach { word ->
            val node = compact.getNodeIndex(word)
            assertTrue(node > 0)
            assertEquals(-1, firstChild.invoke(compact, node), word)
        }
    }
}
