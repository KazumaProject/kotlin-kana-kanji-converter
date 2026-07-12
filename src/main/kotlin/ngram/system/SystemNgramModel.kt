package com.kazumaproject.ngram.system

import java.io.File
import java.text.Normalizer

const val SYSTEM_NGRAM_MIN_ORDER = 2
const val SYSTEM_NGRAM_MAX_ORDER = 5

enum class SystemNgramPosClass(val binaryId: Int) {
    UNKNOWN(0),
    NOUN(1),
    PROPER_NOUN(2),
    VERB(3),
    ADJECTIVE(4),
    ADVERB(5),
    PARTICLE(6),
    AUXILIARY(7),
    SYMBOL(8),
    OTHER(9),
    ;

    companion object {
        private val byName = entries.associateBy { it.name } + mapOf(
            "未知語" to UNKNOWN,
            "名詞" to NOUN,
            "固有名詞" to PROPER_NOUN,
            "動詞" to VERB,
            "形容詞" to ADJECTIVE,
            "副詞" to ADVERB,
            "助詞" to PARTICLE,
            "助動詞" to AUXILIARY,
            "記号" to SYMBOL,
            "その他" to OTHER,
        )
        private val byId = entries.associateBy { it.binaryId }

        fun parse(value: String): SystemNgramPosClass =
            byName[value.uppercase()]
                ?: throw IllegalArgumentException("Unknown system N-gram POS class: $value")

        fun fromBinaryId(value: Int): SystemNgramPosClass = byId[value] ?: UNKNOWN
    }
}

sealed interface SystemNgramElement {
    data class Word(val surface: String) : SystemNgramElement
    data class Pos(val posClass: SystemNgramPosClass) : SystemNgramElement
    data object Any : SystemNgramElement
}

data class SystemNgramRule(
    val elements: List<SystemNgramElement>,
    val sourceFile: String,
    val sourceLine: Int,
)

data class SystemNgramQueryToken(
    val surface: String,
    val posClass: SystemNgramPosClass = SystemNgramPosClass.UNKNOWN,
)

object SystemNgramRuleParser {
    fun parseDirectory(directory: File): List<SystemNgramRule> {
        require(directory.isDirectory) { "System N-gram source directory does not exist: ${directory.path}" }
        val files = directory.walkTopDown()
            .filter { it.isFile && it.extension == "ngram" }
            .sortedBy { it.relativeTo(directory).invariantSeparatorsPath }
            .toList()
        require(files.isNotEmpty()) { "No .ngram source files found in ${directory.path}" }

        val rules = files.flatMap { parseFile(it, directory) }
        val duplicatePatterns = rules.groupBy { canonicalPattern(it.elements) }
            .filterValues { it.size > 1 }
        require(duplicatePatterns.isEmpty()) {
            "Duplicate system N-gram patterns: " + duplicatePatterns.values.joinToString { group ->
                group.joinToString(prefix = "[", postfix = "]") { "${it.sourceFile}:${it.sourceLine}" }
            }
        }
        require(rules.isNotEmpty()) { "At least one system N-gram pattern is required" }
        return rules
    }

    private fun parseFile(file: File, root: File): List<SystemNgramRule> {
        val result = mutableListOf<SystemNgramRule>()
        file.useLines(Charsets.UTF_8) { lines ->
            lines.forEachIndexed { index, raw ->
                val lineNumber = index + 1
                val trimmed = raw.trim()
                if (trimmed.isEmpty() || trimmed.startsWith("#")) return@forEachIndexed
                val elements = splitPattern(trimmed, file, lineNumber).map { parseElement(it, file, lineNumber) }
                require(elements.size in SYSTEM_NGRAM_MIN_ORDER..SYSTEM_NGRAM_MAX_ORDER) {
                    "System N-gram order must be $SYSTEM_NGRAM_MIN_ORDER..$SYSTEM_NGRAM_MAX_ORDER at ${file.path}:$lineNumber; actual=${elements.size}"
                }
                result += SystemNgramRule(
                    elements = elements,
                    sourceFile = file.relativeTo(root).invariantSeparatorsPath,
                    sourceLine = lineNumber,
                )
            }
        }
        return result
    }

    private fun parseElement(raw: String, file: File, lineNumber: Int): SystemNgramElement {
        return when {
            raw == "*" -> SystemNgramElement.Any
            raw.startsWith("[") && raw.endsWith("]") -> {
                val name = raw.substring(1, raw.lastIndex).trim()
                require(name.isNotEmpty()) { "Empty POS element at ${file.path}:$lineNumber" }
                SystemNgramElement.Pos(SystemNgramPosClass.parse(name))
            }
            else -> {
                val surface = if (raw.startsWith('"')) decodeQuotedWord(raw, file, lineNumber) else raw
                require(!surface.contains('"')) { "Quotes must surround the whole word at ${file.path}:$lineNumber" }
                val normalized = Normalizer.normalize(surface, Normalizer.Form.NFC)
                require(normalized.isNotEmpty()) { "Empty word at ${file.path}:$lineNumber" }
                require(normalized != "BOS" && normalized != "EOS") {
                    "BOS/EOS cannot be used as a word element at ${file.path}:$lineNumber"
                }
                SystemNgramElement.Word(normalized)
            }
        }
    }

    private fun splitPattern(line: String, file: File, lineNumber: Int): List<String> {
        val result = mutableListOf<String>()
        val current = StringBuilder()
        var quoted = false
        var escaped = false
        line.forEach { char ->
            when {
                escaped -> {
                    current.append(char)
                    escaped = false
                }
                quoted && char == '\\' -> {
                    current.append(char)
                    escaped = true
                }
                char == '"' -> {
                    quoted = !quoted
                    current.append(char)
                }
                char == '+' && !quoted -> {
                    result += current.toString().trim()
                    current.clear()
                }
                else -> current.append(char)
            }
        }
        require(!quoted && !escaped) { "Unclosed quoted word at ${file.path}:$lineNumber" }
        result += current.toString().trim()
        require(result.none { it.isEmpty() }) { "Empty pattern element at ${file.path}:$lineNumber" }
        return result
    }

    private fun decodeQuotedWord(raw: String, file: File, lineNumber: Int): String {
        require(raw.length >= 2 && raw.endsWith('"')) { "Unclosed quoted word at ${file.path}:$lineNumber" }
        val inner = raw.substring(1, raw.lastIndex)
        val result = StringBuilder()
        var escaped = false
        inner.forEach { char ->
            if (escaped) {
                result.append(char)
                escaped = false
            } else if (char == '\\') {
                escaped = true
            } else {
                require(char != '"') { "Unescaped quote at ${file.path}:$lineNumber" }
                result.append(char)
            }
        }
        require(!escaped) { "Trailing escape in quoted word at ${file.path}:$lineNumber" }
        return result.toString()
    }

    fun canonicalPattern(elements: List<SystemNgramElement>): String = elements.joinToString("+") {
        when (it) {
            is SystemNgramElement.Word -> "W:${it.surface}"
            is SystemNgramElement.Pos -> "P:${it.posClass.name}"
            SystemNgramElement.Any -> "A:*"
        }
    }
}
