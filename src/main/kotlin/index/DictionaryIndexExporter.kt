package com.kazumaproject.index

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.hiraToKata
import com.kazumaproject.mozc.MozcIdDefParser
import java.io.*
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.GZIPOutputStream
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

/** Export decoded tokens, rather than unfiltered source dictionary rows. */
object DictionaryIndexExporter {
    const val ASSET_ROOT = "app/src/main/assets/"
    val packs = linkedMapOf(
        "system" to listOf("system/yomi.dat.zip", "system/tango.dat.zip", "system/token.dat.zip"),
        "single_kanji" to listOf("single_kanji/yomi_singleKanji.dat", "single_kanji/tango_singleKanji.dat", "single_kanji/token_singleKanji.dat"),
        "emoji" to listOf("emoji/yomi_emoji.dat", "emoji/tango_emoji.dat", "emoji/token_emoji.dat"),
        "emoticon" to listOf("emoticon/yomi_emoticon.dat", "emoticon/tango_emoticon.dat", "emoticon/token_emoticon.dat"),
        "symbol" to listOf("symbol/yomi_symbol.dat", "symbol/tango_symbol.dat", "symbol/token_symbol.dat"),
        "reading_correction" to listOf("reading_correction/yomi_reading_correction.dat", "reading_correction/tango_reading_correction.dat", "reading_correction/token_reading_correction.dat"),
        "kotowaza" to listOf("kotowaza/yomi_kotowaza.dat", "kotowaza/tango_kotowaza.dat", "kotowaza/token_kotowaza.dat"),
        "person_name" to listOf("person_name/yomi_person_names.dat", "person_name/tango_person_names.dat", "person_name/token_person_names.dat"),
        "places" to listOf("places/yomi_places.dat.zip", "places/tango_places.dat.zip", "places/token_places.dat.zip"),
        "wiki" to listOf("wiki/yomi_wiki.dat.zip", "wiki/tango_wiki.dat.zip", "wiki/token_wiki.dat.zip"),
        "neologd" to listOf("neologd/yomi_neologd.dat.zip", "neologd/tango_neologd.dat.zip", "neologd/token_neologd.dat.zip"),
        "web" to listOf("web/yomi_web.dat.zip", "web/tango_web.dat.zip", "web/token_web.dat.zip"),
        "english_reading" to listOf("english_reading/yomi.dat.zip", "english_reading/tango.dat.zip", "english_reading/token.dat.zip"),
    )

    fun export(assets: File, output: File, release: String, converterCommit: String, mozcCommit: String) {
        require(release.isNotBlank() && converterCommit.isNotBlank() && mozcCommit.isNotBlank()) { "Build provenance is required" }
        output.mkdirs()
        val work = Files.createTempDirectory(output.toPath(), ".dictionary-index-").toFile()
        try {
            val index = File(work, "dictionary-index.tsv.gz")
            val counts = linkedMapOf<String, Long>()
            var idDef = byteArrayOf()
            ZipFile(assets).use { zip ->
                // A new word pack must be added to this contract before publication.
                val packagedYomi = zip.entries().asSequence().map { it.name }.filter {
                    it.startsWith(ASSET_ROOT) && it.substringAfterLast('/').startsWith("yomi") && !it.endsWith('/')
                }.toSet()
                require(packagedYomi == packs.values.map { ASSET_ROOT + it[0] }.toSet()) { "Dictionary pack coverage differs from the export contract" }
                idDef = zip.getInputStream(zip.getEntry(ASSET_ROOT + "id.def") ?: error("Missing id.def")).use { it.readBytes() }
                GZIPOutputStream(index.outputStream().buffered()).bufferedWriter(Charsets.UTF_8).use { writer ->
                    writer.appendLine("dictionary\treading\tword")
                    packs.forEach { (pack, paths) ->
                        val yomi = LOUDSWithTermId().readExternalNotCompress(objectInput(zip, paths[0]))
                        val tango = LOUDS().readExternalNotCompress(objectInput(zip, paths[1]))
                        val tokens = TokenArray().apply { readExternalNotCompress(objectInput(zip, paths[2])) }
                        val tokenCount = tokens.validateForIndex()
                        var decodedTokens = 0
                        var count = 0L
                        val leaves = yomi.isLeaf.stream().iterator()
                        while (leaves.hasNext()) {
                            val node = leaves.nextInt()
                            val term = yomi.getTermId(node)
                            if (term < 0) continue
                            val reading = yomi.getLetter(node)
                            require(reading.isNotBlank()) { "Empty reading in $pack" }
                            val entries = tokens.getListDictionaryByYomiTermId(term)
                            decodedTokens += entries.size
                            require(entries.isNotEmpty()) { "Missing tokens for $pack/$reading" }
                            val words = entries.map { token ->
                                val decoded = when (token.nodeId) {
                                    -2 -> reading
                                    -1 -> reading.hiraToKata()
                                    else -> {
                                        require(token.nodeId >= 0) { "Invalid token sentinel in $pack" }
                                        tango.getLetter(token.nodeId)
                                    }
                                }
                                // The correction pack appends display-only explanatory text.
                                if (pack == "reading_correction") decoded.substringBefore('\t') else decoded
                            }.toSortedSet()
                            words.forEach { word ->
                                require(word.isNotBlank()) { "Empty output in $pack/$reading" }
                                writer.appendLine(listOf(pack, reading, word).joinToString("\t", transform = ::tsv))
                                count++
                            }
                        }
                        require(count > 0 && decodedTokens == tokenCount) { "Incomplete dictionary export: $pack" }
                        counts[pack] = count
                    }
                }
            }
            val ids = MozcIdDefParser.parse(idDef.inputStream().bufferedReader(Charsets.UTF_8), "packaged id.def")
            val manifest = """{
  "schemaVersion": 1,
  "dictionaryRelease": ${json(release)},
  "converterCommit": ${json(converterCommit)},
  "mozcCommit": ${json(mozcCommit)},
  "assets": {"name": "japanese_keyboard_dictionary_assets.zip", "sha256": ${json(sha256(assets))}},
  "index": {"name": "dictionary-index.tsv.gz", "sha256": ${json(sha256(index))}, "rows": ${counts.values.sum()}},
  "packs": {${counts.entries.joinToString(",") { json(it.key) + ":" + it.value }}},
  "idDefSha256": ${json(digest(idDef))},
  "posIds": {${ids.joinToString(",") { json(it.name) + ":" + it.id }}},
  "notices": "dictionary-index-NOTICES.md"
}
"""
            File(work, "dictionary-index-manifest.json").writeText(manifest, Charsets.UTF_8)
            listOf("dictionary-index.tsv.gz", "dictionary-index-manifest.json").forEach { name ->
                Files.move(File(work, name).toPath(), File(output, name).toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING)
            }
            println("Exported ${counts.values.sum()} decoded conversion entries from ${counts.size} packs")
        } finally { work.deleteRecursively() }
    }

    private fun objectInput(zip: ZipFile, path: String): ObjectInputStream {
        val entry = zip.getEntry(ASSET_ROOT + path) ?: error("Missing dictionary asset: $path")
        val input = zip.getInputStream(entry)
        if (!path.endsWith(".zip")) return ObjectInputStream(BufferedInputStream(input))
        val nested = ZipInputStream(BufferedInputStream(input))
        val inner = nested.nextEntry ?: error("Empty nested dictionary asset: $path")
        require(!inner.isDirectory && inner.name == path.substringAfterLast('/').removeSuffix(".zip")) { "Unexpected nested asset: $path" }
        return ObjectInputStream(BufferedInputStream(nested))
    }

    private fun tsv(value: String) = if (value.any { it in "\t\r\n\"" }) "\"" + value.replace("\"", "\"\"") + "\"" else value
    private fun json(value: String) = "\"" + buildString { value.forEach { c -> when (c) {
        '\\' -> append("\\\\")
        '"' -> append("\\\"")
        '\n' -> append("\\n")
        '\r' -> append("\\r")
        '\t' -> append("\\t")
        else -> if (c.code < 32) append("\\u%04x".format(c.code)) else append(c)
    } } } + "\""
    private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input -> val buffer = ByteArray(65536); while (true) {
            val size = input.read(buffer); if (size < 0) break; digest.update(buffer, 0, size)
        } }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    @JvmStatic
    fun main(args: Array<String>) {
        require(args.size == 5) { "Usage: DictionaryIndexExporter ASSETS_ZIP OUTPUT_DIR RELEASE CONVERTER_COMMIT MOZC_COMMIT" }
        export(File(args[0]), File(args[1]), args[2], args[3], args[4])
    }
}
