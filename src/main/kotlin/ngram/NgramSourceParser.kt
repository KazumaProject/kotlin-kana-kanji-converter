package com.kazumaproject.ngram

import java.io.File
import java.text.Normalizer

object NgramSourceParser {
    fun parseDirectory(directory: File): List<NgramRule> {
        require(directory.isDirectory) { "Missing n-gram source directory: ${directory.path}" }
        val rules = directory.walkTopDown()
            .filter { it.isFile && it.extension == "ngram" }
            .sortedBy { it.relativeTo(directory).invariantSeparatorsPath }
            .flatMap { parseFile(it).asSequence() }
            .toList()
        require(rules.isNotEmpty()) { "No .ngram rules found in ${directory.path}" }
        val duplicates = rules.groupBy { canonical(it) }.filterValues { it.size > 1 }
        require(duplicates.isEmpty()) {
            duplicates.values.joinToString(prefix = "Duplicate n-gram rules: ") { entries ->
                entries.joinToString { "${it.source}:${it.lineNumber}" }
            }
        }
        return rules
    }

    fun parseFile(file: File): List<NgramRule> = buildList {
        file.readLines(Charsets.UTF_8).forEachIndexed { index, raw ->
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith("#")) return@forEachIndexed
            require(!Regex("(?i)\\b(score|cost|adjustment)\\b").containsMatchIn(line)) {
                "Scores are forbidden in system n-gram sources: ${file.path}:${index + 1}"
            }
            val parts = splitFeatures(line)
            require(parts.size in 2..5) {
                "N-gram order must be 2..5 at ${file.path}:${index + 1}: $line"
            }
            add(
                NgramRule(
                    features = parts.map { parseFeature(it, file, index + 1) },
                    source = file.path,
                    lineNumber = index + 1,
                ),
            )
        }
    }

    private fun splitFeatures(line: String): List<String> {
        val result = mutableListOf<String>()
        var quoted = false
        var escaped = false
        var depth = 0
        var start = 0
        line.forEachIndexed { index, char ->
            when {
                escaped -> escaped = false
                char == '\\' && quoted -> escaped = true
                char == '"' -> quoted = !quoted
                !quoted && char == '(' -> depth++
                !quoted && char == ')' -> depth--
                !quoted && depth == 0 && char == '+' -> {
                    result += line.substring(start, index).trim()
                    start = index + 1
                }
            }
        }
        require(!quoted && depth == 0) { "Unclosed quote or parenthesis: $line" }
        result += line.substring(start).trim()
        require(result.none { it.isEmpty() }) { "Empty feature in: $line" }
        return result
    }

    private fun parseFeature(text: String, file: File, lineNumber: Int): NgramFeature {
        if (text == "*") return NgramFeature.Any
        val word = parseQuoted(text)
        if (word != null) {
            val normalized = Normalizer.normalize(word, Normalizer.Form.NFC)
            require(normalized.isNotEmpty()) { "Empty word at ${file.path}:$lineNumber" }
            return NgramFeature.Word(normalized)
        }
        val posMatch = Regex("pos\\(\\s*(\"(?:\\\\.|[^\"])*\")\\s*\\)").matchEntire(text)
        if (posMatch != null) {
            val value = requireNotNull(parseQuoted(posMatch.groupValues[1]))
            require(value.isNotEmpty()) { "Empty POS at ${file.path}:$lineNumber" }
            return NgramFeature.Pos(value)
        }
        error("Invalid n-gram feature at ${file.path}:$lineNumber: $text")
    }

    private fun parseQuoted(text: String): String? {
        if (text.length < 2 || text.first() != '"' || text.last() != '"') return null
        val result = StringBuilder(text.length - 2)
        var index = 1
        while (index < text.lastIndex) {
            val char = text[index++]
            if (char != '\\') {
                result.append(char)
                continue
            }
            require(index < text.lastIndex) { "Invalid escape in $text" }
            result.append(
                when (val escaped = text[index++]) {
                    '\\', '"' -> escaped
                    'n' -> '\n'
                    't' -> '\t'
                    else -> error("Unsupported escape \\$escaped in $text")
                },
            )
        }
        return result.toString()
    }

    private fun canonical(rule: NgramRule): String = rule.features.joinToString("|") {
        when (it) {
            is NgramFeature.Word -> "W:${it.value}"
            is NgramFeature.Pos -> "P:${it.value}"
            NgramFeature.Any -> "*"
        }
    }
}
