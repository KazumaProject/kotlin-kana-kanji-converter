package com.kazumaproject.quality

import com.kazumaproject.dictionary.models.Dictionary
import java.io.File
import java.io.InputStream
import java.util.zip.ZipFile

object SupplementalSources {
    val files = linkedMapOf("person" to "names.txt", "place" to "place.txt.zip", "wiki" to "only_wiki.txt.zip", "neologd" to "only_neologd.txt.zip", "common" to "wiki_neologd_common.txt.zip")

    fun read(source: String, directory: File, visit: (SourceRow) -> Unit) {
        val name = files.getValue(source)
        val file = File(directory, name)
        if (name.endsWith(".zip")) ZipFile(file).use { zip ->
            val inner = name.removeSuffix(".zip")
            val entry = zip.getEntry(inner) ?: error("Missing $inner in $file")
            zip.getInputStream(entry).use { parse(it, source, file.path, visit) }
        } else file.inputStream().use { parse(it, source, file.path, visit) }
    }

    fun parse(input: InputStream, source: String, path: String, visit: (SourceRow) -> Unit) {
        input.bufferedReader(Charsets.UTF_8).use { reader ->
            reader.lineSequence().forEachIndexed { index, line ->
                val parts = line.split('\t')
                require(parts.size == 5) { "$path:${index + 1}: expected 5 TSV fields" }
                try {
                    val word = Dictionary(parts[0], parts[1].toShort(), parts[2].toShort(), parts[3].toShort(), parts[4])
                    visit(SourceRow(source, index + 1, word))
                } catch (e: NumberFormatException) {
                    throw IllegalArgumentException("$path:${index + 1}: invalid ID or cost", e)
                }
            }
        }
    }

    fun normalized(source: String, directory: File = File("src/main/bin"), base: File = File("src/main/resources")): List<Dictionary> {
        val lexical = if (source == "place") LexicalEvidence.load(File("build/dictionary-metadata/snapshot.sqlite").takeIf { it.isFile }) else LexicalEvidence()
        val evidence = if (source == "place") ReadingEvidence.load(base).toMutableMap().apply { lexical.readings.forEach { (surface, readings) -> put(surface, get(surface).orEmpty() + readings) } } else emptyMap()
        val normalizer = CandidateNormalizer(evidence, ManualOverrides(File("src/main/dictionary-quality/overrides.tsv").takeIf { it.isFile }), lexical)
        val result = linkedMapOf<WordKey, Dictionary>()
        var held = 0
        var changed = 0
        read(source, directory) { row ->
            val normalized = normalizer.normalize(row)
            if (normalized.entries.isEmpty()) held++
            if (normalized.reason != "unchanged") changed++
            normalized.entries.forEach { word ->
                val key = word.key()
                if (word.cost < (result[key]?.cost ?: Short.MAX_VALUE)) result[key] = word
                else result.putIfAbsent(key, word)
            }
        }
        println("Normalized $source: accepted=${result.size}, changed=$changed, held=$held")
        return result.values.toList()
    }
}

data class SourceRow(val source: String, val line: Int, val word: Dictionary)
data class WordKey(val reading: String, val surface: String, val leftId: Short, val rightId: Short)
fun Dictionary.key() = WordKey(yomi, tango, leftId, rightId)

object ReadingEvidence {
    fun load(directory: File, supplemental: File? = null): Map<String, Set<String>> {
        val result = hashMapOf<String, MutableSet<String>>()
        val files = (0..9).map { File(directory, "dictionary%02d.txt".format(it)) } + File(directory, "suffix.txt")
        files.forEach { file ->
            require(file.isFile) { "Missing reading evidence: $file" }
            file.forEachLine { line ->
                val parts = line.split('\t', limit = 5)
                require(parts.size == 5) { "Invalid Mozc row in $file" }
                result.getOrPut(parts[4]) { hashSetOf() }.add(parts[0])
            }
        }
        if (supplemental != null) SupplementalSources.files.keys.forEach { source ->
            SupplementalSources.read(source, supplemental) { row ->
                val word = row.word
                if (word.tango.none { it in "()（）" } && word.yomi.isNotBlank() && word.yomi.none { it.isWhitespace() || it.isISOControl() })
                    result.getOrPut(word.tango) { hashSetOf() }.add(word.yomi)
            }
        }
        return result
    }
}
