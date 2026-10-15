package com.kazumaproject.feedback

import com.kazumaproject.BaselineDictionaryInputs
import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.specialist.effectiveSurface
import kotlinx.serialization.json.*
import java.io.File
import java.util.zip.GZIPOutputStream

/** Actual selected records, with both literal and binary-reconstructed spellings. */
fun main(args: Array<String>) {
    require(args.size == 2 && args[0] == "--output")
    val inputs = BaselineDictionaryInputs.load().toMutableMap()
    ClassifiedDictionaryData(File("src/main/specialist"), expectedCategoryCount = 2).records.forEach { (id, entries) ->
        inputs["categories/$id"] = entries.toList()
    }
    val output = File(args[1])
    output.parentFile.mkdirs()
    GZIPOutputStream(output.outputStream().buffered()).bufferedWriter(Charsets.UTF_8).use { writer ->
        inputs.filterKeys { it == "system" || it.startsWith("categories/") }.toSortedMap().forEach { (source, entries) ->
            val literalSurfaces = entries.mapTo(HashSet()) { it.tango }
            entries.distinct().sortedWith(compareBy({ it.yomi }, { it.tango }, { it.leftId }, { it.rightId }, { it.cost })).forEach {
                writer.appendLine(buildJsonObject {
                    put("dictionary", source); put("reading", it.yomi); put("rawSurface", it.tango)
                    put("surface", effectiveSurface(it, literalSurfaces))
                    put("leftId", it.leftId.toInt()); put("rightId", it.rightId.toInt()); put("cost", it.cost.toInt())
                }.toString())
            }
        }
    }
}
