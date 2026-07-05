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

class ContextualCorrectionLookupPerformanceTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val sourceDirectory: Path = repoRoot.resolve("src/main/resources/ngram/context_sources")
    private val dataPath: Path = repoRoot.resolve("src/main/resources/ngram/context_correction.data")
    private val reportPath: Path = repoRoot.resolve("build/reports/contextual-correction-lookup-performance/latest.properties")

    @Test
    fun measureGeneratedContextualCorrectionLookupTime() {
        assumeTrue(
            java.lang.Boolean.getBoolean("contextual.correction.lookup.perf"),
            "Run ./gradlew contextualCorrectionLookupPerformanceTest to measure contextual correction lookup time.",
        )
        assumeTrue(Files.isDirectory(sourceDirectory), "Missing generated contextual correction sources: $sourceDirectory")
        assumeTrue(Files.isRegularFile(dataPath), "Missing generated contextual correction data: $dataPath")

        val loadStart = System.nanoTime()
        val dictionary = ContextualCorrectionDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart

        val compileStart = System.nanoTime()
        val compiled = ContextualCorrectionCompiler.compile(sourceDirectory)
        val compileNanos = System.nanoTime() - compileStart
        val positiveProbes = compiled.rules.map(::positiveTokens)
        val negativeProbes = positiveProbes.map { tokens ->
            tokens.mapIndexed { index, token ->
                if (index == tokens.lastIndex) token.copy(surface = token.surface + "\u0000miss") else token
            }
        }

        positiveProbes.forEach { tokens ->
            assertNotNull(dictionary.lookupBest(tokens), "Expected contextual correction positive lookup to hit: $tokens")
        }
        negativeProbes.forEach { tokens ->
            assertNull(dictionary.lookupBest(tokens), "Expected contextual correction negative lookup to miss: $tokens")
        }

        repeat(5) {
            measureLookupBest(dictionary, positiveProbes, minOps = 25_000)
            measureLookupBest(dictionary, negativeProbes, minOps = 25_000)
        }

        val positiveNs = measureLookupBest(dictionary, positiveProbes, minOps = 250_000)
        val negativeNs = measureLookupBest(dictionary, negativeProbes, minOps = 250_000)

        val properties = Properties()
        properties.setProperty("binary_size_bytes", dataPath.fileSize().toString())
        properties.setProperty("load_ns", loadNanos.toString())
        properties.setProperty("compile_fixture_ns", compileNanos.toString())
        properties.setProperty("rule_count", compiled.rules.size.toString())
        properties.setProperty("lookup_best_positive_ns_op", "%.3f".format(positiveNs))
        properties.setProperty("lookup_best_negative_ns_op", "%.3f".format(negativeNs))
        reportPath.parent.createDirectories()
        reportPath.outputStream().use { out ->
            properties.store(out, "Generated contextual correction lookup performance")
        }

        println("Contextual correction lookup performance:")
        println("  binarySizeBytes=${dataPath.fileSize()}")
        println("  loadMs=${loadNanos / 1_000_000.0}")
        println("  compileFixtureMs=${compileNanos / 1_000_000.0}")
        println("  ruleCount=${compiled.rules.size}")
        println("  lookupBest positiveNsOp=${"%.3f".format(positiveNs)} negativeNsOp=${"%.3f".format(negativeNs)}")
    }

    private fun measureLookupBest(
        dictionary: BinaryContextualCorrectionDictionary,
        probes: List<List<ContextualCorrectionToken>>,
        minOps: Int,
    ): Double {
        if (probes.isEmpty()) return 0.0
        var hits = 0
        var operations = 0
        val repeats = maxOf(1, (minOps + probes.size - 1) / probes.size)
        val start = System.nanoTime()
        repeat(repeats) {
            probes.forEach { tokens ->
                if (dictionary.lookupBest(tokens) != null) {
                    hits += 1
                }
                operations += 1
            }
        }
        blackhole = hits
        return (System.nanoTime() - start).toDouble() / operations
    }

    private fun positiveTokens(rule: ContextualCorrectionRule): List<ContextualCorrectionToken> =
        rule.items.mapIndexed { index, item ->
            when (item.kind) {
                ContextualCorrectionPatternKind.LITERAL -> ContextualCorrectionToken(
                    reading = item.reading,
                    surface = item.surface,
                    coarseClass = ContextualCorrectionCoarseClass.UNKNOWN,
                )
                ContextualCorrectionPatternKind.SLOT -> ContextualCorrectionToken(
                    reading = "slot$index",
                    surface = "フルート",
                    coarseClass = if (item.coarseClass == ContextualCorrectionCoarseClass.ANY) {
                        ContextualCorrectionCoarseClass.NOUN
                    } else {
                        item.coarseClass
                    },
                )
                ContextualCorrectionPatternKind.TARGET -> ContextualCorrectionToken(
                    reading = item.reading,
                    surface = item.surface,
                    coarseClass = ContextualCorrectionCoarseClass.VERB,
                )
            }
        }

    companion object {
        @Volatile
        private var blackhole: Int = 0
    }
}
