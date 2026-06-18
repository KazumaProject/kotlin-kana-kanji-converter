package mozc_runtime.storage.louds

import mozc_runtime.MozcDictionaryGoldenSupport
import mozc_runtime.MozcGoldenTestSupport
import mozc_runtime.dictionary.system.SystemDictionaryCodec
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LoudsTrieGoldenTest {
    @Test
    fun keyTrieSupportsExactPrefixAndPredictiveTraversal() {
        val dictionary = MozcDictionaryGoldenSupport.systemDictionary()
        val codec = SystemDictionaryCodec()
        val keyTrie = dictionary.keyTrie()
        val encodedKey = codec.encodeKeyToBytes("へんかん")

        val keyId = keyTrie.exactSearch(encodedKey)
        assertTrue(keyId >= 0, "key trie exact search should find へんかん")
        assertEquals("へんかん", codec.decodeKey(keyTrie.restoreKeyBytes(keyId)))

        val prefixes = ArrayList<String>()
        keyTrie.prefixSearch(encodedKey) { _, node ->
            prefixes += codec.decodeKey(keyTrie.restoreKeyBytes(node))
        }
        assertTrue("へん" in prefixes, "key trie common prefix search should find へん")
        assertTrue("へんかん" in prefixes, "key trie common prefix search should find へんかん")

        val predictive = keyTrie.terminalNodesInBreadthFirstOrder(keyTrie.traverse(codec.encodeKeyToBytes("へん"))!!, 4096)
            .map { codec.decodeKey(keyTrie.restoreKeyBytes(it)) }
        assertTrue("へんかん" in predictive, "key trie predictive traversal should reach へんかん")
    }

    @Test
    fun valueTrieSupportsReverseValueLookup() {
        val fixture = MozcDictionaryGoldenSupport.readLookupFixture(
            MozcGoldenTestSupport.fixture("dictionary/system_dictionary_lookup.json"),
        )
        val dictionary = MozcDictionaryGoldenSupport.systemDictionary()
        val codec = SystemDictionaryCodec()
        val valueTrie = dictionary.valueTrie()
        val firstNormalValue = fixture.queries
            .asSequence()
            .flatMap { it.lookupExact.asSequence() }
            .map { it.value }
            .first { valueTrie.exactSearch(codec.encodeValueToBytes(it)) >= 0 }

        val valueId = valueTrie.exactSearch(codec.encodeValueToBytes(firstNormalValue))
        assertTrue(valueId >= 0, "value trie exact search should find $firstNormalValue")
        assertEquals(firstNormalValue, codec.decodeValue(valueTrie.restoreKeyBytes(valueId)))
    }
}
