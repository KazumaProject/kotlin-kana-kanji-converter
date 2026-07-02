package com.kazumaproject.ngram

import java.text.Normalizer

const val NGRAM_PRESENCE_VERSION = 1
const val NGRAM_PRESENCE_FORMAT = "BDZ_MPHF_PRESENCE_EXACT"
const val NGRAM_PRESENCE_FORMAT_ID = 1
const val NGRAM_PRESENCE_KEY_MODE = "TERM_ID_32_LEFT_ID_16_RIGHT_ID_16"
const val NGRAM_PRESENCE_KEY_MODE_ID = 1
const val NGRAM_SECTION_COUNT = 5

data class NgramRule(
    val order: Int,
    val reading: String,
    val surfaces: List<String>,
    val source: String,
    val comment: String,
    val sourceFile: String,
    val lineNumber: Int,
)

data class NgramRuleKey(
    val order: Int,
    val reading: String,
    val surfaces: List<String>,
) : Comparable<NgramRuleKey> {
    override fun compareTo(other: NgramRuleKey): Int {
        compareValues(order, other.order).takeIf { it != 0 }?.let { return it }
        compareValues(reading, other.reading).takeIf { it != 0 }?.let { return it }
        for (index in 0 until maxOf(surfaces.size, other.surfaces.size)) {
            compareValues(surfaces.getOrElse(index) { "" }, other.surfaces.getOrElse(index) { "" })
                .takeIf { it != 0 }
                ?.let { return it }
        }
        return 0
    }
}

data class NgramSourceReadResult(
    val rules: List<NgramRule>,
    val sourceFiles: List<String>,
    val sourceRowCount: Int,
)

data class NgramRuleNormalizeResult(
    val rules: List<NgramRule>,
    val duplicateCount: Int,
    val skippedCount: Int,
)

data class UnresolvedNgramRule(
    val order: Int,
    val reading: String,
    val surfaces: List<String>,
    val sourceFile: String,
    val lineNumber: Int,
    val reason: String,
)

data class NgramTerm(
    val termId: Int,
    val reading: String,
    val surface: String,
    val leftId: Short,
    val rightId: Short,
    val cost: Short,
) {
    val nodeKey: Long
        get() = NgramNodeKey.pack(termId, leftId, rightId)
}

object NgramNodeKey {
    fun pack(termId: Int, leftId: Short, rightId: Short): Long {
        return ((termId.toLong() and 0xffffffffL) shl 32) or
                ((leftId.toLong() and 0xffffL) shl 16) or
                (rightId.toLong() and 0xffffL)
    }

    fun termId(nodeKey: Long): Int = (nodeKey ushr 32).toInt()

    fun leftId(nodeKey: Long): Short = ((nodeKey ushr 16) and 0xffffL).toShort()

    fun rightId(nodeKey: Long): Short = (nodeKey and 0xffffL).toShort()
}

data class NgramKeySequence(
    val order: Int,
    val keys: LongArray,
) : Comparable<NgramKeySequence> {
    init {
        require(order in 1..NGRAM_SECTION_COUNT) { "order must be 1..$NGRAM_SECTION_COUNT: $order" }
        require(keys.size == order) { "key count must match order: order=$order keyCount=${keys.size}" }
    }

    override fun compareTo(other: NgramKeySequence): Int {
        compareValues(order, other.order).takeIf { it != 0 }?.let { return it }
        for (index in 0 until maxOf(keys.size, other.keys.size)) {
            compareValues(keys.getOrElse(index) { Long.MIN_VALUE }, other.keys.getOrElse(index) { Long.MIN_VALUE })
                .takeIf { it != 0 }
                ?.let { return it }
        }
        return 0
    }

    override fun equals(other: Any?): Boolean {
        return other is NgramKeySequence && order == other.order && keys.contentEquals(other.keys)
    }

    override fun hashCode(): Int {
        var result = order
        keys.forEach { key ->
            result = 31 * result + (key xor (key ushr 32)).toInt()
        }
        return result
    }
}

object NgramRuleNormalizer {
    fun normalizeAndDedupe(rules: List<NgramRule>): NgramRuleNormalizeResult {
        val normalized = rules.map(::normalize).sortedWith(compareBy<NgramRule> {
            it.key()
        }.thenBy { it.sourceFile }.thenBy { it.lineNumber })

        val unique = mutableListOf<NgramRule>()
        var duplicateCount = 0
        var previousKey: NgramRuleKey? = null
        normalized.forEach { rule ->
            val key = rule.key()
            if (previousKey == key) {
                duplicateCount += 1
            } else {
                unique += rule
                previousKey = key
            }
        }
        return NgramRuleNormalizeResult(
            rules = unique,
            duplicateCount = duplicateCount,
            skippedCount = 0,
        )
    }

    fun normalize(rule: NgramRule): NgramRule {
        require(rule.order in 1..NGRAM_SECTION_COUNT) {
            "Invalid N-gram order at ${rule.sourceFile}:${rule.lineNumber}: order=${rule.order}"
        }
        val reading = normalizeText(rule.reading)
        require(reading.isNotEmpty()) {
            "Invalid N-gram rule at ${rule.sourceFile}:${rule.lineNumber}: reading is empty"
        }
        require(rule.surfaces.size == NGRAM_SECTION_COUNT) {
            "Invalid N-gram rule at ${rule.sourceFile}:${rule.lineNumber}: expected $NGRAM_SECTION_COUNT surface columns"
        }

        val surfaces = rule.surfaces.map(::normalizeText)
        surfaces.take(rule.order).forEachIndexed { index, surface ->
            require(surface.isNotEmpty()) {
                "Invalid N-gram rule at ${rule.sourceFile}:${rule.lineNumber}: surface${index + 1} is empty"
            }
        }
        surfaces.drop(rule.order).forEachIndexed { index, surface ->
            require(surface.isEmpty()) {
                "Invalid N-gram rule at ${rule.sourceFile}:${rule.lineNumber}: surface${rule.order + index + 1} must be empty"
            }
        }

        return rule.copy(
            reading = reading,
            surfaces = surfaces,
            source = normalizeText(rule.source),
            comment = normalizeText(rule.comment),
        )
    }

    fun NgramRule.key(): NgramRuleKey = NgramRuleKey(order, reading, surfaces.take(order))

    private fun normalizeText(value: String): String = Normalizer.normalize(value.trim(), Normalizer.Form.NFC)
}

fun splitPreservingEmpty(value: String, delimiter: Char): List<String> {
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
