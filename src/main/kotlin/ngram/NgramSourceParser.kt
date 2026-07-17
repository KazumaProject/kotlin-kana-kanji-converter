package com.kazumaproject.ngram

import java.io.File
import java.text.Normalizer

object NgramSourceParser {
    fun parseDirectory(directory: File): List<NgramRule> {
        require(directory.isDirectory) { "Missing n-gram source directory: ${directory.path}" }
        val sourceRoot = directory.canonicalFile
        val wordListLoader = WordListLoader(sourceRoot)
        val rules = directory.walkTopDown()
            .filter { it.isFile && it.extension == "ngram" }
            .sortedBy { it.relativeTo(directory).invariantSeparatorsPath }
            .flatMap { parseFile(it, wordListLoader).asSequence() }
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

    fun parseFile(file: File): List<NgramRule> =
        parseFile(file, WordListLoader(requireNotNull(file.parentFile).canonicalFile))

    private fun parseFile(file: File, wordListLoader: WordListLoader): List<NgramRule> = buildList {
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
            val alternatives = parts.map {
                parseFeatureAlternatives(it, file, index + 1, wordListLoader)
            }
            var expandedFeatures = listOf(emptyList<NgramFeature>())
            alternatives.forEach { choices ->
                require(expandedFeatures.size.toLong() * choices.size <= MAX_EXPANDED_RULES_PER_LINE) {
                    "N-gram word-set expansion exceeds $MAX_EXPANDED_RULES_PER_LINE rules " +
                        "at ${file.path}:${index + 1}: $line"
                }
                expandedFeatures = expandedFeatures.flatMap { existing ->
                    choices.map { choice -> existing + choice }
                }
            }
            expandedFeatures.forEach { features ->
                add(
                    NgramRule(
                        features = features,
                        source = file.path,
                        lineNumber = index + 1,
                    ),
                )
            }
        }
    }

    private fun parseFeatureAlternatives(
        text: String,
        file: File,
        lineNumber: Int,
        wordListLoader: WordListLoader,
    ): List<NgramFeature> {
        val wordsMatch = WORDS_PATTERN.matchEntire(text)
        if (wordsMatch != null) {
            val reference = requireNotNull(parseQuoted(wordsMatch.groupValues[1]))
            return wordListLoader.load(reference, file, lineNumber).map(NgramFeature::Word)
        }
        return listOf(parseFeature(text, file, lineNumber))
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

    private class WordListLoader(sourceRoot: File) {
        private val sourceRoot = sourceRoot.canonicalFile
        private val sourceRootPath = this.sourceRoot.toPath()
        private val cache = mutableMapOf<File, List<String>>()

        fun load(reference: String, owner: File, lineNumber: Int): List<String> =
            load(resolve(reference, owner, lineNumber), mutableListOf())

        private fun load(file: File, stack: MutableList<File>): List<String> {
            cache[file]?.let { return it }
            val cycleStart = stack.indexOf(file)
            require(cycleStart < 0) {
                val cycle = (stack.drop(cycleStart) + file).joinToString(" -> ") {
                    it.relativeTo(sourceRoot).invariantSeparatorsPath
                }
                "Cyclic .words include: $cycle"
            }

            stack += file
            val words = linkedSetOf<String>()
            try {
                file.readLines(Charsets.UTF_8).forEachIndexed { index, raw ->
                    val line = raw.trim()
                    if (line.isEmpty() || line.startsWith("#")) return@forEachIndexed
                    val includeMatch = INCLUDE_PATTERN.matchEntire(line)
                    if (includeMatch != null) {
                        val reference = requireNotNull(parseQuoted(includeMatch.groupValues[1]))
                        words += load(resolve(reference, file, index + 1), stack)
                    } else {
                        require(!line.startsWith("@include")) {
                            "Invalid .words include at ${file.path}:${index + 1}: $line"
                        }
                        val normalized = Normalizer.normalize(line, Normalizer.Form.NFC)
                        require(normalized.isNotEmpty() && '\u0000' !in normalized) {
                            "Invalid word at ${file.path}:${index + 1}"
                        }
                        words += normalized
                    }
                }
            } finally {
                stack.removeAt(stack.lastIndex)
            }
            require(words.isNotEmpty()) { "No words found in ${file.path}" }
            return words.toList().also { cache[file] = it }
        }

        private fun resolve(reference: String, owner: File, lineNumber: Int): File {
            require(reference.isNotEmpty() && !File(reference).isAbsolute) {
                ".words reference must be a non-empty relative path at ${owner.path}:$lineNumber: $reference"
            }
            require(File(reference).extension == "words") {
                ".words reference must end in .words at ${owner.path}:$lineNumber: $reference"
            }
            val resolved = requireNotNull(owner.parentFile).resolve(reference).canonicalFile
            require(resolved.toPath().startsWith(sourceRootPath)) {
                ".words reference escapes ${sourceRoot.path} at ${owner.path}:$lineNumber: $reference"
            }
            require(resolved.isFile) {
                "Missing .words file referenced at ${owner.path}:$lineNumber: ${resolved.path}"
            }
            return resolved
        }
    }

    private fun canonical(rule: NgramRule): String = rule.features.joinToString("|") {
        when (it) {
            is NgramFeature.Word -> "W:${it.value}"
            is NgramFeature.Pos -> "P:${it.value}"
            NgramFeature.Any -> "*"
        }
    }

    private val WORDS_PATTERN = Regex("words\\(\\s*(\"(?:\\\\.|[^\"])*\")\\s*\\)")
    private val INCLUDE_PATTERN = Regex("@include\\s+(\"(?:\\\\.|[^\"])*\")")
    private const val MAX_EXPANDED_RULES_PER_LINE = 100_000
}
