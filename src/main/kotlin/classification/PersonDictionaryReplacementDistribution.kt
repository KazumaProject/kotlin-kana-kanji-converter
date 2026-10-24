package com.kazumaproject.classification

import kotlinx.serialization.json.*
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

private const val ASSET_ROOT = "app/src/main/assets"
private const val DISTRIBUTION_MANIFEST = "dictionary-distribution-manifest.json"
private val DICTIONARY_ASSET_NAMES = listOf("yomi.dat.zip", "tango.dat.zip", "token.dat.zip")

class PersonDictionaryReplacementDistribution(
    private val root: File = File("."),
) {
    private val personData = PersonDictionaryData(
        File(root, "src/main/classification"),
        File(root, "src/main/resources/id.def"),
    )
    private val classificationDirectory = File(root, "src/main/classification")
    private val taxonomy = Json.parseToJsonElement(
        File(classificationDirectory, "person-taxonomy.json").readText(),
    ).jsonObject
    private val personCategoryDefinitions = taxonomy.getValue("categories").jsonArray.associateBy {
        it.jsonObject.getValue("id").jsonPrimitive.content
    }
    private val mainCategories = readNamedCategories(
        File(classificationDirectory, "categories.json"),
    )
    private val specialistDirectory = File(root, "src/main/specialist")
    private val specialistCategories = readNamedCategories(File(specialistDirectory, "categories.json"))
    private val baseCategoryIds = mainCategories.keys + specialistCategories.keys
    private val standardPersonCategoryIds = personData.categoryIds
    private val baseCounts = readCategoryCounts(
        File(classificationDirectory, "distribution-manifest.json"),
    ) + readCategoryCounts(File(specialistDirectory, "distribution-manifest.json"))
    private val expectedCategoryCount = baseCategoryIds.size - 1 + standardPersonCategoryIds.size

    init {
        require(mainCategories.isNotEmpty() && mainCategories.containsKey("person"))
        require(specialistCategories.size == 2)
        require(baseCategoryIds.size == mainCategories.size + specialistCategories.size &&
            baseCategoryIds.toSet().size == baseCategoryIds.size)
        require(standardPersonCategoryIds.size == 29)
        require(standardPersonCategoryIds.none { it in baseCategoryIds })
        require(expectedCategoryCount == baseCategoryIds.count { it != "person" } + standardPersonCategoryIds.size)
        require(baseCounts.keys == baseCategoryIds.toSet())
    }

    fun build(baseArchive: File, personCategoriesArchive: File, archive: File, manifestFile: File, checksumsFile: File) {
        personData.verifyArchive(personCategoriesArchive, quiet = true)
        val baseFiles = ZipFile(baseArchive).use { zip -> zip.fileEntryNames() }
        val personFiles = ZipFile(personCategoriesArchive).use { zip -> zip.fileEntryNames() }
        val removedPersonFiles = categoryAssetPaths("person")
        check(removedPersonFiles.all { it in baseFiles }) { "Base dictionary bundle is missing the generic person category" }
        check(personFiles == setOf("manifest.json") + standardPersonCategoryIds.flatMap(::personCategoryArchivePaths)) {
            "Person category archive contains unexpected paths"
        }
        val addedPersonFiles = standardPersonCategoryIds.flatMap { category ->
            personCategoryAssetPaths(category)
        }
        val finalAssetFiles = (baseFiles - removedPersonFiles + addedPersonFiles).toSortedSet()
        val fileHashes = linkedMapOf<String, String>()
        ZipFile(baseArchive).use { baseZip ->
            finalAssetFiles.filter { it !in addedPersonFiles }.forEach { path ->
                fileHashes[path] = baseZip.getInputStream(baseZip.getEntry(path)).use(::sha256)
            }
        }
        ZipFile(personCategoriesArchive).use { personZip ->
            standardPersonCategoryIds.forEach { category ->
                DICTIONARY_ASSET_NAMES.forEach { assetName ->
                    val personPath = "categories/$category/$assetName"
                    val releasePath = "$ASSET_ROOT/categories/person/$category/$assetName"
                    fileHashes[releasePath] = personZip.getInputStream(personZip.getEntry(personPath)).use(::sha256)
                }
            }
        }
        val manifestText = createManifest(fileHashes)
        archive.parentFile?.mkdirs()
        ZipOutputStream(archive.outputStream().buffered()).use { output ->
            ZipFile(baseArchive).use { baseZip ->
                finalAssetFiles.filter { it !in addedPersonFiles }.forEach { path ->
                    output.putNextEntry(ZipEntry(path).apply { time = 0L })
                    baseZip.getInputStream(baseZip.getEntry(path)).use { it.copyTo(output) }
                    output.closeEntry()
                }
            }
            ZipFile(personCategoriesArchive).use { personZip ->
                standardPersonCategoryIds.forEach { category ->
                    DICTIONARY_ASSET_NAMES.forEach { assetName ->
                        val personPath = "categories/$category/$assetName"
                        val releasePath = "$ASSET_ROOT/categories/person/$category/$assetName"
                        output.putNextEntry(ZipEntry(releasePath).apply { time = 0L })
                        personZip.getInputStream(personZip.getEntry(personPath)).use { it.copyTo(output) }
                        output.closeEntry()
                    }
                }
            }
            output.putNextEntry(ZipEntry(DISTRIBUTION_MANIFEST).apply { time = 0L })
            output.write(manifestText.toByteArray(Charsets.UTF_8))
            output.closeEntry()
        }
        manifestFile.parentFile?.mkdirs()
        manifestFile.writeText(manifestText, Charsets.UTF_8)
        verify(baseArchive, archive, manifestFile)
        checksumsFile.parentFile?.mkdirs()
        checksumsFile.writeText(
            "${sha256(archive)}  ${archive.name}\n",
            Charsets.UTF_8,
        )
        println("Built person-category replacement bundle: categories=$expectedCategoryCount, " +
            "personSubcategories=${standardPersonCategoryIds.size}, archiveSha256=${sha256(archive)}")
    }

    fun verify(baseArchive: File, archive: File, externalManifest: File? = null) {
        val baseFiles = ZipFile(baseArchive).use { it.fileEntryNames() }
        val removedPersonFiles = categoryAssetPaths("person")
        check(removedPersonFiles.all { it in baseFiles }) { "Base dictionary bundle is missing the generic person category" }
        val addedPersonFiles = standardPersonCategoryIds.flatMap { category ->
            personCategoryAssetPaths(category)
        }
        val expectedAssets = (baseFiles - removedPersonFiles + addedPersonFiles).toSortedSet()
        val actualFiles = ZipFile(archive).use { it.fileEntryNames() }
        check(actualFiles == expectedAssets + DISTRIBUTION_MANIFEST) {
            "Replacement bundle paths differ: missing=${(expectedAssets + DISTRIBUTION_MANIFEST) - actualFiles}, " +
                "unexpected=${actualFiles - (expectedAssets + DISTRIBUTION_MANIFEST)}"
        }
        check(removedPersonFiles.none { it in actualFiles }) {
            "Replacement bundle still contains the generic person dictionary files"
        }

        val actualHashes = linkedMapOf<String, String>()
        ZipFile(archive).use { zip ->
            expectedAssets.forEach { path ->
                actualHashes[path] = zip.getInputStream(zip.getEntry(path)).use(::sha256)
            }
            val manifestBytes = zip.getInputStream(zip.getEntry(DISTRIBUTION_MANIFEST)).use { it.readBytes() }
            val manifestText = manifestBytes.toString(Charsets.UTF_8)
            check(manifestText == createManifest(actualHashes)) { "Distribution manifest differs from bundle contents or taxonomy" }
            externalManifest?.let {
                check(it.isFile && it.readText(Charsets.UTF_8) == manifestText) {
                    "External manifest differs from the manifest inside the bundle"
                }
            }
        }

        ZipFile(baseArchive).use { baseZip ->
            ZipFile(archive).use { finalZip ->
                (baseFiles - removedPersonFiles).forEach { path ->
                    val baseHash = baseZip.getInputStream(baseZip.getEntry(path)).use(::sha256)
                    val finalHash = finalZip.getInputStream(finalZip.getEntry(path)).use(::sha256)
                    check(baseHash == finalHash) { "Unchanged dictionary asset differs from base bundle: $path" }
                }
            }
        }
        personData.verifyReleaseCategories(archive)
        println("Verified person-category replacement bundle: categories=$expectedCategoryCount, " +
            "removed=person, added=${standardPersonCategoryIds.size}")
    }

    fun extractCategoryAssets(archive: File, category: String, outputDirectory: File) {
        require(category in standardPersonCategoryIds) { "Not a standard-enabled person category: $category" }
        outputDirectory.mkdirs()
        ZipFile(archive).use { zip ->
            DICTIONARY_ASSET_NAMES.forEach { assetName ->
                val path = "$ASSET_ROOT/categories/person/$category/$assetName"
                val entry = zip.getEntry(path) ?: error("Missing person category asset: $path")
                val outputName = assetName.removeSuffix(".zip")
                val nested = ZipInputStream(zip.getInputStream(entry)).use { input ->
                    check(input.nextEntry?.name == outputName) { "Invalid nested category asset: $path" }
                    input.readBytes()
                }
                File(outputDirectory, outputName).writeBytes(nested)
            }
            val posPath = "$ASSET_ROOT/pos_table.dat"
            val pos = zip.getEntry(posPath) ?: error("Missing shared POS table")
            File(outputDirectory, "pos_table.dat").outputStream().use { out ->
                zip.getInputStream(pos).use { it.copyTo(out) }
            }
            val connectionPath = "$ASSET_ROOT/connectionId.dat.zip"
            val connection = zip.getEntry(connectionPath) ?: error("Missing connection matrix")
            ZipInputStream(zip.getInputStream(connection)).use { input ->
                check(input.nextEntry?.name == "connectionId.dat") { "Invalid nested connection matrix" }
                File(outputDirectory, "connectionId.dat").outputStream().use { input.copyTo(it) }
            }
        }
    }

    private fun createManifest(fileHashes: Map<String, String>): String {
        val otherCategories = (mainCategories + specialistCategories).filterKeys { it != "person" }
        val entries = buildJsonArray {
            otherCategories.forEach { (id, label) ->
                add(buildJsonObject {
                    put("id", id)
                    put("label", label)
                    put("recordCount", baseCounts.getValue(id))
                    put("assetPaths", JsonArray(categoryAssetPaths(id).map(::JsonPrimitive)))
                })
            }
            standardPersonCategoryIds.forEach { id ->
                val definition = personCategoryDefinitions.getValue(id).jsonObject
                val categoryRecords = personData.records.getValue(id)
                add(buildJsonObject {
                    put("id", id)
                    put("label", definition.getValue("label").jsonPrimitive.content)
                    put("parentCategoryId", "person")
                    put("dictionaryType", "person")
                    put("recordCount", categoryRecords.size)
                    put("uniquePairs", categoryRecords.map { it.yomi to it.tango }.toSet().size)
                    put("assetPaths", JsonArray(personCategoryAssetPaths(id).map(::JsonPrimitive)))
                })
            }
        }
        check(entries.size == expectedCategoryCount)
        val personLabel = mainCategories.getValue("person")
        val personFamily = buildJsonObject {
            put("id", "person")
            put("label", personLabel)
            put("replacement", "category_split")
            put("categoryIds", JsonArray(standardPersonCategoryIds.map(::JsonPrimitive)))
        }
        val files = buildJsonObject {
            fileHashes.toSortedMap().forEach { (path, hash) -> put(path, hash) }
        }
        val manifest = buildJsonObject {
            put("schemaVersion", 1)
            put("distributionType", "person_category_replacement")
            put("replacesCategory", "person")
            put("categoryCount", expectedCategoryCount)
            put("personCategoryCount", standardPersonCategoryIds.size)
            put("personTaxonomyVersion", taxonomy.getValue("taxonomy_version").jsonPrimitive.content)
            put("personSourceSha256", sha256(File(classificationDirectory, "person-dictionary-candidates.tsv.gz")))
            put("restrictedPersonRecordsIncluded", false)
            put("unclassifiedPersonRecordsIncluded", false)
            put("personCategoryFamily", personFamily)
            put("categories", entries)
            put("files", files)
        }
        return Json { prettyPrint = true; prettyPrintIndent = "  " }.encodeToString(JsonObject.serializer(), manifest) + "\n"
    }

    private fun categoryAssetPaths(category: String): Set<String> =
        DICTIONARY_ASSET_NAMES.mapTo(linkedSetOf()) { "$ASSET_ROOT/categories/$category/$it" }

    private fun personCategoryAssetPaths(category: String): List<String> =
        DICTIONARY_ASSET_NAMES.map { "$ASSET_ROOT/categories/person/$category/$it" }

    private fun personCategoryArchivePaths(category: String): List<String> =
        DICTIONARY_ASSET_NAMES.map { "categories/$category/$it" }

    private fun readNamedCategories(path: File): Map<String, String> {
        val rows = Json.parseToJsonElement(path.readText()).jsonObject.getValue("categories").jsonArray
        return rows.associate { element ->
            val row = element.jsonObject
            row.getValue("id").jsonPrimitive.content to row.getValue("name").jsonPrimitive.content
        }
    }

    private fun readCategoryCounts(path: File): Map<String, Int> =
        Json.parseToJsonElement(path.readText()).jsonObject.getValue("categoryRows").jsonObject.mapValues {
            it.value.jsonPrimitive.int
        }

    private fun ZipFile.fileEntryNames(): Set<String> = entries().asSequence()
        .filterNot { it.isDirectory }
        .map { it.name }
        .toSet()

    private fun sha256(file: File): String = file.inputStream().buffered().use(::sha256)

    private fun sha256(input: java.io.InputStream): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

fun main(args: Array<String>) {
    require(args.isNotEmpty() && args[0] in setOf("--build", "--verify")) {
        "Usage: --build --base <base.zip> --person <person-categories.zip> --archive <output.zip> " +
            "--manifest <output.json> --checksums <output.txt> | --verify --base <base.zip> --archive <output.zip>"
    }
    val options = args.drop(1).also { require(it.size % 2 == 0) }.chunked(2).associate { (key, value) ->
        require(key.startsWith("--"))
        key.removePrefix("--") to File(value)
    }
    val distribution = PersonDictionaryReplacementDistribution()
    val base = options.getValue("base")
    val archive = options.getValue("archive")
    when (args[0]) {
        "--build" -> distribution.build(
            base,
            options.getValue("person"),
            archive,
            options.getValue("manifest"),
            options.getValue("checksums"),
        )
        "--verify" -> distribution.verify(base, archive, options["manifest"])
    }
}
