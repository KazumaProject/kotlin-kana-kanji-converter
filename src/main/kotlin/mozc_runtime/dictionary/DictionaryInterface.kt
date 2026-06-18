package mozc_runtime.dictionary

interface DictionaryInterface {
    fun hasKey(key: String): Boolean
    fun hasValue(value: String): Boolean
    fun lookupPrefix(
        key: String,
        callback: (Token) -> Unit,
    )
    fun lookupExact(
        key: String,
        callback: (Token) -> Unit,
    )
    fun lookupPredictive(
        key: String,
        callback: (Token) -> Unit,
    )
    fun lookupReverse(
        value: String,
        callback: (Token) -> Unit,
    )
    fun lookupComment(
        key: String,
        value: String,
    ): String?
    fun populateReverseLookupCache()
    fun clearReverseLookupCache()
}
