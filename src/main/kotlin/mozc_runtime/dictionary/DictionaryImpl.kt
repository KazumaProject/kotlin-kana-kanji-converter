package mozc_runtime.dictionary

// Ported from mozc/src/dictionary/dictionary_impl.*
class DictionaryImpl(
    private val dictionaries: List<DictionaryInterface>,
) : DictionaryInterface {
    constructor(vararg dictionaries: DictionaryInterface) : this(dictionaries.toList())

    init {
        require(dictionaries.isNotEmpty()) { "DictionaryImpl requires at least one dictionary" }
    }

    override fun hasKey(key: String): Boolean = dictionaries.any { it.hasKey(key) }

    override fun hasValue(value: String): Boolean = dictionaries.any { it.hasValue(value) }

    override fun lookupPrefix(key: String, callback: (Token) -> Unit) {
        dictionaries.forEach { it.lookupPrefix(key, callback) }
    }

    override fun lookupPrefixWithOptions(
        key: String,
        kanaModifierInsensitiveConversion: Boolean,
        callback: (Token) -> Unit,
    ) {
        dictionaries.forEach { dictionary ->
            dictionary.lookupPrefixWithOptions(key, kanaModifierInsensitiveConversion, callback)
        }
    }

    override fun lookupExact(key: String, callback: (Token) -> Unit) {
        dictionaries.forEach { it.lookupExact(key, callback) }
    }

    override fun lookupPredictive(key: String, callback: (Token) -> Unit) {
        dictionaries.forEach { it.lookupPredictive(key, callback) }
    }

    override fun lookupReverse(value: String, callback: (Token) -> Unit) {
        dictionaries.forEach { it.lookupReverse(value, callback) }
    }

    override fun lookupComment(key: String, value: String): String? =
        dictionaries.firstNotNullOfOrNull { it.lookupComment(key, value) }

    override fun populateReverseLookupCache() {
        dictionaries.forEach { it.populateReverseLookupCache() }
    }

    override fun clearReverseLookupCache() {
        dictionaries.forEach { it.clearReverseLookupCache() }
    }
}
