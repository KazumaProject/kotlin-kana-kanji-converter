package mozc_runtime.dictionary

// Ported from mozc/src/dictionary/user_dictionary.*
class UserDictionary(
    entries: List<Token>,
) : DictionaryInterface {
    private val entries: List<Token> = entries.toList()
    private val byKey: Map<String, List<Token>> = this.entries.groupBy { it.key }
    private val byValue: Map<String, List<Token>> = this.entries.groupBy { it.value }

    override fun hasKey(key: String): Boolean = byKey.containsKey(key)

    override fun hasValue(value: String): Boolean = byValue.containsKey(value)

    override fun lookupPrefix(key: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { key.startsWith(it.key) }
            .forEach(callback)
    }

    override fun lookupExact(key: String, callback: (Token) -> Unit) {
        byKey[key].orEmpty().forEach(callback)
    }

    override fun lookupPredictive(key: String, callback: (Token) -> Unit) {
        entries.asSequence()
            .filter { it.key.startsWith(key) }
            .forEach(callback)
    }

    override fun lookupReverse(value: String, callback: (Token) -> Unit) {
        byValue[value].orEmpty().forEach { token ->
            callback(token.copy(key = token.value, value = token.key))
        }
    }

    override fun lookupComment(key: String, value: String): String? = null

    override fun populateReverseLookupCache() = Unit

    override fun clearReverseLookupCache() = Unit
}
