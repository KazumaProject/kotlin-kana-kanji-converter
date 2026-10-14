package com.kazumaproject.specialist

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.classification.ClassifiedDictionaryData
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.hiraToKata
import kotlinx.serialization.json.*
import java.io.*
import java.nio.file.Files
import java.text.Normalizer
import java.util.zip.*

internal fun pairKey(reading: String, surface: String): Pair<String, String> {
    val normalized = Normalizer.normalize(reading.trim(), Normalizer.Form.NFKC)
        .map { if (it in '\u30a1'..'\u30f6') it - 0x60 else it }.joinToString("")
    return Normalizer.normalize(normalized, Normalizer.Form.NFC) to Normalizer.normalize(surface.trim(), Normalizer.Form.NFC)
}

internal fun restoredSurface(reading: String, nodeId: Int, tango: LOUDS): String = when (nodeId) {
    -2 -> reading
    -1 -> reading.hiraToKata()
    else -> { require(nodeId >= 0); tango.getLetter(nodeId) }
}

private fun readAsset(zip: ZipFile, path: String): ObjectInputStream {
    val stream = zip.getInputStream(zip.getEntry("app/src/main/assets/$path") ?: error("Missing $path"))
    if (!path.endsWith(".zip")) return ObjectInputStream(stream.buffered())
    val nested = ZipInputStream(stream)
    require(nested.nextEntry?.name == File(path.removeSuffix(".zip")).name) { "Wrong nested asset $path" }
    return ObjectInputStream(nested.buffered())
}

private fun assetPaths(source: String): List<String> = when {
    source.startsWith("categories/") -> listOf("yomi", "tango", "token").map { "$source/$it.dat.zip" }
    source == "system" -> listOf("yomi", "tango", "token").map { "system/$it.dat.zip" }
    source == "english_reading" -> listOf("yomi", "tango", "token").map { "english_reading/$it.dat.zip" }
    source in setOf("single_kanji", "emoji", "emoticon", "symbol", "reading_correction", "kotowaza") -> {
        val suffix = if (source == "single_kanji") "singleKanji" else source
        listOf("yomi", "tango", "token").map { "$source/${it}_$suffix.dat" }
    }
    else -> error("Unknown baseline dictionary $source")
}

private fun readDictionary(zip: ZipFile, source: String): List<Dictionary> {
    val (yp, tp, tokensPath) = assetPaths(source)
    val yomi = readAsset(zip, yp).use { LOUDSWithTermId().readExternalNotCompress(it) }
    val tango = readAsset(zip, tp).use { LOUDS().readExternalNotCompress(it) }
    val tokens = readAsset(zip, tokensPath).use { TokenArray().also { a -> a.readExternalNotCompressStrict(it) } }
    val result = ArrayList<Dictionary>()
    var node = yomi.isLeaf.nextSetBit(0)
    var readings = 0
    while (node >= 0) {
        val reading = yomi.getLetter(node)
        val term = yomi.getTermId(node)
        require(term > 0) { "$source: invalid terminal $node" }
        readings++
        tokens.getListDictionaryByYomiTermId(term).forEach {
            result.add(Dictionary(reading, 0, 0, it.wordCost, restoredSurface(reading, it.nodeId, tango)))
        }
        node = yomi.isLeaf.nextSetBit(node + 1)
    }
    check(readings == yomi.termIdsSave.size && result.size == tokens.entryCount) { "$source: incomplete archive traversal" }
    return result
}

fun main(args: Array<String>) {
    require(args.size == 4 && args[0] == "--archive" && args[2] == "--existing-index")
    val expectedInventory = File(args[3])
    val sources = GZIPInputStream(expectedInventory.inputStream()).bufferedReader().useLines { lines ->
        lines.map { Json.parseToJsonElement(it).jsonObject.getValue("dictionary").jsonPrimitive.content }.toSet()
    }
    val specialists = ClassifiedDictionaryData(File("src/main/specialist"), expectedCategoryCount = 2)
    specialists.verifyArchive(File(args[1]))
    val temporary = Files.createTempDirectory("packaged-specialist-inventory").toFile()
    try {
        ZipFile(File(args[1])).use { zip ->
            val baseline = sources.sorted().associateWith { readDictionary(zip, it) }
            val inventory = File(temporary, "existing-pairs.jsonl.gz")
            writeInventory(baseline, inventory)
            if (!expectedInventory.readBytes().contentEquals(inventory.readBytes())) {
                val diagnostic = File("build/reports/specialist/packaged-existing-pairs.jsonl.gz")
                diagnostic.parentFile.mkdirs()
                inventory.copyTo(diagnostic, overwrite = true)
                println("Inventory mismatch; packaged inventory saved at ${diagnostic.path}")
            }
            // Recompute selection against the actual packaged dictionaries, not only their input text.
            val process = ProcessBuilder("python3", "scripts/specialist_distribution.py", "verify",
                "--existing-index", inventory.path).inheritIO().start()
            check(process.waitFor() == 0) { "Specialist selection verification failed against packaged inventory; see Python diagnostic" }
            val occupied = baseline.values.asSequence().flatten().map { pairKey(it.yomi, it.tango) }.toMutableSet()
            for (category in specialists.categoryIds) {
                val entries = readDictionary(zip, "categories/$category")
                val wanted = specialists.records.getValue(category).map { it.yomi to it.tango }.toSet()
                check(entries.map { it.yomi to it.tango }.toSet() == wanted && entries.size == wanted.size) {
                    "$category: reconstructed surface mismatch or duplicate token"
                }
                entries.forEach { check(occupied.add(pairKey(it.yomi, it.tango))) { "$category: duplicate packaged candidate $it" } }
                println("Verified packaged specialist=$category rows=${entries.size}; duplicate pairs=0")
            }
        }
    } finally { temporary.deleteRecursively() }
}
