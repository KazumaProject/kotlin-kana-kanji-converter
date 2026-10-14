package com.kazumaproject.specialist

import com.kazumaproject.BaselineDictionaryInputs
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.hiraToKata
import com.kazumaproject.isHiraganaOnlyPure
import com.kazumaproject.isKatakanaOnlyPure
import kotlinx.serialization.json.*
import java.io.File
import java.text.Normalizer
import java.util.zip.GZIPOutputStream

/** Surface reconstructed by TokenArray's kana sentinels, rather than its raw input spelling. */
internal fun effectiveSurface(entry: Dictionary, literalSurfaces: Set<String>? = null): String = when {
    entry.yomi == entry.tango || entry.tango.isHiraganaOnlyPure() -> entry.yomi
    entry.tango.isKatakanaOnlyPure() -> entry.yomi.hiraToKata()
    else -> {
        val normalized = Normalizer.normalize(entry.tango, Normalizer.Form.NFC)
        // PrefixTree inserts raw spellings while TokenArray looks up NFC. A missing
        // lookup returns -1, which is the existing katakana sentinel. Preserve that
        // observed baseline behavior in this inventory; do not silently fix assets.
        if (literalSurfaces != null && normalized !in literalSurfaces) entry.yomi.hiraToKata() else normalized
    }
}

internal fun writeInventory(inputs: Map<String, List<Dictionary>>, output: File) {
    output.parentFile.mkdirs()
    GZIPOutputStream(output.outputStream().buffered()).bufferedWriter(Charsets.UTF_8).use { writer ->
        inputs.toSortedMap().forEach { (source, entries) ->
            val literalSurfaces = entries.mapTo(HashSet()) { it.tango }
            entries.asSequence().map { it.yomi to effectiveSurface(it, literalSurfaces) }.distinct()
                .sortedWith(compareBy({ it.first }, { it.second })).forEach { (reading, surface) ->
                    writer.appendLine(buildJsonObject {
                        put("dictionary", source); put("reading", reading); put("surface", surface)
                    }.toString())
                }
        }
    }
}

fun main(args: Array<String>) {
    require(args.size == 2 && args[0] == "--output") { "Usage: --output <existing-pairs.jsonl.gz>" }
    writeInventory(BaselineDictionaryInputs.load(), File(args[1]))
}
