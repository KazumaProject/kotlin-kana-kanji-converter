package mozc_runtime.dictionary

// Ported from mozc/src/dictionary/suffix_dictionary.*
class SuffixDictionary(
    entries: List<Token>,
) : DictionaryInterface {
    private val entries: List<Token> = entries.toList()

    override fun hasKey(key: String): Boolean = entries.any { it.key == key }

    override fun hasValue(value: String): Boolean = entries.any { it.value == value }

    override fun lookupPrefix(key: String, callback: (Token) -> Unit) {
        lookupPredictive(key, callback)
    }

    override fun lookupExact(key: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.key == key }
            .forEach(callback)
    }

    override fun lookupPredictive(key: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.key.startsWith(key) }
            .forEach(callback)
    }

    override fun lookupReverse(value: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.value == value }
            .forEach { token -> callback(token.copy(key = token.value, value = token.key)) }
    }

    override fun lookupComment(key: String, value: String): String? = null

    override fun populateReverseLookupCache() = Unit

    override fun clearReverseLookupCache() = Unit
}
