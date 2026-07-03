package com.kazumaproject.ngram

import org.junit.jupiter.api.Assumptions.assumeTrue
import java.nio.file.Files
import java.nio.file.Path
import java.util.Properties
import kotlin.io.path.createDirectories
import kotlin.io.path.fileSize
import kotlin.io.path.outputStream
import kotlin.test.Test
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class NgramCorrectionLookupPerformanceTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val sourceDirectory: Path = repoRoot.resolve("src/main/resources/ngram/sources")
    private val dataPath: Path = repoRoot.resolve("src/main/resources/ngram/ngram_correction.data")
    private val reportPath: Path = repoRoot.resolve("build/reports/ngram-correction-lookup-performance/latest.properties")

    @Test
    fun measureGeneratedCorrectionLookupTime() {
        assumeTrue(
            java.lang.Boolean.getBoolean("ngram.correction.lookup.perf"),
            "Run ./gradlew ngramCorrectionLookupPerformanceTest to measure generated N-gram correction lookup time.",
        )
        assumeTrue(Files.isDirectory(sourceDirectory), "Missing generated N-gram sources: $sourceDirectory")
        assumeTrue(Files.isRegularFile(dataPath), "Missing generated N-gram correction data: $dataPath")

        val loadStart = System.nanoTime()
        val dictionary = NgramCorrectionDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart

        val compileStart = System.nanoTime()
        val compiled = NgramCorrectionCompiler.compile(sourceDirectory)
        val compileNanos = System.nanoTime() - compileStart
        val positiveReadings = compiled.candidates.map { it.reading }.distinct()
        val positiveByOrder = (1..NGRAM_SECTION_COUNT).associateWith { order ->
            compiled.candidates.filter { it.order == order }.map { it.reading }.distinct()
        }
        val negativeReadings = positiveReadings.map { "$it\u0000miss" }

        positiveReadings.forEach { reading ->
            assertNotNull(dictionary.lookupBest(reading), "Expected positive lookup to hit: $reading")
        }
        negativeReadings.forEach { reading ->
            assertNull(dictionary.lookupBest(reading), "Expected negative lookup to miss: $reading")
        }

        repeat(3) {
            measureLookupBest(dictionary, positiveReadings, minOps = 25_000)
            measureLookupBest(dictionary, negativeReadings, minOps = 25_000)
        }

        val positiveNs = measureLookupBest(dictionary, positiveReadings, minOps = 250_000)
        val negativeNs = measureLookupBest(dictionary, negativeReadings, minOps = 250_000)
        val positiveNsByOrder = positiveByOrder.mapValues { (_, readings) ->
            if (readings.isEmpty()) null else measureLookupBest(dictionary, readings, minOps = 100_000)
        }

        val properties = Properties()
        properties.setProperty("binary_size_bytes", dataPath.fileSize().toString())
        properties.setProperty("load_ns", loadNanos.toString())
        properties.setProperty("compile_fixture_ns", compileNanos.toString())
        properties.setProperty("candidate_count", compiled.candidates.size.toString())
        properties.setProperty("reading_count", positiveReadings.size.toString())
        properties.setProperty("lookup_best_positive_ns_op", "%.3f".format(positiveNs))
        properties.setProperty("lookup_best_negative_ns_op", "%.3f".format(negativeNs))
        for (order in 1..NGRAM_SECTION_COUNT) {
            properties.setProperty("order${order}_candidate_count", compiled.candidates.count { it.order == order }.toString())
            properties.setProperty("order${order}_reading_count", positiveByOrder.getValue(order).size.toString())
            positiveNsByOrder[order]?.let {
                properties.setProperty("lookup_best_order${order}_positive_ns_op", "%.3f".format(it))
            }
        }
        reportPath.parent.createDirectories()
        reportPath.outputStream().use { out ->
            properties.store(out, "Generated N-gram correction lookup performance")
        }

        println("N-gram correction lookup performance:")
        println("  binarySizeBytes=${dataPath.fileSize()}")
        println("  loadMs=${loadNanos / 1_000_000.0}")
        println("  compileFixtureMs=${compileNanos / 1_000_000.0}")
        println("  candidateCount=${compiled.candidates.size}")
        println("  readingCount=${positiveReadings.size}")
        println("  lookupBest positiveNsOp=${"%.3f".format(positiveNs)} negativeNsOp=${"%.3f".format(negativeNs)}")
        for (order in 1..NGRAM_SECTION_COUNT) {
            val ns = positiveNsByOrder[order]?.let { "%.3f".format(it) } ?: "n/a"
            println(
                "  order$order positiveNsOp=$ns " +
                        "candidates=${compiled.candidates.count { it.order == order }} " +
                        "readings=${positiveByOrder.getValue(order).size}"
            )
        }
    }

    private fun measureLookupBest(
        dictionary: BinaryNgramCorrectionDictionary,
        readings: List<String>,
        minOps: Int,
    ): Double {
        if (readings.isEmpty()) {
            return 0.0
        }
        var hits = 0
        var operations = 0
        val repeats = maxOf(1, (minOps + readings.size - 1) / readings.size)
        val start = System.nanoTime()
        repeat(repeats) {
            readings.forEach { reading ->
                if (dictionary.lookupBest(reading) != null) {
                    hits += 1
                }
                operations += 1
            }
        }
        blackhole = hits
        return (System.nanoTime() - start).toDouble() / operations
    }

    companion object {
        @Volatile
        private var blackhole: Int = 0
    }
}
