package com.kazumaproject.mozc.zeroquery

data class ZeroQueryEntry(
    val key: String,
    val value: String,
    val type: ZeroQueryType,
)

typealias ZeroQueryEntryMap = LinkedHashMap<String, MutableList<ZeroQueryEntry>>

internal object UnicodeCodePointStringComparator : Comparator<String> {
    override fun compare(left: String, right: String): Int {
        var leftIndex = 0
        var rightIndex = 0
        while (leftIndex < left.length && rightIndex < right.length) {
            val leftCodePoint = left.codePointAt(leftIndex)
            val rightCodePoint = right.codePointAt(rightIndex)
            if (leftCodePoint != rightCodePoint) {
                return leftCodePoint.compareTo(rightCodePoint)
            }
            leftIndex += Character.charCount(leftCodePoint)
            rightIndex += Character.charCount(rightCodePoint)
        }
        return (left.length - leftIndex).compareTo(right.length - rightIndex)
    }
}

internal fun isAsciiKey(key: String): Boolean = key.all { it.code < 128 }

internal fun splitPreservingEmpty(value: String, delimiter: Char): List<String> {
    val result = mutableListOf<String>()
    var start = 0
    while (true) {
        val index = value.indexOf(delimiter, start)
        if (index < 0) {
            result += value.substring(start)
            return result
        }
        result += value.substring(start, index)
        start = index + 1
    }
}

internal fun ZeroQueryEntryMap.appendEntry(entry: ZeroQueryEntry) {
    getOrPut(entry.key) { mutableListOf() }.add(entry)
}

internal fun zeroQueryParseError(filePath: String, lineNumber: Int, rawLine: String, reason: String): Nothing {
    error("Failed to parse zero query data: file path=$filePath, line number=$lineNumber, raw line='$rawLine', reason=$reason")
}
