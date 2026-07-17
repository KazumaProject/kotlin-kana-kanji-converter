package com.kazumaproject.engine

import com.kazumaproject.graph.Node

data class ConversionResult(
    val input: String,
    val bestPath: List<ConversionPathNode>,
) {
    val value: String = bestPath.joinToString(separator = "") { it.value }
}

data class ConversionPathNode(
    val key: String,
    val value: String,
    val lid: Int,
    val rid: Int,
    val wcost: Int,
    val cost: Int,
    val start: Int,
    val end: Int,
)

internal fun Node.toConversionPathNode(): ConversionPathNode =
    ConversionPathNode(
        key = key,
        value = tango,
        lid = l.toInt(),
        rid = r.toInt(),
        wcost = wcost,
        cost = totalCost,
        start = sPos,
        end = sPos + len.toInt(),
    )
