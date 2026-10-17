package com.kazumaproject.classification

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.isHiraganaOnlyPure
import com.kazumaproject.isKatakanaOnlyPure
import com.kazumaproject.mozc.MozcIdDefParser
import com.kazumaproject.mozc.ConnectionMatrixIO
import kotlinx.serialization.json.*
import java.io.*
import java.text.Normalizer
import java.util.BitSet
import java.util.zip.GZIPInputStream
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

class ClassifiedDictionaryData(
    directory: File = File("src/main/classification"),
    private val idDef: File = File("src/main/resources/id.def"),
    expectedCategoryCount: Int = 28,
) {
    val categoryIds = Json.parseToJsonElement(File(directory, "categories.json").readText())
        .jsonObject.getValue("categories").jsonArray.map { it.jsonObject.getValue("id").jsonPrimitive.content }
    /** Original source records. Packaging must not overwrite their costs. */
    val records: Map<String, Set<Dictionary>>
    private val costPolicy = CategoryCostPolicy.load()

    init {
        require(categoryIds.size == expectedCategoryCount && categoryIds.distinct().size == expectedCategoryCount && categoryIds.all { it.matches(Regex("[a-z_]+")) })
        val idCount = MozcIdDefParser.parse(idDef.toPath()).size
        val categories = categoryIds.associateWith { linkedSetOf<Dictionary>() }
        GZIPInputStream(File(directory, "distribution-candidates.tsv.gz").inputStream().buffered()).bufferedReader().useLines { lines ->
            lines.forEachIndexed { index, line ->
                val fields = line.split('\t')
                require(fields.size == 6) { "Malformed distribution row ${index + 1}" }
                val (category, reading, left, right, cost) = fields
                val surface = fields[5]
                require(reading.isNotEmpty() && surface.isNotEmpty())
                val leftId = left.toInt()
                val rightId = right.toInt()
                val wordCost = cost.toInt()
                require(leftId in 0 until idCount && rightId in 0 until idCount && wordCost in Short.MIN_VALUE..Short.MAX_VALUE)
                val entries = categories[category] ?: error("Unknown category: $category")
                check(entries.add(Dictionary(reading, leftId.toShort(), rightId.toShort(), wordCost.toShort(), surface))) {
                    "Duplicate distribution row ${index + 1}"
                }
            }
        }
        records = categories
    }

    fun build(output: File = File("src/main/resources/dictionary_categories"), posTableForBuildPath: String? = null) {
        records.forEach { (category, entries) ->
            val directory = File(output, category).apply { mkdirs() }
            buildAndWriteDictionaryArtifacts(
                entries.map { it.copy(cost = costPolicy.cost(it.yomi, it.cost)) }.groupBy { it.yomi }
                    .mapValues { (_, values) -> values.sortedWith(compareBy({ it.cost }, { it.tango }, { it.leftId }, { it.rightId })) }
                    .toSortedMap(compareBy({ it.length }, { it })),
                File(directory, "yomi.dat").path, File(directory, "tango.dat").path, File(directory, "token.dat").path,
                posTableForBuildPath = posTableForBuildPath,
            )
            println("category=$category records=${entries.size}")
        }
    }

    fun verifyArchive(archive: File) {
        ZipFile(archive).use { zip ->
            val root = "app/src/main/assets"
            fun raw(name: String): ObjectInputStream = ObjectInputStream(zip.getInputStream(zip.getEntry("$root/$name")
                ?: error("Missing asset: $name")).buffered())
            val pos = raw("pos_table.dat").use { it.readObject() as ShortArray to (it.readObject() as ShortArray) }
            require(pos.first.size == pos.second.size && pos.first.size <= Short.MAX_VALUE + 1)
            val ids = MozcIdDefParser.parse(idDef.toPath()).size
            require(pos.first.all { it.toInt() in 0 until ids } && pos.second.all { it.toInt() in 0 until ids })
            val connections = nestedStream(zip, "$root/connectionId.dat.zip", "connectionId.dat").use {
                ConnectionMatrixIO.read(it, archive.path)
            }
            require(connections.size == ids) { "Connection matrix size differs from id.def" }
            for ((category, expected) in records) {
                fun read(name: String) = rawNested(zip, "$root/categories/$category/$name.zip", name)
                val yomi = read("yomi.dat").use {
                    val lbs = it.readObject() as BitSet
                    val leaves = it.readObject() as BitSet
                    val labels = (it.readObject() as CharArray).toMutableList()
                    LOUDSWithTermId(lbs, labels, leaves, it.readObject() as IntArray)
                }
                val tango = read("tango.dat").use {
                    val lbs = it.readObject() as BitSet
                    val leaves = it.readObject() as BitSet
                    LOUDS(lbs, (it.readObject() as CharArray).toMutableList(), leaves)
                }
                val tokens = read("token.dat").use { TokenArray().also { a -> a.readExternalNotCompressStrict(it) } }
                val byReading = expected.groupBy { it.yomi }
                check(yomi.termIdsSave.size == byReading.size) { "$category: extra or missing readings" }
                check(tokens.entryCount == expected.size)
                byReading.forEach { (reading, values) ->
                    val node = yomi.getNodeIndex(reading)
                    val term = yomi.getTermId(node)
                    check(term > 0) { "$category: missing terminal reading $reading" }
                    val actual = tokens.getListDictionaryByYomiTermId(term).map {
                        val index = it.posTableIndex.toInt()
                        require(index in pos.first.indices) { "$category: invalid POS table index $index" }
                        listOf(it.nodeId, pos.first[index].toInt(), pos.second[index].toInt(), it.wordCost.toInt())
                    }.groupingBy { it }.eachCount()
                    val wanted = values.map {
                        val spelling = when {
                            it.yomi == it.tango || it.tango.isHiraganaOnlyPure() -> -2
                            it.tango.isKatakanaOnlyPure() -> -1
                            else -> tango.getNodeIndex(Normalizer.normalize(it.tango, Normalizer.Form.NFC)).also { n -> check(n >= 0) }
                        }
                        listOf(spelling, it.leftId.toInt(), it.rightId.toInt(), costPolicy.cost(reading, it.cost).toInt())
                    }.groupingBy { it }.eachCount()
                    check(actual == wanted) { "$category: spelling/POS/cost mismatch for $reading" }
                }
                println("Verified packaged category=$category readings=${byReading.size} rows=${expected.size}")
            }
        }
    }
}

private fun rawNested(zip: ZipFile, path: String, name: String): ObjectInputStream {
    return ObjectInputStream(nestedStream(zip, path, name).buffered())
}

private fun nestedStream(zip: ZipFile, path: String, name: String): ZipInputStream {
    val stream = ZipInputStream(zip.getInputStream(zip.getEntry(path) ?: error("Missing asset: $path")))
    check(stream.nextEntry?.name == name) { "Wrong nested entry: $path" }
    return stream
}

fun main(args: Array<String>) {
    require(args.size == 2 && args[0] == "--archive") { "Usage: --archive <distribution.zip>" }
    ClassifiedDictionaryData().verifyArchive(File(args[1]))
}
