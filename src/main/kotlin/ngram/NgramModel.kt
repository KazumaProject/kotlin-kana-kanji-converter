package com.kazumaproject.ngram

sealed interface NgramFeature {
    data class Word(val value: String) : NgramFeature
    data class Pos(val value: String) : NgramFeature
    data object Any : NgramFeature
}

data class NgramRule(
    val features: List<NgramFeature>,
    val source: String,
    val lineNumber: Int,
)

object NgramEncoding {
    const val MAGIC = 0x4A4B4E47 // JKNG
    const val VERSION = 2
    const val HEADER_SIZE = 64
    const val STATE_SIZE = 8
    const val EDGE_SIZE = 8
    const val SIGNATURE_BASE = 0x120000
    const val WORD_START = 0x130000
    const val WORD_END = 0x130001
    const val POS_BASE = 0x140000

    const val KIND_WORD = 1
    const val KIND_POS = 2
    const val KIND_ANY = 3

    fun signature(features: List<NgramFeature>): Int {
        var result = features.size
        features.forEachIndexed { index, feature ->
            val kind = when (feature) {
                is NgramFeature.Word -> KIND_WORD
                is NgramFeature.Pos -> KIND_POS
                NgramFeature.Any -> KIND_ANY
            }
            result = result or (kind shl (3 + index * 2))
        }
        return result
    }

    fun kindAt(signature: Int, index: Int): Int =
        (signature ushr (3 + index * 2)) and 0x3

    fun order(signature: Int): Int = signature and 0x7
}
