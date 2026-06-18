package mozc_runtime.dictionary.system

import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.Token
import mozc_runtime.storage.louds.LoudsTrie
import java.util.ArrayDeque

// Ported from mozc/src/dictionary/system/value_dictionary.*
class ValueDictionary(
    private val valueTrie: LoudsTrie,
    private val suggestionOnlyWordId: Int,
    private val codec: SystemDictionaryCodec = SystemDictionaryCodec(),
) : DictionaryInterface {
    override fun hasKey(key: String): Boolean = hasValue(key)

    override fun hasValue(value: String): Boolean = valueTrie.hasKey(codec.encodeValueToBytes(value))

    override fun lookupPrefix(key: String, callback: (Token) -> Unit) {
        Unit
    }

    override fun lookupExact(key: String, callback: (Token) -> Unit) {
        if (!isValidKey(key)) {
            return
        }
        if (valueTrie.exactSearch(codec.encodeValueToBytes(key)) >= 0) {
            callback(valueToken(key))
        }
    }

    override fun lookupPredictive(key: String, callback: (Token) -> Unit) {
        if (!isValidKey(key)) {
            return
        }
        val start = valueTrie.traverse(codec.encodeValueToBytes(key)) ?: return
        val queue = ArrayDeque<LoudsTrie.Node>()
        queue.add(start)
        while (!queue.isEmpty()) {
            val node = queue.removeFirst()
            if (valueTrie.isTerminalNode(node)) {
                callback(valueToken(codec.decodeValue(valueTrie.restoreKeyBytes(node))))
            }
            var child = valueTrie.moveToFirstChild(node)
            while (valueTrie.isValidNode(child)) {
                queue.add(child)
                child = valueTrie.moveToNextSibling(child)
            }
        }
    }

    override fun lookupReverse(value: String, callback: (Token) -> Unit) {
        Unit
    }

    override fun lookupComment(key: String, value: String): String? = null

    override fun populateReverseLookupCache() = Unit

    override fun clearReverseLookupCache() = Unit

    private fun valueToken(value: String): Token =
        Token(
            key = value,
            value = value,
            lid = suggestionOnlyWordId,
            rid = suggestionOnlyWordId,
            cost = 10000,
        )

    private fun isValidKey(key: String): Boolean {
        if (key.isEmpty()) {
            return false
        }
        return key.codePoints().findFirst().orElse(0).let { first ->
            first !in 0x3040..0x30ff && first !in 0x4e00..0x9fff
        }
    }
}
