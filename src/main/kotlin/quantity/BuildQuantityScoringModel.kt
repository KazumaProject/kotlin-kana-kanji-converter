package com.kazumaproject.quantity

import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.mozc.ConnectionMatrixParser
import java.io.File
import java.nio.ByteBuffer
import java.security.MessageDigest

object QuantityModelSource {
    private data class Word(val reading: String, val left: Int, val right: Int, val cost: Int, val text: String)
    private fun fingerprint(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    fun numericModel(resources: File, source: File): QuantityScoringModel {
        val idFile = File(resources, "id.def")
        val contexts = idFile.readLines().associate { it.substringBefore(' ').toInt() to it.substringAfter(' ') }
        val numericIds = contexts.filterValues { it.startsWith("名詞,数,") }.keys
        val quantity = QuantitySource.parse(source, idFile)
        val counterUnits = File(source, "units.txt").readLines().map(String::trim)
            .filter { it.isNotEmpty() && !it.startsWith("#") && !it.startsWith("@") }.toSet()
        val suffixPairs = quantity.suffixes.map { it.reading to it.output }.toSet()
        val schema = QuantityContextSource.schema(quantity, File(source.parentFile, "quantity-model"))
        val reviewedReadings = (File(source, "counter-readings.tsv").readLines() +
            File(source.parentFile, "quantity-model/native-readings.tsv").readLines())
            .filter { it.isNotBlank() && !it.startsWith("#") }.map { it.split('\t') }
            .groupBy { it[2] }
        val wholeCandidates = ArrayList<Pair<Word, Pair<Long, String>>>()
        val quantities = ArrayList<QuantityScoringModel.QuantityLexeme>()
        val baseWords = ArrayList<Word>()
        val numbers = ArrayList<QuantityScoringModel.Lexeme>()
        val units = ArrayList<QuantityScoringModel.UnitLexeme>()
        for (file in (0..9).map { File(resources, "dictionary%02d.txt".format(it)) } + File(resources, "suffix.txt")) {
            file.useLines { lines -> lines.filter { it.isNotBlank() && !it.startsWith("#") }.forEach { line ->
                val fields = line.split('\t'); require(fields.size >= 5)
                val word = Word(fields[0], fields[1].toInt(), fields[2].toInt(), fields[3].toInt(), fields[4])
                if (word.text in schema.words) baseWords.add(word)
                if (word.left in numericIds && word.right in numericIds) {
                    val value = CardinalGrammar.surfaceValue(word.text)
                    if (value != null && value >= 0)
                        numbers.add(QuantityScoringModel.Lexeme(word.reading, word.text, value, word.left, word.right, word.cost))
                }
                val feature = contexts.getValue(word.left)
                if (word.left in numericIds || feature.startsWith("名詞,一般,") || feature.startsWith("名詞,副詞可能,")) {
                    for (unit in counterUnits) if (word.text.endsWith(unit)) {
                        val value = CardinalGrammar.surfaceValue(word.text.dropLast(unit.length))
                        if (value != null) wholeCandidates.add(word to (value to unit))
                    }
                    for (reading in reviewedReadings[word.reading].orEmpty()) {
                        val value = reading[0].toLong(); val unit = reading[1]
                        if (word.text.endsWith(unit) && CardinalGrammar.surfaceValue(word.text.dropLast(unit.length)) == value)
                            quantities.add(QuantityScoringModel.QuantityLexeme(word.reading, word.text, value, unit,
                                word.left, word.right, word.cost))
                    }
                }
                val counter = feature.startsWith("名詞,接尾,助数詞,")
                val suffix = counter || feature.startsWith("名詞,副詞可能,") || feature.startsWith("名詞,接尾,一般,")
                if (counter && word.text in counterUnits)
                    units.add(QuantityScoringModel.UnitLexeme(word.reading, word.text, QuantityScoringModel.UnitRole.COUNTER, word.left, word.right, word.cost))
                if (suffix && word.reading to word.text in suffixPairs)
                    units.add(QuantityScoringModel.UnitLexeme(word.reading, word.text, QuantityScoringModel.UnitRole.SUFFIX, word.left, word.right, word.cost))
            } }
        }
        val counterReadings = units.filter { it.role == QuantityScoringModel.UnitRole.COUNTER }.groupBy { it.text }
        for ((word, meaning) in wholeCandidates) {
            val (value, unit) = meaning
            if (counterReadings[unit].orEmpty().any { counter -> word.reading.endsWith(counter.reading) &&
                    CardinalGrammar.parse(word.reading.dropLast(counter.reading.length))?.value == value })
                quantities.add(QuantityScoringModel.QuantityLexeme(word.reading, word.text, value, unit, word.left, word.right, word.cost))
        }
        val matrix = ConnectionMatrixParser.parse(File(resources, "connection_single_column.txt").toPath())
        val indexed = numbers.groupBy { it.reading }
        val anchors = numbers.groupBy { it.reading to it.value }.mapNotNull { (identity, words) ->
            val expression = CardinalGrammar.parse(identity.first) ?: return@mapNotNull null
            if (expression.value != identity.second || expression.atoms.size < 2) return@mapNotNull null
            val cost = atomicCost(expression, indexed, matrix) ?: return@mapNotNull null
            val target = words.minOf { matrix.getCost(0, it.left) + it.cost + matrix.getCost(it.right, 0) }
            val features = expression.features
            QuantityRankCalibrator.Anchor(doubleArrayOf(features.smallProducts.toDouble(), features.largeProducts.toDouble(),
                features.additions.toDouble()), (target - cost).toDouble())
        }
        val suffixAnchors = units.filter { it.role == QuantityScoringModel.UnitRole.COUNTER }.mapNotNull { whole ->
            val alternatives = quantity.suffixes.filter { whole.text == it.base + it.output && whole.reading.endsWith(it.reading) }
                .flatMap { suffix ->
                    val baseReading = whole.reading.dropLast(suffix.reading.length)
                    units.filter { it.role == QuantityScoringModel.UnitRole.COUNTER && it.text == suffix.base && it.reading == baseReading }
                        .flatMap { before -> units.filter { it.role == QuantityScoringModel.UnitRole.SUFFIX && it.text == suffix.output && it.reading == suffix.reading }
                            .map { after -> matrix.getCost(0, before.left) + before.cost + matrix.getCost(before.right, after.left) +
                                after.cost + matrix.getCost(after.right, 0) } }
                }
            val base = alternatives.minOrNull() ?: return@mapNotNull null
            val target = matrix.getCost(0, whole.left) + whole.cost + matrix.getCost(whole.right, 0)
            QuantityRankCalibrator.Anchor(doubleArrayOf(0.0, 0.0, 0.0, 1.0), (target - base).toDouble())
        }
        require(anchors.size >= 5) { "Insufficient real numeric lexical anchors" }
        val weights = QuantityRankCalibrator.fit(3, anchors, emptyList())
        val forms = baseWords.flatMap { word -> QuantityContextSource.inflections(word.text,
            contexts.getValue(word.left), schema.words.getValue(word.text)) }.distinct().groupBy { it.text }
        val inflectedLemmas = baseWords.filter { word -> QuantityContextSource.inflections(word.text,
            contexts.getValue(word.left), schema.words.getValue(word.text)).isNotEmpty() }.mapTo(HashSet()) { it.text }
        val classes = HashMap<Triple<String, Int, Int>, Long>()
        for (file in (0..9).map { File(resources, "dictionary%02d.txt".format(it)) } + File(resources, "suffix.txt")) {
            file.useLines { lines -> lines.filter { it.isNotBlank() && !it.startsWith("#") }.forEach { line ->
                val fields = line.split('\t')
                val text = fields[4]
                if (text !in schema.words && text !in forms) return@forEach
                val left = fields[1].toInt(); val right = fields[2].toInt()
                val pos = contexts.getValue(left); val parts = pos.split(',')
                if (parts.getOrNull(1) == "固有名詞") return@forEach
                var bits = if (text !in inflectedLemmas) schema.words[text] ?: 0L else 0L
                for (form in forms[text].orEmpty()) if (parts.take(5).joinToString(",") == form.family && parts.getOrNull(5) == form.conjugation)
                    bits = bits or form.classes
                if (bits != 0L) { val key = Triple(text, left, right); classes[key] = (classes[key] ?: 0L) or bits }
            } }
        }
        val rawMatrix = ByteBuffer.allocate(matrix.costs.size * 2).also { buffer -> matrix.costs.forEach(buffer::putShort) }.array()
        val numericModel = QuantityScoringModel(fingerprint(idFile.readBytes()), fingerprint(rawMatrix), numbers.distinct(), units.distinct(),
            weights, schema.quantities, classes.entries.sortedWith(compareBy({ it.key.first }, { it.key.second }, { it.key.third })).map {
                QuantityScoringModel.LexicalClass(it.key.first, it.key.second, it.key.third, it.value)
            }, emptyList(), quantities.distinct())
        val corpus = QuantityCalibrationCorpus(resources, File(source.parentFile, "quantity-model"), numericModel, matrix, schema)
        val calibrated = corpus.calibrate(anchors + suffixAnchors)
        for (example in corpus.examples) {
            val desired = corpus.decode(example, calibrated, example.preferQuantity, example.expected)
                ?: error("Missing evaluation path: ${example.input}")
            val competing = corpus.competing(example, calibrated)
            require(competing == null || desired.cost(calibrated) < competing.cost(calibrated)) {
                "Quantity ranking regression (${example.split}): ${example.input} -> ${desired.text} costs ${desired.cost(calibrated)}, competing ${competing?.text} costs ${competing?.cost(calibrated)}"
            }
            println("quantity-rank ${example.split} ${example.input}: ${desired.cost(calibrated)} ${desired.text} vs ${competing?.cost(calibrated)} ${competing?.text}")
        }
        println("quantity-model weights=${calibrated.toList()}")
        return QuantityScoringModel(numericModel.posFingerprint, numericModel.connectionFingerprint,
            numericModel.numericLexemes, numericModel.unitLexemes, calibrated.copyOf(4), schema.quantities,
            numericModel.lexicalClasses, schema.patterns.map { QuantityScoringModel.Rule(it.features, calibrated[it.family] + (it.unitFamily?.let { at -> calibrated[at] } ?: 0)) }, numericModel.quantityLexemes)
    }

    private fun atomicCost(expression: CardinalGrammar.Expression, words: Map<String, List<QuantityScoringModel.Lexeme>>,
                           matrix: ConnectionMatrix): Int? {
        var costs = mapOf(0 to 0)
        for (atom in expression.atoms) {
            val choices = words[atom.lexicalReading].orEmpty().filter { it.value == atom.value }
            if (choices.isEmpty()) return null
            val next = HashMap<Int, Int>()
            for (word in choices) {
                val cost = costs.minOf { (right, prefix) -> prefix + matrix.getCost(right, word.left) + word.cost }
                val old = next[word.right]
                if (old == null || cost < old) next[word.right] = cost
            }
            costs = next
        }
        return costs.minOfOrNull { (right, cost) -> cost + matrix.getCost(right, 0) }
    }
}

fun main(args: Array<String>) {
    require(args.size == 3) { "Expected resource directory, quantity source directory and output file" }
    val model = QuantityModelSource.numericModel(File(args[0]), File(args[1]))
    File(args[2]).also { it.parentFile.mkdirs() }.writeBytes(model.write())
    println("quantity-model-v${QuantityScoringModel.VERSION}: ${model.numericLexemes.size} numeric lexemes, ${model.unitLexemes.size} unit lexemes, construction=${model.constructionWeights.toList()}")
}
