package com.kazumaproject.quantity

import com.kazumaproject.dictionary.models.Dictionary
import java.io.File

/** Adds reviewed readings using an existing numeric lexeme's POS and cost, never a guessed discount. */
object QuantityLexicalAliases {
    data class Reading(val value: Int, val unit: String, val reading: String)
    fun read(file: File): List<Reading> = file.readLines().filter { it.isNotBlank() && !it.startsWith("#") }.map { line ->
        val fields = line.split('\t')
        require(fields.size == 3) { "Invalid counter reading: $line" }
        Reading(fields[0].toInt(), fields[1], fields[2]).also {
            require(it.value in 1..10 && it.unit.isNotBlank() && it.reading.all { ch -> ch in 'ぁ'..'ゖ' })
        }
    }.also { require(it.distinct().size == it.size) }

    fun build(entries: List<Dictionary>, readings: List<Reading>, numericIds: Set<Int>): List<Dictionary> {
        val numbers = listOf("", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十")
        val numeric = entries.filter { it.leftId.toInt() in numericIds }.groupBy { it.tango }
        val existing = entries.mapTo(HashSet()) { listOf(it.yomi, it.tango, it.leftId, it.rightId) }
        return readings.flatMap { reading ->
            val outputs = listOf(reading.value.toString(), reading.value.toString().map { (it.code + 0xfee0).toChar() }.joinToString(""), numbers[reading.value]).map { it + reading.unit }
            outputs.flatMap { output -> numeric[output].orEmpty().groupBy { it.leftId to it.rightId }.values.mapNotNull { variants ->
                val source = variants.minBy { it.cost }
                if (existing.add(listOf(reading.reading, source.tango, source.leftId, source.rightId))) source.copy(yomi = reading.reading) else null
            } }
        }
    }
}
