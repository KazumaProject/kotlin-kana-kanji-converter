package glide

data class QwertyGlideIndexedEntry(
    val word: String,
    val wordCost: Int,
    val firstChar: Char,
    val lastChar: Char,
    val length: Int,
    val characterMask: Int,
    val transitionMask: Long
) {
    companion object {
        fun from(word: String, wordCost: Int): QwertyGlideIndexedEntry {
            return QwertyGlideIndexedEntry(
                word = word,
                wordCost = wordCost,
                firstChar = word.first(),
                lastChar = word.last(),
                length = word.length,
                characterMask = word.characterMask(),
                transitionMask = word.transitionMask()
            )
        }
    }
}

private fun String.characterMask(): Int {
    var mask = 0
    for (ch in this) {
        mask = mask or (1 shl (ch - 'a'))
    }
    return mask
}

private fun String.transitionMask(): Long {
    var mask = 0L
    for (i in 1 until length) {
        val from = this[i - 1] - 'a'
        val to = this[i] - 'a'
        val bucket = (from * 31 + to) and 63
        mask = mask or (1L shl bucket)
    }
    return mask
}
