package com.kazumaproject.quantity

import java.io.File

object QuantitySource {
    fun parse(dir: File, idDef: File = File("src/main/resources/id.def")): QuantityDictionary {
        val units = File(dir, "units.txt").readLines().map(String::trim).filter { it.isNotEmpty() && !it.startsWith("#") }.toSet()
        require(units.isNotEmpty())
        val suffixes = File(dir, "suffixes.tsv").readLines().filter { it.isNotBlank() && !it.startsWith("#") }.mapIndexed { index, line ->
            val fields = line.split('\t'); require(fields.size == 3) { "suffixes.tsv:${index + 1}: expected 3 columns" }
            require(fields.all { it.isNotBlank() && it.length <= 32 })
            require(fields[1].all { it in 'ぁ'..'ゖ' })
            require(fields[0] in units && fields[0] + fields[2] in units) { "Unknown suffix unit: $line" }
            QuantityDictionary.Suffix(fields[0], fields[1], fields[2])
        }
        val rules = dir.listFiles().orEmpty().filter { it.extension == "ngram" }.sortedBy { it.name }.flatMap { file ->
            file.readLines().flatMapIndexed { index, raw ->
                val line = raw.trim(); if (line.isEmpty() || line.startsWith("#")) return@flatMapIndexed emptyList()
                val parts = line.split(Regex("\\s+\\+\\s+"))
                require(parts.size in 2..5) { "${file.name}:${index + 1}: expected 2–5 conditions" }
                val alternatives = parts.map { part ->
                    val quantity = Regex("quantity\\(\"([^\"]+)\"\\)").matchEntire(part)
                    val words = Regex("words\\(\"([a-z][a-z0-9-]*\\.words)\"\\)").matchEntire(part)
                    val word = Regex("\"([^\"]+)\"").matchEntire(part)
                    when {
                        quantity != null -> listOf(QuantityDictionary.Feature.Quantity(quantity.groupValues[1].also { require(it in units) { "Unknown unit: $it" } }))
                        word != null -> listOf(QuantityDictionary.Feature.Word(word.groupValues[1]))
                        words != null -> File(dir, words.groupValues[1]).readLines().map(String::trim)
                            .filter { it.isNotEmpty() && !it.startsWith("#") }.distinct().also { values ->
                                require(values.size in 1..256 && values.all { it.length <= 64 })
                            }.map { QuantityDictionary.Feature.Word(it) }
                        else -> throw IllegalArgumentException("${file.name}:${index + 1}: invalid feature: $part")
                    }
                }
                alternatives.fold(listOf(emptyList<QuantityDictionary.Feature>())) { prefixes, choices ->
                    require(prefixes.size * choices.size <= 4096) { "Rule expansion too large" }
                    prefixes.flatMap { prefix -> choices.map { prefix + it } }
                }.onEach { require(it.any { f -> f is QuantityDictionary.Feature.Quantity }) }
            }
        }
        val numericIds = idDef.readLines().filter { it.substringAfter(' ').startsWith("名詞,数,") }
            .map { it.substringBefore(' ').toInt() }.toSet()
        require(numericIds.isNotEmpty()) { "Missing numeric POS contexts" }
        val counterIds = idDef.readLines().filter { it.substringAfter(' ').startsWith("名詞,接尾,助数詞,") }
            .map { it.substringBefore(' ').toInt() }.toSet()
        require(counterIds.isNotEmpty()) { "Missing counter POS contexts" }
        val dictionary = QuantityDictionary(rules.distinct(), suffixes, numericIds, counterIds)
        return QuantityDictionary.read(dictionary.write()) // Same validation as the consumer.
    }
}

fun main(args: Array<String>) {
    require(args.size == 2) { "Expected source directory and output file" }
    val dictionary = QuantitySource.parse(File(args[0]))
    File(args[1]).also { it.parentFile.mkdirs() }.writeBytes(dictionary.write())
    println("quantity-v${QuantityDictionary.VERSION}: ${dictionary.rules.size} rules, ${dictionary.suffixes.size} suffixes")
}
