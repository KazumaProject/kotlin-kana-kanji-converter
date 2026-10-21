package com.kazumaproject.classification

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.isHiraganaOnlyPure
import com.kazumaproject.isKatakanaOnlyPure
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.mozc.MozcIdDefParser
import kotlinx.serialization.json.*
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.ObjectInputStream
import java.text.Normalizer
import java.nio.file.Files
import java.security.MessageDigest
import java.util.BitSet
import java.util.TreeMap
import java.util.zip.GZIPInputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

private data class PersonDictionaryRow(
    val categoryId: String,
    val dictionary: Dictionary,
    val sportSubcategories: Set<String>,
)

class PersonDictionaryData(
    private val classificationDirectory: File = File("src/main/classification"),
    private val idDef: File = File("src/main/resources/id.def"),
) {
    private val taxonomy = Json.parseToJsonElement(
        File(classificationDirectory, "person-taxonomy.json").readText(),
    ).jsonObject
    private val categories = taxonomy.getValue("categories").jsonArray
    val categoryIds: List<String> = categories.mapNotNull { element ->
        val category = element.jsonObject
        if (category.getValue("standard_enabled").jsonPrimitive.boolean) {
            category.getValue("id").jsonPrimitive.content
        } else null
    }
    private val nonStandardCategoryIds = categories.mapNotNull { element ->
        val category = element.jsonObject
        if (!category.getValue("standard_enabled").jsonPrimitive.boolean) {
            category.getValue("id").jsonPrimitive.content
        } else null
    }.toSet()
    private val requiredRestrictedCategoryIds = setOf(
        "adult_performer", "adult_work_creator", "crime_offender", "espionage", "organized_crime", "religion", "terrorism",
    )
    private val sportIds = taxonomy.getValue("sport_subcategories").jsonObject.keys
    private val idCount = if (idDef.isFile) MozcIdDefParser.parse(idDef.toPath()).size else null
    private val rows: List<PersonDictionaryRow>
    val records: Map<String, List<Dictionary>>
    private val sportTagsByPair: Map<Pair<String, String>, Set<String>>

    init {
        require(categoryIds.size == 24 && categoryIds.distinct().size == categoryIds.size)
        require(nonStandardCategoryIds == requiredRestrictedCategoryIds + "unclassified_person")
        val policy = taxonomy.getValue("policy").jsonObject
        require(policy.getValue("standard_dictionary_excluded_categories").jsonArray
            .map { it.jsonPrimitive.content }.toSet() == requiredRestrictedCategoryIds)
        require(policy.getValue("restricted_category_records").jsonPrimitive.content == "aggregate_counts_only")
        require(policy.getValue("adult_distribution").jsonObject.let { adultDistribution ->
            adultDistribution.getValue("adult_performer").jsonPrimitive.content == "metadata_only" &&
                adultDistribution.getValue("adult_work_creator").jsonPrimitive.content == "metadata_only"
        })
        require(policy
            .getValue("adult_related_hold").jsonObject
            .getValue("distribution").jsonPrimitive.content == "metadata_only")
        val file = File(classificationDirectory, "person-dictionary-candidates.tsv.gz")
        val parsed = mutableListOf<PersonDictionaryRow>()
        val seen = mutableSetOf<List<Any>>()
        val tagsByPair = mutableMapOf<Pair<String, String>, Set<String>>()
        GZIPInputStream(file.inputStream().buffered()).bufferedReader().useLines { lines ->
            lines.forEachIndexed { index, line ->
                val fields = line.split('\t')
                require(fields.size == 7) { "Malformed person dictionary row ${index + 1}" }
                val categoryId = fields[0]
                val reading = fields[1]
                val leftText = fields[2]
                val rightText = fields[3]
                val costText = fields[4]
                val surface = fields[5]
                val tagText = fields[6]
                require(categoryId in categoryIds) {
                    if (categoryId in nonStandardCategoryIds) {
                        "Restricted person category found in standard dictionary source"
                    } else {
                        "Unknown or disabled person category in standard dictionary source"
                    }
                }
                require(reading.isNotBlank() && surface.isNotBlank())
                require(reading.none { it == '\r' || it == '\n' } && surface.none { it == '\r' || it == '\n' })
                val left = leftText.toInt()
                val right = rightText.toInt()
                val cost = costText.toInt()
                idCount?.let { count -> require(left in 0 until count && right in 0 until count) }
                require(cost in Short.MIN_VALUE..Short.MAX_VALUE)
                val tags: Set<String> = if (tagText.isEmpty()) emptySet() else tagText.split(',').toSet()
                require(tags.size == if (tagText.isEmpty()) 0 else tagText.split(',').size)
                require(tags.all { it in sportIds })
                val dictionary = Dictionary(reading, left.toShort(), right.toShort(), cost.toShort(), surface)
                val identity = listOf(categoryId, dictionary.yomi, dictionary.leftId,
                    dictionary.rightId, dictionary.cost, dictionary.tango)
                require(seen.add(identity)) { "Duplicate person dictionary record at row ${index + 1}" }
                parsed += PersonDictionaryRow(categoryId, dictionary, tags)
                if (tags.isNotEmpty()) {
                    val pair = reading to surface
                    tagsByPair[pair] = (tagsByPair[pair] ?: emptySet()) + tags
                }
            }
        }
        require(parsed.isNotEmpty()) { "Person dictionary source is empty" }
        rows = parsed
        records = categoryIds.associateWith { category ->
            rows.asSequence().filter { it.categoryId == category }.map { it.dictionary }.toList()
        }
        sportTagsByPair = tagsByPair
    }

    fun buildArchive(archive: File) {
        require(idCount != null) { "Missing Mozc id.def required to build the person dictionary" }
        val sharedPosTable = File("src/main/resources/pos_table.dat")
        val sharedPosIndex = File("src/main/resources/pos_table_for_build.dat")
        check(sharedPosTable.isFile && sharedPosIndex.isFile) {
            "Missing shared POS tables; run the standard dictionary generation before person categories"
        }
        val temporary = Files.createTempDirectory("person-dictionary-assets-").toFile()
        try {
            val categoryDirectory = File(temporary, "categories").apply { mkdirs() }
            categoryIds.forEach { category ->
                val directory = File(categoryDirectory, category).apply { mkdirs() }
                buildAndWriteDictionaryArtifacts(
                    groupByReading(records.getValue(category)),
                    File(directory, "yomi.dat").path,
                    File(directory, "tango.dat").path,
                    File(directory, "token.dat").path,
                    mode = 1,
                    posTableForBuildPath = sharedPosIndex.path,
                )
            }

            val packagedFiles = linkedMapOf<String, ByteArray>()
            categoryIds.forEach { category ->
                val directory = File(categoryDirectory, category)
                listOf("yomi.dat", "tango.dat", "token.dat").forEach { name ->
                    packagedFiles["categories/$category/$name.zip"] = nestedZip(name, File(directory, name).readBytes())
                }
            }
            val manifest = createManifest(packagedFiles)
            packagedFiles["manifest.json"] = manifest.toByteArray(Charsets.UTF_8)
            archive.parentFile?.mkdirs()
            ZipOutputStream(archive.outputStream().buffered()).use { zip ->
                packagedFiles.toSortedMap().forEach { (path, bytes) ->
                    zip.putNextEntry(ZipEntry(path).apply { time = 0L })
                    zip.write(bytes)
                    zip.closeEntry()
                }
            }
            val digest = sha256(archive.readBytes())
            File(archive.parentFile, "DICTIONARY-SHA256SUMS").writeText(
                "$digest  ${archive.name}\n", Charsets.UTF_8,
            )
            verifyArchive(archive)
            println("Built standard person dictionaries: categories=${categoryIds.size}, " +
                "pairs=${rows.map { it.categoryId to (it.dictionary.yomi to it.dictionary.tango) }.toSet().size}, " +
                "records=${rows.size}, archiveSha256=$digest")
        } finally {
            temporary.deleteRecursively()
        }
    }

    fun verifyArchive(archive: File, quiet: Boolean = false) {
        ZipFile(archive).use { zip ->
            val manifestEntry = zip.getEntry("manifest.json") ?: error("Missing manifest.json")
            val manifest = zip.getInputStream(manifestEntry).bufferedReader(Charsets.UTF_8).use {
                Json.parseToJsonElement(it.readText()).jsonObject
            }
            check(manifest.keys == setOf(
                "schemaVersion", "taxonomyVersion", "sourceSha256", "categoryCount",
                "uniquePairs", "recordCount", "categories", "sportSubcategories", "files",
            )) { "Manifest contains missing or unexpected fields" }
            check(manifest.getValue("schemaVersion").jsonPrimitive.int == 1)
            check(manifest.getValue("taxonomyVersion").jsonPrimitive.content ==
                taxonomy.getValue("taxonomy_version").jsonPrimitive.content)
            check(manifest.getValue("sourceSha256").jsonPrimitive.content ==
                sha256(File(classificationDirectory, "person-dictionary-candidates.tsv.gz").readBytes()))
            val manifestCategories = manifest.getValue("categories").jsonArray.map {
                it.jsonObject.getValue("id").jsonPrimitive.content
            }
            check(manifest.getValue("categoryCount").jsonPrimitive.int == categoryIds.size)
            check(manifestCategories == categoryIds) { "Manifest category list differs from the standard taxonomy" }
            val expectedFiles = mutableSetOf("manifest.json")
            categoryIds.forEach { category ->
                listOf("yomi.dat", "tango.dat", "token.dat").forEach { name ->
                    expectedFiles += "categories/$category/$name.zip"
                    check(zip.getEntry("categories/$category/$name.zip") != null) {
                        "Missing category asset: $category/$name"
                    }
                }
            }
            val actualFiles = zip.entries().asSequence().map { it.name }.toSet()
            check(actualFiles == expectedFiles) { "Archive contains missing or unexpected files" }
            val hashes = manifest.getValue("files").jsonObject
            check(hashes.keys == expectedFiles - "manifest.json")
            hashes.forEach { (path, expectedHash) ->
                val bytes = zip.getInputStream(zip.getEntry(path)).use { it.readBytes() }
                check(sha256(bytes) == expectedHash.jsonPrimitive.content) { "Asset hash mismatch: $path" }
            }

            val posTable = File("src/main/resources/pos_table.dat")
            check(posTable.isFile) { "Missing shared POS table required to verify person categories" }
            val pos = ObjectInputStream(posTable.inputStream().buffered()).use {
                (it.readObject() as ShortArray) to (it.readObject() as ShortArray)
            }
            val expectedIdCount = idCount ?: error("Missing Mozc id.def required to verify person categories")
            check(pos.first.size == pos.second.size && pos.first.isNotEmpty())
            check(pos.first.all { it.toInt() in 0 until expectedIdCount } &&
                pos.second.all { it.toInt() in 0 until expectedIdCount })
            val manifestRecordCount = manifest.getValue("recordCount").jsonPrimitive.int
            check(manifestRecordCount == rows.size)
            val manifestCategoryCounts = manifest.getValue("categories").jsonArray.associate { element ->
                val category = element.jsonObject
                check(category.keys == setOf("id", "pairs", "records")) {
                    "Category manifest entry contains missing or unexpected fields"
                }
                category.getValue("id").jsonPrimitive.content to category
            }
            val expectedUniquePairs = rows.map {
                it.categoryId to (it.dictionary.yomi to it.dictionary.tango)
            }.toSet().size
            check(manifest.getValue("uniquePairs").jsonPrimitive.int == expectedUniquePairs)
            for (category in categoryIds) {
                val expected = records.getValue(category)
                val expectedPairs = expected.map { it.yomi to it.tango }.toSet().size
                val manifestCategory = manifestCategoryCounts[category]
                    ?: error("Missing manifest entry for category=$category")
                check(manifestCategory.getValue("records").jsonPrimitive.int == expected.size) {
                    "Manifest record count differs for category=$category"
                }
                check(manifestCategory.getValue("pairs").jsonPrimitive.int == expectedPairs) {
                    "Manifest pair count differs for category=$category"
                }
                val yomi = nestedObject(zip, "categories/$category/yomi.dat.zip", "yomi.dat")
                val tango = nestedObject(zip, "categories/$category/tango.dat.zip", "tango.dat")
                val token = nestedObject(zip, "categories/$category/token.dat.zip", "token.dat")
                verifyDictionaryAssets(category, expected, yomi, tango, token, pos)
            }
            if (!quiet) {
                println("Verified standard person dictionary archive: categories=${categoryIds.size}, " +
                    "records=$manifestRecordCount, sharedPosTable=true")
            }
        }
    }

    fun verifyReleaseCategories(archive: File, assetRoot: String = "app/src/main/assets") {
        ZipFile(archive).use { zip ->
            val posEntry = zip.getEntry("$assetRoot/pos_table.dat")
                ?: error("Missing shared POS table in replacement archive")
            val pos = ObjectInputStream(zip.getInputStream(posEntry).buffered()).use {
                (it.readObject() as ShortArray) to (it.readObject() as ShortArray)
            }
            val expectedIdCount = idCount ?: error("Missing Mozc id.def required to verify person categories")
            check(pos.first.size == pos.second.size && pos.first.isNotEmpty())
            check(pos.first.all { it.toInt() in 0 until expectedIdCount } &&
                pos.second.all { it.toInt() in 0 until expectedIdCount })
            for (category in categoryIds) {
                val expected = records.getValue(category)
                val yomi = nestedObject(zip, "$assetRoot/categories/person/$category/yomi.dat.zip", "yomi.dat")
                val tango = nestedObject(zip, "$assetRoot/categories/person/$category/tango.dat.zip", "tango.dat")
                val token = nestedObject(zip, "$assetRoot/categories/person/$category/token.dat.zip", "token.dat")
                verifyDictionaryAssets(category, expected, yomi, tango, token, pos)
            }
        }
    }

    private fun createManifest(files: Map<String, ByteArray>): String {
        val uniquePairs = rows.map { it.categoryId to (it.dictionary.yomi to it.dictionary.tango) }.toSet().size
        val categoryRows = categoryIds.joinToString(",\n") { category ->
            val selected = rows.filter { it.categoryId == category }
            val pairs = selected.map { it.dictionary.yomi to it.dictionary.tango }.toSet().size
            "    {\"id\":\"$category\",\"pairs\":$pairs,\"records\":${selected.size}}"
        }
        val sportCounts = sportTagsByPair.values.flatten().groupingBy { it }.eachCount().toSortedMap()
            .entries.joinToString(",") { (id, count) -> "\"$id\":$count" }
        val fileHashes = files.toSortedMap().entries.joinToString(",\n") { (path, bytes) ->
            "    \"$path\":\"${sha256(bytes)}\""
        }
        return """{
  "schemaVersion": 1,
  "taxonomyVersion": ${jsonString(taxonomy.getValue("taxonomy_version").jsonPrimitive.content)},
  "sourceSha256": "${sha256(File(classificationDirectory, "person-dictionary-candidates.tsv.gz").readBytes())}",
  "categoryCount": ${categoryIds.size},
  "uniquePairs": $uniquePairs,
  "recordCount": ${rows.size},
  "categories": [
$categoryRows
  ],
  "sportSubcategories": {$sportCounts},
  "files": {
$fileHashes
  }
}
"""
    }

    private fun groupByReading(entries: List<Dictionary>): java.util.SortedMap<String, List<Dictionary>> {
        val grouped = entries.groupBy { it.yomi }
        val comparator = compareBy<String>({ it.length }, { it })
        return TreeMap<String, List<Dictionary>>(comparator).apply {
            putAll(grouped.mapValues { (_, values) ->
                values.sortedWith(compareBy({ it.cost }, { it.tango }, { it.leftId }, { it.rightId }))
            })
        }
    }

    private fun nestedZip(name: String, bytes: ByteArray): ByteArray {
        val output = ByteArrayOutputStream()
        ZipOutputStream(output).use { zip ->
            zip.putNextEntry(ZipEntry(name).apply { time = 0L })
            zip.write(bytes)
            zip.closeEntry()
        }
        return output.toByteArray()
    }

    private fun nestedObject(zip: ZipFile, path: String, name: String): ByteArray {
        val entry = zip.getEntry(path) ?: error("Missing category asset: $path")
        val bytes = ZipInputStream(zip.getInputStream(entry)).use { nested ->
            check(nested.nextEntry?.name == name) { "Invalid nested category asset: $path" }
            val content = nested.readBytes()
            check(content.isNotEmpty()) { "Empty category asset: $path" }
            check(nested.nextEntry == null) { "Unexpected nested entry: $path" }
            content
        }
        return bytes
    }

    private fun verifyDictionaryAssets(
        label: String,
        expected: List<Dictionary>,
        yomiBytes: ByteArray,
        tangoBytes: ByteArray,
        tokenBytes: ByteArray,
        pos: Pair<ShortArray, ShortArray>,
    ) {
        val yomi = ObjectInputStream(ByteArrayInputStream(yomiBytes)).use { input ->
            val lbs = input.readObject() as BitSet
            val leaves = input.readObject() as BitSet
            val labels = (input.readObject() as CharArray).toMutableList()
            LOUDSWithTermId(lbs, labels, leaves, input.readObject() as IntArray)
        }
        val tango = ObjectInputStream(ByteArrayInputStream(tangoBytes)).use { input ->
            val lbs = input.readObject() as BitSet
            val leaves = input.readObject() as BitSet
            val labels = (input.readObject() as CharArray).toMutableList()
            LOUDS(lbs, labels, leaves)
        }
        val tokens = ObjectInputStream(ByteArrayInputStream(tokenBytes)).use { input ->
            TokenArray().also { it.readExternalNotCompressStrict(input) }
        }
        check(pos.first.size == pos.second.size)
        check(tokens.entryCount == expected.size) { "$label: token record count differs" }
        val byReading = expected.groupBy { it.yomi }
        check(yomi.termIdsSave.size == byReading.size) { "$label: reading count differs" }
        byReading.forEach { (reading, values) ->
            val node = yomi.getNodeIndex(reading)
            val term = yomi.getTermId(node)
            check(term > 0) { "$label: missing terminal reading" }
            val actual = tokens.getListDictionaryByYomiTermId(term).map { token ->
                val index = token.posTableIndex.toInt()
                require(index in pos.first.indices) { "$label: invalid POS table index" }
                listOf(token.nodeId, pos.first[index].toInt(), pos.second[index].toInt(), token.wordCost.toInt())
            }.groupingBy { it }.eachCount()
            val wanted = values.map { entry ->
                val spelling = when {
                    entry.yomi == entry.tango || entry.tango.isHiraganaOnlyPure() -> -2
                    entry.tango.isKatakanaOnlyPure() -> -1
                    else -> tango.getNodeIndex(Normalizer.normalize(entry.tango, Normalizer.Form.NFC))
                        .also { index -> check(index >= 0) { "$label: missing surface spelling" } }
                }
                listOf(spelling, entry.leftId.toInt(), entry.rightId.toInt(), entry.cost.toInt())
            }.groupingBy { it }.eachCount()
            check(actual == wanted) { "$label: spelling, POS, or cost differs for a reading" }
        }
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }

    private fun jsonString(value: String): String = JsonPrimitive(value).toString()
}

fun main(args: Array<String>) {
    require(args.size == 2 && args[0] in setOf("--build", "--verify")) {
        "Usage: --build <output.zip> | --verify <person-dictionary.zip>"
    }
    val data = PersonDictionaryData()
    when (args[0]) {
        "--build" -> data.buildArchive(File(args[1]))
        "--verify" -> data.verifyArchive(File(args[1]))
    }
}
