package com.kazumaproject.ngram

import com.kazumaproject.Constants
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.models.Dictionary
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.createDirectories

data class StableTermIdMap(
    val terms: List<NgramTerm>,
) {
    fun writeTo(outputPath: Path) {
        outputPath.parent?.createDirectories()
        Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8).use { writer ->
            writer.appendLine("termId\treading\tsurface\tleftId\trightId\tcost")
            terms.sortedWith(termOutputComparator).forEach { term ->
                writer.appendLine(
                    listOf(
                        term.termId.toString(),
                        encodeTermMapText(term.reading),
                        encodeTermMapText(term.surface),
                        term.leftId.toInt().toString(),
                        term.rightId.toInt().toString(),
                        term.cost.toInt().toString(),
                    ).joinToString("\t")
                )
            }
        }
    }

    companion object {
        fun build(dictionaries: Iterable<Dictionary>): StableTermIdMap {
            val dictionaryList = dictionaries.toList()
            val termIds = NgramTokenTermIdBuilder.stableTermIds(dictionaryList)

            val terms = dictionaryList
                .map { dictionary ->
                    val termId = termIds.getValue(TermIdentity(dictionary.yomi, dictionary.tango))
                    NgramTerm(
                        termId = termId,
                        reading = dictionary.yomi,
                        surface = dictionary.tango,
                        leftId = dictionary.leftId,
                        rightId = dictionary.rightId,
                        cost = dictionary.cost,
                    )
                }
                .sortedWith(termOutputComparator)
                .fold(mutableListOf<NgramTerm>()) { acc, term ->
                    if (acc.lastOrNull() != term) {
                        acc += term
                    }
                    acc
                }

            return StableTermIdMap(terms)
        }

        fun readFrom(inputPath: Path): StableTermIdMap {
            require(Files.isRegularFile(inputPath)) { "Stable termId map does not exist: $inputPath" }
            val rows = Files.readAllLines(inputPath, StandardCharsets.UTF_8)
            require(rows.isNotEmpty()) { "Stable termId map is empty: $inputPath" }
            val header = splitPreservingEmpty(rows.first(), '\t')
                .map { it.trim() }
                .withIndex()
                .associate { it.value to it.index }
            listOf("termId", "reading", "surface", "leftId", "rightId", "cost").forEach { column ->
                require(column in header) { "Stable termId map is missing column '$column': $inputPath" }
            }
            val terms = rows.drop(1)
                .filter { it.isNotBlank() }
                .mapIndexed { index, row ->
                    val lineNumber = index + 2
                    val columns = splitPreservingEmpty(row, '\t')
                    fun value(name: String): String = columns.getOrElse(header.getValue(name)) { "" }
                    NgramTerm(
                        termId = value("termId").toIntOrNull()
                            ?: error("Invalid termId at $inputPath:$lineNumber"),
                        reading = decodeTermMapText(value("reading")),
                        surface = decodeTermMapText(value("surface")),
                        leftId = value("leftId").toShortOrNull()
                            ?: error("Invalid leftId at $inputPath:$lineNumber"),
                        rightId = value("rightId").toShortOrNull()
                            ?: error("Invalid rightId at $inputPath:$lineNumber"),
                        cost = value("cost").toShortOrNull()
                            ?: error("Invalid cost at $inputPath:$lineNumber"),
                    )
                }
                .sortedWith(termOutputComparator)
            return StableTermIdMap(terms)
        }

        private val termOutputComparator = compareBy<NgramTerm> { it.termId }
            .thenBy { it.reading.length }
            .thenBy { it.reading }
            .thenBy { it.surface.length }
            .thenBy { it.surface }
            .thenBy { it.leftId.toInt() }
            .thenBy { it.rightId.toInt() }
            .thenBy { it.cost.toInt() }
    }
}

private fun encodeTermMapText(value: String): String = buildString {
    value.forEach { ch ->
        when (ch) {
            '\\' -> append("\\\\")
            '\t' -> append("\\t")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            else -> append(ch)
        }
    }
}

private fun decodeTermMapText(value: String): String = buildString {
    var index = 0
    while (index < value.length) {
        val ch = value[index]
        if (ch != '\\' || index == value.lastIndex) {
            append(ch)
            index += 1
            continue
        }
        when (val escaped = value[index + 1]) {
            '\\' -> append('\\')
            't' -> append('\t')
            'n' -> append('\n')
            'r' -> append('\r')
            else -> {
                append('\\')
                append(escaped)
            }
        }
        index += 2
    }
}

object NgramDictionarySource {
    private val systemDictionaryFiles = listOf(
        "/dictionary00.txt",
        "/dictionary01.txt",
        "/dictionary02.txt",
        "/dictionary03.txt",
        "/dictionary04.txt",
        "/dictionary05.txt",
        "/dictionary06.txt",
        "/dictionary07.txt",
        "/dictionary08.txt",
        "/dictionary09.txt",
        "/suffix.txt",
    )

    fun buildMainDictionaryList(): List<Dictionary> {
        return DicUtils().getListDictionary(systemDictionaryFiles) +
                Constants.DIC_LIST +
                Constants.CUSTOM_LIST +
                Constants.NAME_LIST +
                Constants.FIXED_LIST +
                Constants.DIFFICULT_LIST +
                Constants.SYMBOL_LIST +
                Constants.NAME_MUSIC_LIST +
                Constants.NAME_IT_LIST +
                Constants.VERB_LIST +
                Constants.DOMAIN +
                Constants.ERA +
                Constants.PLACE +
                Constants.WORDS +
                Constants.ZENKANKU_LIST +
                Constants.ADDS_NEW_WORDS +
                Constants.PHISIC_NOUN_LIST +
                Constants.FIGHT_NAME +
                Constants.FOOD_NAME +
                Constants.ENTERTAIMENT_NAME +
                Constants.RESCORE_WORDS
    }
}

class NgramTermResolver(
    terms: List<NgramTerm>,
) {
    private val termsBySurface: Map<String, List<NgramTerm>> = terms
        .groupBy { it.surface }
        .mapValues { (_, value) ->
            value.sortedWith(compareBy<NgramTerm> { it.reading.length }
                .thenBy { it.reading }
                .thenBy { it.cost.toInt() }
                .thenBy { it.leftId.toInt() }
                .thenBy { it.rightId.toInt() }
                .thenBy { it.termId })
        }

    fun candidates(surface: String): List<NgramTerm> = termsBySurface[surface].orEmpty()
}

data class ResolvedNgramRule(
    val rule: NgramRule,
    val terms: List<NgramTerm>,
) {
    val keySequence: NgramKeySequence
        get() = NgramKeySequence(rule.order, terms.map { it.nodeKey }.toLongArray())
}

class FullReadingSegmentResolver(
    private val termResolver: NgramTermResolver,
) {
    fun resolve(rule: NgramRule): ResolvedNgramRule? {
        val selected = arrayOfNulls<NgramTerm>(rule.order)
        val surfaces = rule.surfaces.take(rule.order)

        fun search(surfaceIndex: Int, readingOffset: Int): Boolean {
            if (surfaceIndex == rule.order) {
                return readingOffset == rule.reading.length
            }
            val surface = surfaces[surfaceIndex]
            val candidates = termResolver.candidates(surface)
            candidates.forEach { candidate ->
                if (rule.reading.startsWith(candidate.reading, readingOffset)) {
                    selected[surfaceIndex] = candidate
                    if (search(surfaceIndex + 1, readingOffset + candidate.reading.length)) {
                        return true
                    }
                    selected[surfaceIndex] = null
                }
            }
            return false
        }

        if (!search(0, 0)) {
            return null
        }
        return ResolvedNgramRule(
            rule = rule,
            terms = selected.map { it ?: error("unreachable: selected term was null") },
        )
    }
}
