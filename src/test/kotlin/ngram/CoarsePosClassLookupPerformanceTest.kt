package com.kazumaproject.ngram

import org.junit.jupiter.api.Assumptions.assumeTrue
import java.nio.file.Files
import java.nio.file.Path
import java.util.Properties
import kotlin.io.path.createDirectories
import kotlin.io.path.fileSize
import kotlin.io.path.outputStream
import kotlin.test.Test
import kotlin.test.assertEquals

class CoarsePosClassLookupPerformanceTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val idDefPath: Path = repoRoot.resolve("src/main/resources/id.def")
    private val dataPath: Path = repoRoot.resolve("src/main/resources/ngram/coarse_pos_class.data")
    private val reportPath: Path = repoRoot.resolve("build/reports/coarse-pos-class-lookup-performance/latest.properties")

    @Test
    fun measureGeneratedCoarsePosClassLookupTime() {
        assumeTrue(
            java.lang.Boolean.getBoolean("coarse.pos.class.lookup.perf"),
            "Run ./gradlew coarsePosClassLookupPerformanceTest to measure coarse POS class lookup time.",
        )
        assumeTrue(Files.isRegularFile(idDefPath), "Missing id.def: $idDefPath")
        assumeTrue(Files.isRegularFile(dataPath), "Missing generated coarse POS class data: $dataPath")

        val loadStart = System.nanoTime()
        val table = CoarsePosClassDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart
        val ids = IntArray(table.idCount) { it }

        repeat(5) {
            measureClassify(table, ids, minOps = 100_000)
        }
        val classifyNs = measureClassify(table, ids, minOps = 2_000_000)
        val verifyStart = System.nanoTime()
        val verified = CoarsePosClassVerifier.verify(idDefPath, dataPath)
        val verifyNanos = System.nanoTime() - verifyStart

        assertEquals(table.idCount, verified.verifiedIdCount)

        val properties = Properties()
        properties.setProperty("binary_size_bytes", dataPath.fileSize().toString())
        properties.setProperty("load_ns", loadNanos.toString())
        properties.setProperty("id_count", table.idCount.toString())
        properties.setProperty("classify_ns_op", "%.3f".format(classifyNs))
        properties.setProperty("verify_ns", verifyNanos.toString())
        reportPath.parent.createDirectories()
        reportPath.outputStream().use { out ->
            properties.store(out, "Generated coarse POS class lookup performance")
        }

        println("Coarse POS class lookup performance:")
        println("  binarySizeBytes=${dataPath.fileSize()}")
        println("  loadMs=${loadNanos / 1_000_000.0}")
        println("  idCount=${table.idCount}")
        println("  classifyNsOp=${"%.3f".format(classifyNs)}")
        println("  verifyMs=${verifyNanos / 1_000_000.0}")
    }

    private fun measureClassify(
        table: CoarsePosClassTable,
        ids: IntArray,
        minOps: Int,
    ): Double {
        if (ids.isEmpty()) return 0.0
        var checksum = 0
        var operations = 0
        val repeats = maxOf(1, (minOps + ids.size - 1) / ids.size)
        val startedAt = System.nanoTime()
        repeat(repeats) {
            ids.forEach { id ->
                checksum += table.classify(id).id
                operations += 1
            }
        }
        blackhole = checksum
        return (System.nanoTime() - startedAt).toDouble() / operations
    }

    companion object {
        @Volatile
        private var blackhole: Int = 0
    }
}
