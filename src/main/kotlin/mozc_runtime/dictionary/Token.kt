package mozc_runtime.dictionary

data class Token(
    val key: String,
    val value: String,
    val lid: Int,
    val rid: Int,
    val cost: Int,
    val attributes: Int = Attributes.None,
) {
    object Attributes {
        const val None: Int = 0
        const val SpellingCorrection: Int = 1
        const val SuffixDictionary: Int = 1 shl 6
        const val UserDictionary: Int = 1 shl 7
    }
}
