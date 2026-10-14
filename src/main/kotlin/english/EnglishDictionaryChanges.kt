package com.kazumaproject.english

import com.kazumaproject.dictionary.models.Dictionary
import java.nio.file.Files
import java.nio.file.Path
import java.util.Locale

data class EnglishDictionaryChange(val kind: String, val before: Dictionary?, val after: Dictionary?)

/** Compare adopted rows, keeping case-only changes separate from additions and removals. */
object EnglishDictionaryChanges {
    fun compare(before: List<Dictionary>, after: List<Dictionary>): List<EnglishDictionaryChange> {
        fun key(row: Dictionary) = row.yomi to row.tango
        fun foldedKey(row: Dictionary) = row.yomi to row.tango.lowercase(Locale.ROOT)
        val old = before.associateBy(::key).toMutableMap()
        val current = after.associateBy(::key).toMutableMap()
        require(old.size == before.size && current.size == after.size) { "Duplicate adopted reading/surface pair" }
        val changes = mutableListOf<EnglishDictionaryChange>()
        (old.keys intersect current.keys).forEach { pair ->
            val original = old.remove(pair)!!
            val updated = current.remove(pair)!!
            if (original != updated) changes += EnglishDictionaryChange("cost-or-pos-changed", original, updated)
        }
        val oldGroups = old.values.groupBy(::foldedKey)
        val newGroups = current.values.groupBy(::foldedKey)
        (oldGroups.keys intersect newGroups.keys).forEach { pair ->
            val original = oldGroups.getValue(pair).singleOrNull()
            val updated = newGroups.getValue(pair).singleOrNull()
            if (original != null && updated != null) {
                changes += EnglishDictionaryChange("surface-changed", original, updated)
                old.remove(key(original))
                current.remove(key(updated))
            }
        }
        changes += old.values.map { EnglishDictionaryChange("removed", it, null) }
        changes += current.values.map { EnglishDictionaryChange("added", null, it) }
        return changes.sortedWith(compareBy({ (it.after ?: it.before!!).yomi }, { it.kind }, { (it.after ?: it.before!!).tango }))
    }

    fun write(changes: List<EnglishDictionaryChange>, output: Path) {
        output.parent?.let(Files::createDirectories)
        Files.newBufferedWriter(output).use { writer ->
            writer.appendLine("kind\treading\tbefore_surface\tafter_surface\tbefore_cost\tafter_cost\tbefore_left_id\tafter_left_id\tbefore_right_id\tafter_right_id")
            changes.forEach { change ->
                val old = change.before
                val current = change.after
                writer.appendLine(listOf(change.kind, (current ?: old!!).yomi, old?.tango.orEmpty(), current?.tango.orEmpty(),
                    old?.cost?.toString().orEmpty(), current?.cost?.toString().orEmpty(), old?.leftId?.toString().orEmpty(),
                    current?.leftId?.toString().orEmpty(), old?.rightId?.toString().orEmpty(), current?.rightId?.toString().orEmpty()).joinToString("\t"))
            }
        }
    }
}
