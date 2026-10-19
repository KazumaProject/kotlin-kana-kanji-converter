package com.kazumaproject.classification

import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.mozc.buildConnectionIdsFromResource
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import java.io.File

/** Active distribution after independent person review and cross-category filtering.
 *
 * The default ClassifiedDictionaryData and BaselineDictionaryInputs remain the
 * frozen source inventory used by specialist duplicate exclusions. That original
 * inventory conservatively contains this distribution; it is not the active list.
 */
fun personDistributionData(
    directory: File = File("src/main/classification/person-subclassification/distribution"),
    idDef: File = File("src/main/resources/id.def"),
): ClassifiedDictionaryData = ClassifiedDictionaryData(directory, idDef, expectedCategoryCount = 51)

/** Build curated category binaries with their own POS table for isolated checks.
 * The full application build uses Main's shared POS table instead.
 */
fun main(args: Array<String>) {
    require(args.size % 2 == 0) { "Usage: --output <directory> [--id-def <file>] [--directory <source>] [--archive <zip>]" }
    val options = args.toList().chunked(2)
    require(options.map { it[0] }.distinct().size == options.size &&
        options.all { it[0] in setOf("--output", "--id-def", "--directory", "--archive") }) { "Invalid or repeated option" }
    val values = options.associate { it[0] to it[1] }
    val output = File(requireNotNull(values["--output"]) { "--output is required" })
    val directory = values["--directory"]?.let(::File)
        ?: File("src/main/classification/person-subclassification/distribution")
    val idDef = values["--id-def"]?.let(::File) ?: File("src/main/resources/id.def")
    val data = personDistributionData(directory, idDef)
    check(output.mkdirs() || output.isDirectory) { "Cannot create output: $output" }
    val entries = data.records.values.flatten().groupBy { it.yomi }
        .toSortedMap(compareBy({ it.length }, { it }))
    val pos = File(output, "pos_table.dat")
    val buildPos = File(output, "pos_table_for_build.dat")
    TokenArray().buildPOSTable(entries, 1, pos.path)
    TokenArray().buildPOSTableWithIndex(entries, 1, buildPos.path)
    check(pos.isFile && pos.length() > 0 && buildPos.isFile && buildPos.length() > 0) { "Missing POS output" }
    data.build(File(output, "categories"), buildPos.path)
    val connection = File(output, "connectionId.dat")
    buildConnectionIdsFromResource(outputPath = connection.path)
    val archive = values["--archive"]?.let(::File)
        ?: File(output, "person_subclassified_dictionary_assets.zip")
    archive.parentFile?.mkdirs()
    val assets = "app/src/main/assets"
    ZipOutputStream(archive.outputStream().buffered()).use { zip ->
        fun bytes(name: String, contents: ByteArray) {
            zip.putNextEntry(ZipEntry(name).apply { time = 0L })
            zip.write(contents)
            zip.closeEntry()
        }
        fun raw(name: String, file: File) {
            zip.putNextEntry(ZipEntry(name).apply { time = 0L })
            file.inputStream().use { it.copyTo(zip) }
            zip.closeEntry()
        }
        fun nested(name: String, file: File) {
            val compressed = ByteArrayOutputStream()
            ZipOutputStream(compressed).use { inner ->
                inner.putNextEntry(ZipEntry(file.name).apply { time = 0L })
                file.inputStream().use { it.copyTo(inner) }
                inner.closeEntry()
            }
            bytes(name, compressed.toByteArray())
        }
        raw("$assets/pos_table.dat", pos)
        nested("$assets/connectionId.dat.zip", connection)
        data.categoryIds.forEach { category ->
            listOf("yomi.dat", "tango.dat", "token.dat").forEach { name ->
                nested("$assets/categories/$category/$name.zip", File(output, "categories/$category/$name"))
            }
        }
        listOf("LICENSE", "LICENSE-DATA.md", "src/main/resources/THIRD-PARTY-NOTICES.md").forEach {
            raw("notices/project/${File(it).name}", File(it))
        }
        val thirdParty = File("src/main/resources/third-party")
        check(thirdParty.isDirectory) { "Missing original dictionary license notices" }
        thirdParty.walkTopDown().filter { it.isFile }.sortedBy { it.relativeTo(thirdParty).invariantSeparatorsPath }.forEach {
            raw("notices/third-party/${it.relativeTo(thirdParty).invariantSeparatorsPath}", it)
        }
        raw("id.def", idDef)
        raw("classification-categories.json", File(directory, "categories.json"))
        raw("classification-manifest.json", File(directory, "distribution-manifest.json"))
        val notices = File(directory, "notices")
        check(notices.isDirectory && notices.walkTopDown().any { it.isFile }) { "Missing distribution license notices" }
        notices.walkTopDown().filter { it.isFile }.sortedBy { it.relativeTo(notices).invariantSeparatorsPath }.forEach {
            raw("notices/${it.relativeTo(notices).invariantSeparatorsPath}", it)
        }
        bytes("README.txt", ("Curated category dictionaries with an isolated POS table and connection matrix.\n" +
            "Load the included pos_table.dat with all categories from this archive.\n" +
            "System, English and specialist assets must be rebuilt with that same POS table before mixing them.\n" +
            "Source categories and provenance: classification-categories.json and classification-manifest.json.\n" +
            "License and attribution: notices/project/LICENSE-DATA.md, notices/project/THIRD-PARTY-NOTICES.md and notices/third-party/.\n" +
            "This archive does not establish compatibility with a particular IME runtime.\n").toByteArray(Charsets.UTF_8))
    }
    data.verifyArchive(archive)
    println("Built and verified category archive: ${archive.path}")
}
