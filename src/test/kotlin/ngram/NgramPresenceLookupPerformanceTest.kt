package com.kazumaproject.ngram

import org.junit.jupiter.api.Assumptions.assumeTrue
import java.nio.file.Files
import java.nio.file.Path
import java.util.Properties
import kotlin.io.path.createDirectories
import kotlin.io.path.fileSize
import kotlin.io.path.outputStream
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class NgramPresenceLookupPerformanceTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val sourceDirectory: Path = repoRoot.resolve("src/main/resources/ngram/sources")
    private val dataPath: Path = repoRoot.resolve("src/main/resources/ngram/ngram_presence.data")
    private val reportPath: Path = repoRoot.resolve("build/reports/ngram-presence-lookup-performance/latest.properties")

    @Test
    fun measureGeneratedDictionaryLookupTime() {
        assumeTrue(
            java.lang.Boolean.getBoolean("ngram.lookup.perf"),
            "Run ./gradlew ngramPresenceLookupPerformanceTest to measure generated N-gram lookup time.",
        )
        assumeTrue(Files.isDirectory(sourceDirectory), "Missing generated N-gram sources: $sourceDirectory")
        assumeTrue(Files.isRegularFile(dataPath), "Missing generated N-gram presence data: $dataPath")

        val loadStart = System.nanoTime()
        val dictionary = NgramPresenceDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart

        val compileStart = System.nanoTime()
        val compiled = NgramPresenceCompiler.compile(sourceDirectory)
        val compileNanos = System.nanoTime() - compileStart
        val positiveByOrder = (1..NGRAM_SECTION_COUNT).associateWith { order ->
            compiled.keySequences.filter { it.order == order }
        }
        val negativeByOrder = positiveByOrder.mapValues { (order, values) ->
            if (values.isEmpty()) {
                listOf(NgramKeySequence(order, LongArray(order) { 0x1000L + order * 17L + it }))
            } else {
                values.map { mutateLastKey(it) }
            }
        }

        positiveByOrder.values.flatten().forEach { sequence ->
            assertTrue(contains(dictionary, sequence), "Expected positive lookup to hit: $sequence")
        }
        negativeByOrder.values.flatten().forEach { sequence ->
            assertFalse(contains(dictionary, sequence), "Expected negative lookup to miss: $sequence")
        }

        repeat(3) {
            positiveByOrder.values.forEach { measureContains(dictionary, it, minOps = 25_000) }
            negativeByOrder.values.forEach { measureContains(dictionary, it, minOps = 25_000) }
        }

        val positiveNs = positiveByOrder.mapValues { (_, probes) ->
            if (probes.isEmpty()) null else measureContains(dictionary, probes, minOps = 250_000)
        }
        val negativeNs = negativeByOrder.mapValues { (_, probes) ->
            measureContains(dictionary, probes, minOps = 250_000)
        }

        val properties = Properties()
        properties.setProperty("binary_size_bytes", dataPath.fileSize().toString())
        properties.setProperty("load_ns", loadNanos.toString())
        properties.setProperty("compile_fixture_ns", compileNanos.toString())
        properties.setProperty("resolved_entry_count", compiled.keySequences.size.toString())
        for (order in 1..NGRAM_SECTION_COUNT) {
            properties.setProperty("order${order}_entry_count", positiveByOrder.getValue(order).size.toString())
            positiveNs[order]?.let { properties.setProperty("contains${order}_positive_ns_op", "%.3f".format(it)) }
            properties.setProperty("contains${order}_negative_ns_op", "%.3f".format(negativeNs.getValue(order)))
        }
        reportPath.parent.createDirectories()
        reportPath.outputStream().use { out ->
            properties.store(out, "Generated N-gram presence lookup performance")
        }

        println("N-gram presence lookup performance:")
        println("  binarySizeBytes=${dataPath.fileSize()}")
        println("  loadMs=${loadNanos / 1_000_000.0}")
        println("  compileFixtureMs=${compileNanos / 1_000_000.0}")
        println("  resolvedEntryCount=${compiled.keySequences.size}")
        for (order in 1..NGRAM_SECTION_COUNT) {
            val positive = positiveNs[order]?.let { "%.3f".format(it) } ?: "n/a"
            val negative = "%.3f".format(negativeNs.getValue(order))
            println("  contains$order positiveNsOp=$positive negativeNsOp=$negative entries=${positiveByOrder.getValue(order).size}")
        }
    }

    private fun measureContains(
        dictionary: BinaryNgramPresenceDictionary,
        probes: List<NgramKeySequence>,
        minOps: Int,
    ): Double {
        if (probes.isEmpty()) {
            return 0.0
        }
        var hits = 0
        var operations = 0
        val repeats = maxOf(1, (minOps + probes.size - 1) / probes.size)
        val start = System.nanoTime()
        repeat(repeats) {
            probes.forEach { sequence ->
                if (contains(dictionary, sequence)) {
                    hits += 1
                }
                operations += 1
            }
        }
        blackhole = hits
        return (System.nanoTime() - start).toDouble() / operations
    }

    private fun contains(dictionary: BinaryNgramPresenceDictionary, sequence: NgramKeySequence): Boolean {
        return when (sequence.order) {
            1 -> dictionary.contains1(sequence.keys[0])
            2 -> dictionary.contains2(sequence.keys[0], sequence.keys[1])
            3 -> dictionary.contains3(sequence.keys[0], sequence.keys[1], sequence.keys[2])
            4 -> dictionary.contains4(sequence.keys[0], sequence.keys[1], sequence.keys[2], sequence.keys[3])
            5 -> dictionary.contains5(sequence.keys[0], sequence.keys[1], sequence.keys[2], sequence.keys[3], sequence.keys[4])
            else -> false
        }
    }

    private fun mutateLastKey(sequence: NgramKeySequence): NgramKeySequence {
        val keys = sequence.keys.copyOf()
        keys[keys.lastIndex] = keys[keys.lastIndex] xor 0x6a09e667f3bcc909L
        return NgramKeySequence(sequence.order, keys)
    }

    companion object {
        @Volatile
        private var blackhole: Int = 0
    }
}
