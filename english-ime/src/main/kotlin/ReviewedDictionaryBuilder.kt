import converters.Converter
import converters.ConverterWithTermId
import dictionary.Dictionary
import glide.QwertyGlideIndexGenerator
import grammar.FormKey
import grammar.Lexicon
import grammar.readTsv
import kotlinx.serialization.json.*
import louds.LOUDS
import prefix.PrefixTree
import prefix.prefix_with_term_id.PrefixTreeWithTermId
import java.io.File
import java.io.ObjectOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.BitSet
import java.util.zip.ZipFile

internal data class SourceRow(val id: String, val reading: String, val surface: String, val cost: Short)

internal fun englishInventory(source: File): List<SourceRow> {
    val rows = ZipFile(source).use { zip ->
        val entry = requireNotNull(zip.getEntry("1-grams_score_cost_pos_combined_with_ner.txt")) {
            "Missing unigram TSV in $source"
        }
        zip.getInputStream(entry).bufferedReader(Charsets.UTF_8).useLines { lines ->
            val iterator = lines.iterator()
            require(iterator.hasNext() && iterator.next() == "input_word\toutput_word\tpos_tag\tscore") {
                "Invalid unigram TSV header in $source"
            }
            iterator.asSequence().mapIndexed { index, line ->
                val columns = line.split('\t')
                require(columns.size == 4) { "Invalid source row at line ${index + 2}" }
                SourceRow("tsv:${index + 2}", columns[0], columns[1], columns[3].toShort())
            }.toList()
        }
    }
    return rows + (MANUAL_WORD + TERMINAL_COMMAND + PYTHON_COMMAND + WEB_COMMAND + WEB_COMMAND_EXTRA +
        PYTHON_COMMAND_EXTRA + DEVOPS_COMMAND + UTIL_COMMAND).mapIndexed { index, row ->
        SourceRow("manual:${index + 1}", row.reading, row.word, row.cost)
    }
}

internal fun exportInventory(source: File, output: File) {
    val rows = englishInventory(source)
    output.bufferedWriter(Charsets.UTF_8).use { writer ->
        for (row in rows) {
            writer.appendLine(buildJsonObject {
                put("id", row.id)
                put("reading", row.reading)
                put("surface", row.surface)
                put("cost", row.cost.toInt())
            }.toString())
        }
    }
}

internal fun buildReviewedDictionary(
    source: File,
    decisions: File,
    lexiconDirectory: File,
    relations: File,
    output: File,
    corrections: File? = null,
    notices: File? = null,
) {
    val lexicon = Lexicon.load(lexiconDirectory)
    val forms = lexicon.forms.associateBy { it.key }
    val knownSurfaces = forms.keys.map { it.surface }.toSet()
    validateRelations(relations, knownSurfaces)
    val accepted = selectReviewedRows(englishInventory(source), decisions, forms.keys, corrections)
    val noticeDirectory = requireNotNull(notices) { "Reviewed builds require --notices DIR" }
    require(noticeDirectory.isDirectory) { "Reviewed builds require --notices DIR" }
    val destination = output.absoluteFile
    require(!destination.exists()) { "Output path already exists: $destination" }
    val parent = destination.parentFile
    require(parent.isDirectory || parent.mkdirs()) { "Cannot create $parent" }
    val staging = Files.createTempDirectory(parent.toPath(), ".english-reviewed-").toFile()
    try {
        writeReviewedPayloads(accepted, staging)
        writeReviewedCategoryBundle(lexiconDirectory, relations, decisions, noticeDirectory, staging)
        corrections?.copyTo(staging.resolve("surface-corrections.tsv"))
        Files.move(staging.toPath(), destination.toPath(), StandardCopyOption.ATOMIC_MOVE)
    } finally {
        staging.deleteRecursively()
    }
}

internal fun selectReviewedRows(rows: List<SourceRow>, decisions: File, forms: Set<FormKey>, corrections: File? = null): List<Dictionary> {
    val expected = rows.associateBy { it.id }.toMutableMap()
    val targets = mutableMapOf<String, MutableList<String>>()
    val correctionTypes = mutableMapOf<String, MutableSet<String>>()
    val seenCorrections = mutableSetOf<Pair<String, String>>()
    val surfaces = forms.map { it.surface }.toSet()
    for (record in corrections?.readTsv("id", "source", "target", "relation", "evidence").orEmpty()) {
        val (id, source, target, relation, evidence) = record
        require(seenCorrections.add(id to target) && expected[id]?.surface == source && source != target &&
            relation in setOf("case_correction", "case_candidates", "input_spelling_correction", "input_spelling_candidates") && source == source.lowercase() &&
            (if (relation.startsWith("input_spelling_")) keyboardReading(source) == expected[id]?.reading else source.lowercase() == target.lowercase()) && target in surfaces &&
            keyboardReading(target) == expected[id]?.reading && evidence.startsWith("https://")) {
            "Invalid source surface correction for $id"
        }
        targets.getOrPut(id) { mutableListOf() }.add(target)
        correctionTypes.getOrPut(id) { mutableSetOf() }.add(relation)
    }
    for ((id, values) in targets) {
        val types = correctionTypes.getValue(id)
        require(types.size == 1 && (types.single() in setOf("case_correction", "input_spelling_correction")) == (values.size == 1)) {
            "Invalid or duplicate source surface correction for $id"
        }
    }
    val accepted = mutableListOf<Dictionary>()
    val ledger = decisions.readTsv("id", "reading", "surface", "cost", "decision", "lexeme_ids", "reason", "evidence")
    val pending = ledger.count { it[4] == "pending" }
    require(pending == 0) { "Incomplete review: $pending pending decisions; no assets generated" }
    for ((index, record) in ledger.withIndex()) {
        val (id, reading, surface, cost, decision) = record
        val lexemes = record[5]
        val reason = record[6]
        val evidence = record[7]
        require(expected.remove(id) == SourceRow(id, reading, surface, cost.toShort())) {
            "Unexpected, duplicate, or changed source row on decision line ${index + 2}"
        }
        require(evidence.startsWith("https://")) { "Missing evidence URL for $id" }
        when (decision) {
            "include" -> {
                val effectiveSurfaces = targets[id] ?: listOf(surface)
                val ids = lexemes.split(',')
                require(ids.size == ids.toSet().size &&
                    ids.all { key -> effectiveSurfaces.any { FormKey(key, it) in forms } } &&
                    effectiveSurfaces.all { target -> ids.any { FormKey(it, target) in forms } }) {
                    "Included row $id lacks verified lexical membership"
                }
                require(reason == "verified" && reading.isNotBlank() && effectiveSurfaces.all { it.isNotBlank() }) {
                    "Invalid candidate for $id"
                }
                effectiveSurfaces.sorted().forEach { accepted.add(Dictionary(reading, cost.toShort(), it, reading != it)) }
            }
            "exclude" -> require(id !in targets && lexemes == "-" && reason in exclusionReasons) {
                "Excluded row $id lacks a supported reason"
            }
            else -> error("Unresolved decision for $id")
        }
    }
    require(expected.isEmpty()) { "Missing decisions for ${expected.size} rows, starting with ${expected.keys.take(5)}" }
    require(accepted.isNotEmpty()) { "The reviewed dictionary is empty" }
    return accepted
}

internal fun validateRelations(relations: File, surfaces: Set<String>) {
    val rows = relations.readTsv("relation", "source", "target", "evidence")
    require(rows.map { it.take(3) }.toSet().size == rows.size) { "Duplicate spelling relation" }
    for ((type, source, target, evidence) in rows) {
        val validSource = when (type) {
            "input_spelling" -> source == keyboardReading(target)
            "input_alias" -> source.matches(Regex("[a-z][a-z0-9_-]*"))
            "capitalization" -> source.lowercase() == target.lowercase()
            "contraction" -> true
            else -> source in surfaces
        }
        require(type in relationTypes && source != target &&
            validSource &&
            (target in surfaces || type == "contraction" && target.split(' ').all { it in surfaces }) &&
            evidence.startsWith("https://")) {
            "Invalid spelling relation $type between $source and $target"
        }
    }
}

private fun keyboardReading(surface: String): String? {
    val value = surface.replace('’', '\'').lowercase()
    if (value.any { it !in 'a'..'z' && it !in '0'..'9' && it !in "'-./" }) return null
    return value.filter { it !in "'-./" }.takeIf { it.isNotEmpty() }
}

internal fun writeReviewedPayloads(input: List<Dictionary>, output: File) {
    val grouped = input.groupBy { it.reading }.toSortedMap(compareBy<String> { it.length }.thenBy { it })
    val groups = grouped.values.map { rows ->
        rows.groupBy { it.word }.values.map { variants -> variants.minBy { it.cost } }
            .sortedWith(compareBy<Dictionary> { it.cost }.thenBy { it.word })
    }
    val readingTree = PrefixTreeWithTermId()
    grouped.keys.forEach(readingTree::insert)
    val wordTree = PrefixTree()
    val candidates = groups.flatten()
    candidates.asSequence().filter { it.reading != it.word }.map { it.word }.distinct().sorted().forEach(wordTree::insert)
    val reading = ConverterWithTermId().convert(readingTree.root).apply { convertListToBitSet() }
    val word = Converter().convert(wordTree.root).apply { convertListToBitSet() }
    ObjectOutputStream(output.resolve("reading.dat").outputStream().buffered()).use {
        it.writeObject(reading.LBS)
        it.writeObject(reading.isLeaf)
        it.writeObject(reading.labelsTemp.toCharArray())
        it.writeObject(reading.termIds.toIntArray())
    }
    val labels = word.labelsTemp.toCharArray()
    ObjectOutputStream(output.resolve("word.dat").outputStream().buffered()).use {
        it.writeObject(word.LBS)
        it.writeObject(word.isLeaf)
        it.writeObject(labels)
    }
    val wordIndex = LOUDS(word.LBS, labels, word.isLeaf)

    val delimiterAfterLast = groups.size + candidates.size
    // The Android compact format retains only words with set bits. At a word boundary
    // an unreachable token after the last delimiter keeps the last group readable.
    val padding = if (delimiterAfterLast % Long.SIZE_BITS == 0) 1 else 0
    val costs = ShortArray(candidates.size + padding)
    val nodes = IntArray(costs.size) { -1 }
    val bits = BitSet()
    var bit = 0
    var token = 0
    for (group in groups) {
        bit++
        for (candidate in group) {
            costs[token] = candidate.cost
            if (candidate.reading != candidate.word) {
                nodes[token] = wordIndex.getNodeIndex(candidate.word).also { require(it > 0) }
            }
            bits.set(bit++)
            token++
        }
    }
    if (padding == 1) bits.set(delimiterAfterLast + 1)
    ObjectOutputStream(output.resolve("token.dat").outputStream().buffered()).use {
        it.writeObject(costs)
        it.writeObject(nodes)
        it.writeObject(bits)
    }

    val glide = QwertyGlideIndexGenerator.buildEntries(candidates, includeFallback = false)
    QwertyGlideIndexGenerator.write(glide, output.resolve("qwerty_glide_index.dat"))
    println("acceptedRows=${input.size} distinctPairs=${candidates.size} readings=${groups.size} glide=${glide.size}")
}

private val exclusionReasons = setOf("malformed", "wrong_mapping", "unattested", "restricted", "ineligible_senses", "ineligible_reference", "unsupported_mapping")
private val relationTypes = setOf("contraction", "regional_spelling", "hyphen_variant", "capitalization", "derivation", "input_spelling", "spelling_variant", "input_alias")
