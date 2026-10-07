package com.kazumaproject.index

import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import java.io.File
import java.nio.file.Files
import java.util.zip.GZIPInputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.test.Test
import kotlin.test.assertContains
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

class DictionaryIndexExporterTest {
    private fun fixture(directory: File, omit: String? = null, corrupt: String? = null): File {
        val dictionaries = listOf(
            Dictionary("かんじ", 1, 1, 100, "漢字"),
            Dictionary("かな", 1, 1, 100, "カナ"),
            Dictionary("ひらがな", 1, 1, 100, "ひらがな"),
            Dictionary("せつめい", 1, 1, 100, "説明\t表示用注記"),
        ).groupBy { it.yomi }.toSortedMap(compareBy({ it.length }, { it }))
        val pos = File(directory, "pos-for-build.dat")
        TokenArray().buildPOSTableWithIndex(dictionaries, 1, pos.path)
        val paths = listOf("yomi.dat", "tango.dat", "token.dat").map { File(directory, it) }
        buildAndWriteDictionaryArtifacts(dictionaries, paths[0].path, paths[1].path, paths[2].path, posTableForBuildPath = pos.path)
        val bundle = File(directory, "assets.zip")
        ZipOutputStream(bundle.outputStream()).use { output ->
            output.putNextEntry(ZipEntry(DictionaryIndexExporter.ASSET_ROOT + "id.def"))
            output.write("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n".toByteArray())
            output.closeEntry()
            DictionaryIndexExporter.packs.forEach { (_, names) -> names.forEachIndexed { index, name ->
                if (name != omit) {
                    output.putNextEntry(ZipEntry(DictionaryIndexExporter.ASSET_ROOT + name))
                    val bytes = if (name == corrupt) byteArrayOf(0, 1, 2) else paths[index].readBytes()
                    if (name.endsWith(".zip")) {
                        val buffer = java.io.ByteArrayOutputStream()
                        ZipOutputStream(buffer).use { nested ->
                            nested.putNextEntry(ZipEntry(name.substringAfterLast('/').removeSuffix(".zip")))
                            nested.write(bytes)
                            nested.closeEntry()
                        }
                        output.write(buffer.toByteArray())
                    } else output.write(bytes)
                    output.closeEntry()
                }
            } }
        }
        return bundle
    }

    @Test
    fun exportsAllPacksAndDecodedKanaAndCorrectionOutputs() {
        val directory = Files.createTempDirectory("index-test-").toFile()
        try {
            val output = File(directory, "release")
            DictionaryIndexExporter.export(fixture(directory), output, "v-test", "a".repeat(40), "b".repeat(40))
            val rows = GZIPInputStream(File(output, "dictionary-index.tsv.gz").inputStream()).bufferedReader().use { it.readLines() }
            assertEquals("dictionary\treading\tword", rows.first())
            assertEquals(DictionaryIndexExporter.packs.keys, rows.drop(1).map { it.substringBefore('\t') }.toSet())
            assertContains(rows, "system\tかな\tカナ")
            assertContains(rows, "system\tひらがな\tひらがな")
            assertContains(rows, "reading_correction\tせつめい\t説明")
            assertContains(rows, "wiki\tかんじ\t漢字")
            assertContains(File(output, "dictionary-index-manifest.json").readText(), "\"dictionaryRelease\": \"v-test\"")
        } finally { directory.deleteRecursively() }
    }

    @Test
    fun incompletePackCannotPublishAnIndex() {
        val directory = Files.createTempDirectory("index-missing-").toFile()
        try {
            val output = File(directory, "release")
            assertFailsWith<IllegalArgumentException> {
                DictionaryIndexExporter.export(fixture(directory, omit = "english_reading/yomi.dat.zip"), output, "v-test", "a".repeat(40), "b".repeat(40))
            }
            assertFalse(File(output, "dictionary-index-manifest.json").exists())
        } finally { directory.deleteRecursively() }
    }

    @Test
    fun corruptTokensCannotPublishAnIndex() {
        val directory = Files.createTempDirectory("index-corrupt-").toFile()
        try {
            val output = File(directory, "release")
            assertFailsWith<java.io.IOException> {
                DictionaryIndexExporter.export(fixture(directory, corrupt = "wiki/token_wiki.dat.zip"), output, "v-test", "a".repeat(40), "b".repeat(40))
            }
            assertFalse(File(output, "dictionary-index-manifest.json").exists())
        } finally { directory.deleteRecursively() }
    }
}
