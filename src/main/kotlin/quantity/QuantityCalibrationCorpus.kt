package com.kazumaproject.quantity

import com.kazumaproject.mozc.ConnectionMatrix
import java.io.File

/** Build-time contrastive decoding using the same lexical costs, matrix and numeric grammar as the IME. */
internal class QuantityCalibrationCorpus(
    resources: File,
    source: File,
    private val model: QuantityScoringModel,
    private val matrix: ConnectionMatrix,
    private val schema: QuantityContextSource.Schema,
) {
    data class Example(val split: String, val group: String, val prefix: String, val quantity: String,
                       val suffix: String, val cardinal: String, val unitReading: String, val unit: String,
                       val expected: String, val preferQuantity: Boolean) {
        val input = prefix + quantity.replace("|", "") + suffix
        fun components(): List<Example> {
            val pieces = quantity.split('|')
            if (pieces.size == 1) return listOf(this)
            require(pieces.size % 2 == 1)
            val values = cardinal.split('|'); val readings = unitReading.split('|'); val labels = unit.split('|')
            require(values.size == (pieces.size + 1) / 2 && readings.size == values.size && labels.size == values.size)
            var before = prefix
            return pieces.mapIndexedNotNull { index, piece ->
                val component = if (index % 2 == 0) copy(prefix = before, quantity = piece, cardinal = values[index / 2],
                    unitReading = readings[index / 2], unit = labels[index / 2]) else null
                before += piece; component
            }
        }
    }
    private data class Symbol(val quantity: Long, val lexical: Long)
    private data class Arc(val end: Int, val text: String, val left: Int, val right: Int, val base: Int,
                           val features: IntArray, val symbol: Symbol, val quantity: Boolean = false)
    data class Path(val base: Int, val features: IntArray, val text: String) {
        fun cost(weights: IntArray): Int = base + features.indices.sumOf { features[it] * weights[it] }
    }
    private data class State(val right: Int, val history: List<Symbol>, val quantity: Boolean, val output: Int, val excludedPrefix: String? = null)
    val examples: List<Example> = File(source, "ranking.tsv").readLines()
        .filter { it.isNotBlank() && !it.startsWith("#") }.map { line ->
            val f = line.split('\t'); require(f.size == 10) { "Invalid ranking row: $line" }
            Example(f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8], f[9] == "quantity")
        }.also { rows ->
            require(rows.all { it.split in setOf("train", "test") })
            require(rows.groupBy { it.group }.values.all { group -> group.map { it.split }.distinct().size == 1 })
        }
    private val words: Map<String, List<Arc>>
    private val order = schema.patterns.maxOf { it.features.size }
    init {
        val readings = examples.flatMap { example -> example.input.indices.flatMap { start ->
            (start + 1..example.input.length).map { end -> example.input.substring(start, end) }
        } }.toHashSet()
        val found = HashMap<String, MutableList<Arc>>()
        for (file in (0..9).map { File(resources, "dictionary%02d.txt".format(it)) } + File(resources, "suffix.txt")) {
            file.useLines { lines -> lines.forEach { line ->
                val reading = line.substringBefore('\t')
                if (reading !in readings) return@forEach
                val f = line.split('\t'); if (f.size < 5) return@forEach
                val left = f[1].toInt(); val right = f[2].toInt()
                found.getOrPut(reading) { arrayListOf() }.add(Arc(reading.length, f[4], left, right, f[3].toInt(),
                    IntArray(QuantityContextSource.FEATURE_COUNT), Symbol(0, model.classes(f[4], left, right))))
            } }
        }
        words = found.mapValues { it.value.distinct() }
    }

    private fun numeric(example: Example, weights: IntArray): List<Arc> {
        val expression = CardinalGrammar.parse(example.cardinal) ?: error("Invalid annotated cardinal: $example")
        val labels = example.unit.split('+'); val readings = example.unitReading.split('+')
        val source = example.quantity.dropLast(readings.drop(1).sumOf { it.length })
        val native = model.numbers(source).filter { it.value == expression.value }.map {
            Arc(0, it.text, it.left, it.right, it.cost, IntArray(QuantityContextSource.FEATURE_COUNT), Symbol(0, 0), true)
        } + model.quantities(source).filter { it.value == expression.value && it.unit == labels.first() }.map {
            Arc(0, it.text, it.left, it.right, it.cost, IntArray(QuantityContextSource.FEATURE_COUNT), Symbol(0, 0), true)
        }
        val nativePaths = if (native.isNotEmpty()) {
            var paths = native
            for (at in 1 until labels.size) paths = paths.flatMap { before ->
                model.units(readings[at]).filter { it.text == labels[at] && it.role == QuantityScoringModel.UnitRole.SUFFIX }.map { after ->
                    val features = before.features.copyOf(); features[QuantityContextSource.SUFFIX_JOIN]++
                    Arc(0, before.text + after.text, before.left, after.right,
                        before.base + matrix.getCost(before.right, after.left) + after.cost, features, Symbol(0, 0), true)
                }
            }
            paths.map { it.copy(end = example.prefix.length + example.quantity.length,
                text = expression.value.toString() + labels.joinToString(""),
                symbol = Symbol(model.quantityClasses[labels.joinToString("")] ?: 0L, 0)) }
        } else emptyList()
        val grammar = NumericGrammarGraph(example.cardinal, expression, model)
        data class NumericState(val left: Int, val right: Int)
        val rows = Array(grammar.size + 1) { HashMap<NumericState, Path>() }
        for (start in 0 until grammar.size) for (arc in grammar.starts[start]) {
            val word = arc.lexeme
            val joining = IntArray(QuantityContextSource.FEATURE_COUNT).also {
                it[0] = arc.joining.smallProducts; it[1] = arc.joining.largeProducts; it[2] = arc.joining.additions
            }
            val predecessors = if (start == 0) listOf(NumericState(word.left, 0) to Path(0, IntArray(QuantityContextSource.FEATURE_COUNT), ""))
                else rows[start].entries.map { it.key to it.value }
            for ((before, path) in predecessors) {
                val candidate = Path(path.base + word.cost + if (start == 0) 0 else matrix.getCost(before.right, word.left),
                    IntArray(QuantityContextSource.FEATURE_COUNT) { path.features[it] + joining[it] }, "")
                val key = NumericState(before.left, word.right)
                val old = rows[arc.end][key]
                if (old == null || candidate.cost(weights) < old.cost(weights)) rows[arc.end][key] = candidate
            }
        }
        data class UnitPath(val text: String, val left: Int, val right: Int, val cost: Int, val joins: Int)
        require(labels.size == readings.size)
        val whole = model.units(readings.joinToString("")).filter {
            it.text == labels.joinToString("") && it.role == QuantityScoringModel.UnitRole.COUNTER
        }
        var units = whole.map { UnitPath(it.text, it.left, it.right, it.cost, 0) }
        if (units.isEmpty()) {
            units = model.units(readings.first()).filter { it.text == labels.first() && it.role == QuantityScoringModel.UnitRole.COUNTER }
                .map { UnitPath(it.text, it.left, it.right, it.cost, 0) }
            for (at in 1 until labels.size) units = units.flatMap { before ->
                model.units(readings[at]).filter { it.text == labels[at] && it.role == QuantityScoringModel.UnitRole.SUFFIX }.map { after ->
                    UnitPath(before.text + after.text, before.left, after.right,
                        before.cost + matrix.getCost(before.right, after.left) + after.cost, before.joins + 1)
                }
            }
        }
        require(units.isNotEmpty()) { "Missing typed unit: $example" }
        return nativePaths + rows.last().flatMap { (state, path) -> units.map { unit ->
            val features = path.features.copyOf(); features[QuantityContextSource.SUFFIX_JOIN] += unit.joins
            Arc(example.prefix.length + example.quantity.length, expression.value.toString() + unit.text, state.left, unit.right,
                path.base + matrix.getCost(state.right, unit.left) + unit.cost, features,
                Symbol(model.quantityClasses[unit.text] ?: model.quantityClasses[labels.first()] ?: 0L, 0L), true)
        } }
    }

    fun decode(example: Example, weights: IntArray, quantity: Boolean?, expected: String? = null, excluded: Set<String> = emptySet()): Path? {
        val rows = Array(example.input.length + 1) { HashMap<State, Path>() }
        rows[0][State(0, emptyList(), false, 0, if (excluded.isEmpty()) null else "")] = Path(0, IntArray(QuantityContextSource.FEATURE_COUNT), "")
        val quantities = example.components().associate { it.prefix.length to numeric(it, weights) }
        for (start in example.input.indices) {
            if (rows[start].isEmpty()) continue
            val arcs = ArrayList<Arc>()
            for (end in start + 1..example.input.length) {
                words[example.input.substring(start, end)]?.forEach { arcs.add(it.copy(end = end)) }
            }
            quantities[start]?.let(arcs::addAll)
            if (arcs.isEmpty()) arcs.add(Arc(start + 1, example.input.substring(start, start + 1), 0, 0, 10000,
                IntArray(QuantityContextSource.FEATURE_COUNT), Symbol(0, 0)))
            for ((state, path) in rows[start]) for (arc in arcs) {
                if (quantity == false && arc.quantity) continue
                if (expected != null && !expected.startsWith(arc.text, state.output)) continue
                val history = state.history + arc.symbol
                val features = IntArray(QuantityContextSource.FEATURE_COUNT) { path.features[it] + arc.features[it] }
                for (pattern in schema.patterns) {
                    if (pattern.features.size > history.size) continue
                    val offset = history.size - pattern.features.size
                    if (pattern.features.indices.all { index ->
                        val feature = pattern.features[index]; val symbol = history[offset + index]
                        val bits = if (feature.kind == QuantityScoringModel.FeatureKind.QUANTITY) symbol.quantity else symbol.lexical
                        bits and feature.classes != 0L
                    }) {
                        features[pattern.family]++
                        pattern.unitFamily?.let { features[it]++ }
                    }
                }
                val key = State(arc.right, history.takeLast(order - 1), state.quantity || arc.quantity,
                    if (expected == null) 0 else state.output + arc.text.length,
                    state.excludedPrefix?.let { prefix -> (prefix + arc.text).takeIf { next -> excluded.any { it.startsWith(next) } } })
                val candidate = Path(path.base + matrix.getCost(state.right, arc.left) + arc.base, features, path.text + arc.text)
                val old = rows[arc.end][key]
                if (old == null || candidate.cost(weights) < old.cost(weights)) rows[arc.end][key] = candidate
            }
        }
        return rows.last().filter { (state, _) -> (quantity == null || state.quantity == quantity) && state.excludedPrefix !in excluded && (expected == null || state.output == expected.length) }
            .map { (state, path) -> path.copy(base = path.base + matrix.getCost(state.right, 0)) }.minByOrNull { it.cost(weights) }
    }

    fun competing(example: Example, weights: IntArray): Path? = decode(example, weights, if (example.preferQuantity) null else true,
        excluded = if (example.preferQuantity) setOf(example.expected) else emptySet())

    fun calibrate(anchors: List<QuantityRankCalibrator.Anchor>): IntArray {
        val expanded = anchors.map { QuantityRankCalibrator.Anchor(it.features.copyOf(QuantityContextSource.FEATURE_COUNT), it.target) }
        var weights = QuantityRankCalibrator.fit(QuantityContextSource.FEATURE_COUNT, expanded, emptyList())
        val preferences = LinkedHashMap<String, QuantityRankCalibrator.Preference>()
        repeat(30) {
            val before = weights
            for (example in examples.filter { it.split == "train" }) {
                val desired = decode(example, weights, example.preferQuantity, example.expected)
                    ?: error("Missing annotated path: ${example.input} -> ${example.expected}")
                val competing = competing(example, weights) ?: continue
                val difference = DoubleArray(QuantityContextSource.FEATURE_COUNT) { (desired.features[it] - competing.features[it]).toDouble() }
                val base = (desired.base - competing.base).toDouble()
                val preference = QuantityRankCalibrator.Preference(difference, base, margin = 1000.0)
                preferences["${difference.toList()}:$base"] = preference
            }
            weights = QuantityRankCalibrator.fit(QuantityContextSource.FEATURE_COUNT, expanded, preferences.values.toList())
            if (weights.contentEquals(before)) return weights
        }
        return weights
    }
}
