package distribution

import java.io.ByteArrayInputStream
import java.nio.file.Files
import java.nio.file.Path
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

internal data class ZipEntrySnapshot(
    val name: String,
    val directory: Boolean,
    val size: Long,
)

private data class ZipEntryContent(
    val name: String,
    val directory: Boolean,
    val bytes: ByteArray,
)

internal object AssetBundleTestSupport {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val distributionsDir: Path = repoRoot.resolve("build/distributions")

    val mainDictionaryEntries = listOf(
        "connectionId.dat.zip",
        "pos_table.dat",
        "id.def",
        "system/tango.dat.zip",
        "system/yomi.dat.zip",
        "system/token.dat.zip",
        "single_kanji/tango_singleKanji.dat",
        "single_kanji/yomi_singleKanji.dat",
        "single_kanji/token_singleKanji.dat",
        "emoji/tango_emoji.dat",
        "emoji/yomi_emoji.dat",
        "emoji/token_emoji.dat",
        "emoticon/tango_emoticon.dat",
        "emoticon/yomi_emoticon.dat",
        "emoticon/token_emoticon.dat",
        "symbol/tango_symbol.dat",
        "symbol/yomi_symbol.dat",
        "symbol/token_symbol.dat",
        "reading_correction/tango_reading_correction.dat",
        "reading_correction/yomi_reading_correction.dat",
        "reading_correction/token_reading_correction.dat",
        "kotowaza/tango_kotowaza.dat",
        "kotowaza/yomi_kotowaza.dat",
        "kotowaza/token_kotowaza.dat",
    )

    val mozcUTDictionaryEntries = listOf(
        "person_name/tango_person_names.dat",
        "person_name/yomi_person_names.dat",
        "person_name/token_person_names.dat",
        "places/tango_places.dat.zip",
        "places/yomi_places.dat.zip",
        "places/token_places.dat.zip",
    )

    val wikiDictionaryEntries = listOf(
        "wiki/tango_wiki.dat.zip",
        "wiki/yomi_wiki.dat.zip",
        "wiki/token_wiki.dat.zip",
    )

    val neologdDictionaryEntries = listOf(
        "neologd/tango_neologd.dat.zip",
        "neologd/yomi_neologd.dat.zip",
        "neologd/token_neologd.dat.zip",
    )

    val webDictionaryEntries = listOf(
        "web/tango_web.dat.zip",
        "web/yomi_web.dat.zip",
        "web/token_web.dat.zip",
    )

    val japaneseKeyboardDictionaryEntries =
        mainDictionaryEntries +
                mozcUTDictionaryEntries +
                wikiDictionaryEntries +
                neologdDictionaryEntries +
                webDictionaryEntries

    val finalArtifactNames = listOf(
        "japanese_keyboard_dictionary_assets.zip",
    )

    private val datZipInnerEntries = mapOf(
        "connectionId.dat.zip" to "connectionId.dat",
        "system/tango.dat.zip" to "tango.dat",
        "system/yomi.dat.zip" to "yomi.dat",
        "system/token.dat.zip" to "token.dat",
        "places/tango_places.dat.zip" to "tango_places.dat",
        "places/yomi_places.dat.zip" to "yomi_places.dat",
        "places/token_places.dat.zip" to "token_places.dat",
        "wiki/tango_wiki.dat.zip" to "tango_wiki.dat",
        "wiki/yomi_wiki.dat.zip" to "yomi_wiki.dat",
        "wiki/token_wiki.dat.zip" to "token_wiki.dat",
        "neologd/tango_neologd.dat.zip" to "tango_neologd.dat",
        "neologd/yomi_neologd.dat.zip" to "yomi_neologd.dat",
        "neologd/token_neologd.dat.zip" to "token_neologd.dat",
        "web/tango_web.dat.zip" to "tango_web.dat",
        "web/yomi_web.dat.zip" to "yomi_web.dat",
        "web/token_web.dat.zip" to "token_web.dat",
    )

    fun bundlePath(zipName: String): Path {
        val path = distributionsDir.resolve(zipName)
        assertTrue(Files.isRegularFile(path), "Missing bundle zip: $path")
        return path
    }

    fun assertExactEntries(zipName: String, expectedEntries: List<String>) {
        val entries = readZipEntries(bundlePath(zipName))
        assertCommonBundleInvariants(zipName, entries)

        val fileNames = entries.filterNot { it.directory }.map { it.name }
        assertEquals(
            expectedEntries.toSet(),
            fileNames.toSet(),
            "$zipName entries must match the JapaneseKeyboard assets layout",
        )
        assertEquals(
            expectedEntries.size,
            fileNames.size,
            "$zipName must not contain duplicate or extra file entries",
        )
    }

    fun assertNoEnglishAssets(zipName: String) {
        val englishEntries = readZipEntries(bundlePath(zipName))
            .filterNot { it.directory }
            .map { it.name }
            .filter { it.startsWith("english/") }
        assertTrue(englishEntries.isEmpty(), "$zipName must not contain english assets: $englishEntries")
    }

    fun assertDatZipEntriesAreReal(zipName: String) {
        val path = bundlePath(zipName)
        val datZipEntries = readZipEntries(path)
            .filter { !it.directory && it.name.endsWith(".dat.zip") }
        ZipFile(path.toFile()).use { outerZip ->
            datZipEntries.forEach { outerEntry ->
                val expectedInner = datZipInnerEntries[outerEntry.name]
                    ?: fail("$zipName contains unexpected .dat.zip entry: ${outerEntry.name}")
                val innerBytes = outerZip.getInputStream(outerZip.getEntry(outerEntry.name)).use { it.readBytes() }
                val innerEntries = readZipEntryContents(innerBytes, "$zipName!/${outerEntry.name}")
                assertTrue(
                    innerEntries.none { it.directory },
                    "$zipName!/${outerEntry.name} must not contain directory entries",
                )
                assertEquals(
                    listOf(expectedInner),
                    innerEntries.map { it.name },
                    "$zipName!/${outerEntry.name} must contain only the raw .dat file",
                )
                assertTrue(
                    innerEntries.single().bytes.isNotEmpty(),
                    "$zipName!/${outerEntry.name}!/$expectedInner must not be empty",
                )
            }
        }
    }

    fun assertNoNativeFiles(zipName: String) {
        val forbiddenExtensions = listOf(".so", ".dylib", ".jnilib", ".dll")
        val violations = mutableListOf<String>()

        fun scanZipStream(prefix: String, zipInput: ZipInputStream) {
            var entry = zipInput.nextEntry
            while (entry != null) {
                val path = "$prefix!/${entry.name}"
                val lower = entry.name.lowercase()
                if (forbiddenExtensions.any { lower.endsWith(it) }) {
                    violations += path
                }
                if (!entry.isDirectory && (lower.endsWith(".zip") || lower.endsWith(".jar"))) {
                    val nestedBytes = zipInput.readBytes()
                    scanZipStream(path, ZipInputStream(ByteArrayInputStream(nestedBytes)))
                }
                zipInput.closeEntry()
                entry = zipInput.nextEntry
            }
        }

        ZipFile(bundlePath(zipName).toFile()).use { zip ->
            zip.entries().asSequence().filterNot { it.isDirectory }.forEach { entry ->
                val lower = entry.name.lowercase()
                if (forbiddenExtensions.any { lower.endsWith(it) }) {
                    violations += entry.name
                }
                if (lower.endsWith(".zip") || lower.endsWith(".jar")) {
                    ZipInputStream(zip.getInputStream(entry)).use { nestedZip ->
                        scanZipStream(entry.name, nestedZip)
                    }
                }
            }
        }
        assertTrue(violations.isEmpty(), "$zipName contains native files: ${violations.joinToString()}")
    }

    private fun assertCommonBundleInvariants(zipName: String, entries: List<ZipEntrySnapshot>) {
        val names = entries.map { it.name }
        val duplicates = names.groupingBy { it }.eachCount().filterValues { it > 1 }.keys
        assertTrue(duplicates.isEmpty(), "$zipName contains duplicate entries: ${duplicates.joinToString()}")

        val emptyFiles = entries.filter { !it.directory && it.size == 0L }.map { it.name }
        assertTrue(emptyFiles.isEmpty(), "$zipName contains empty files: ${emptyFiles.joinToString()}")

        val forbiddenPaths = names.filter { name ->
            name.startsWith("/") ||
                    Regex("^[A-Za-z]:").containsMatchIn(name) ||
                    name.startsWith("../") ||
                    name.contains("/../") ||
                    name.contains('\\') ||
                    name.startsWith("app/src/main/assets/") ||
                    name.startsWith("assets/") ||
                    name.contains("src/main/resources/") ||
                    name.contains("build/")
        }
        assertTrue(forbiddenPaths.isEmpty(), "$zipName contains forbidden paths: ${forbiddenPaths.joinToString()}")
    }

    private fun readZipEntries(path: Path): List<ZipEntrySnapshot> =
        ZipFile(path.toFile()).use { zipFile ->
            zipFile.entries().asSequence().map { entry ->
                ZipEntrySnapshot(
                    name = entry.name,
                    directory = entry.isDirectory,
                    size = entry.size,
                )
            }.toList()
        }.also { entries ->
            assertTrue(entries.isNotEmpty(), "$path must be a non-empty zip archive")
        }

    private fun readZipEntryContents(bytes: ByteArray, label: String): List<ZipEntryContent> {
        val entries = mutableListOf<ZipEntryContent>()
        ZipInputStream(ByteArrayInputStream(bytes)).use { zipInput ->
            var entry = zipInput.nextEntry
            while (entry != null) {
                entries += ZipEntryContent(
                    name = entry.name,
                    directory = entry.isDirectory,
                    bytes = if (entry.isDirectory) ByteArray(0) else zipInput.readBytes(),
                )
                zipInput.closeEntry()
                entry = zipInput.nextEntry
            }
        }
        assertTrue(entries.isNotEmpty(), "$label must be a non-empty zip archive")
        return entries
    }
}
