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
            file.readLines().mapIndexedNotNull { index, raw ->
                val line = raw.trim(); if (line.isEmpty() || line.startsWith("#")) return@mapIndexedNotNull null
                val parts = line.split(Regex("\\s+\\+\\s+"))
                require(parts.size in 2..5) { "${file.name}:${index + 1}: expected 2–5 conditions" }
                parts.map { part ->
                    val quantity = Regex("quantity\\(\"([^\"]+)\"\\)").matchEntire(part)
                    val word = Regex("\"([^\"]+)\"").matchEntire(part)
                    when {
                        quantity != null -> QuantityDictionary.Feature.Quantity(quantity.groupValues[1].also { require(it in units) { "Unknown unit: $it" } })
                        word != null -> QuantityDictionary.Feature.Word(word.groupValues[1])
                        else -> error("${file.name}:${index + 1}: invalid feature: $part")
                    }
                }.also { require(it.any { f -> f is QuantityDictionary.Feature.Quantity }) }
            }
        }
        val numericIds = idDef.readLines().filter { it.substringAfter(' ').startsWith("名詞,数,") }
            .map { it.substringBefore(' ').toInt() }.toSet()
        require(numericIds.isNotEmpty()) { "Missing numeric POS contexts" }
        val counterIds = idDef.readLines().filter { it.substringAfter(' ').startsWith("名詞,接尾,助数詞,") }
            .map { it.substringBefore(' ').toInt() }.toSet()
        require(counterIds.isNotEmpty()) { "Missing counter POS contexts" }
        val dictionary = QuantityDictionary(rules, suffixes, numericIds, counterIds)
        return QuantityDictionary.read(dictionary.write()) // Same validation as the consumer.
    }
}

fun main(args: Array<String>) {
    require(args.size == 2) { "Expected source directory and output file" }
    val dictionary = QuantitySource.parse(File(args[0]))
    File(args[1]).also { it.parentFile.mkdirs() }.writeBytes(dictionary.write())
    println("quantity-v${QuantityDictionary.VERSION}: ${dictionary.rules.size} rules, ${dictionary.suffixes.size} suffixes")
}
