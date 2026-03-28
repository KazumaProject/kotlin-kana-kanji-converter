package integration

import com.kazumaproject.Constants
import com.kazumaproject.buildAndWriteDictionaryArtifacts
import com.kazumaproject.connection_id.ConnectionIdBuilder
import com.kazumaproject.dictionary.DicUtils
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import org.junit.jupiter.api.Assumptions.assumeTrue
import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant
import java.util.Properties
import kotlin.io.path.exists
import kotlin.io.path.fileSize
import kotlin.io.path.inputStream
import kotlin.io.path.outputStream
import kotlin.test.Test
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.measureTime

class DictionaryBuildIntegrationTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val baselineFile: Path = repoRoot.resolve("src/test/resources/perf/dictionary-build-baseline.properties")
    private val latestReportFile: Path = repoRoot.resolve("build/reports/dictionary-build-performance/latest.properties")

    @Test
    fun buildDictionaryArtifactsFromRealSourcesSmokeTest() {
        val tempDir = Files.createTempDirectory("dictionary-build-smoke-")
        try {
            val dictionaries = buildFinalList(
                listOf("/dictionary00.txt", "/suffix.txt"),
            )
            val tokenArray = TokenArray()
            val posTablePath = tempDir.resolve("pos_table.dat")
            val posTableForBuildPath = tempDir.resolve("pos_table_for_build.dat")

            tokenArray.buildPOSTable(dictionaries, mode = 1, outputPath = posTablePath.toString())
            tokenArray.buildPOSTableWithIndex(dictionaries, mode = 1, outputPath = posTableForBuildPath.toString())

            val yomiPath = tempDir.resolve("yomi.dat")
            val tangoPath = tempDir.resolve("tango.dat")
            val tokenPath = tempDir.resolve("token.dat")

            buildAndWriteDictionaryArtifacts(
                dictionaryList = dictionaries,
                yomiOutputPath = yomiPath.toString(),
                tangoOutputPath = tangoPath.toString(),
                tokenOutputPath = tokenPath.toString(),
                mode = 1,
                skipKanaOnlyTango = true,
                posTableForBuildPath = posTableForBuildPath.toString(),
            )

            assertArtifactWritten(posTablePath)
            assertArtifactWritten(posTableForBuildPath)
            assertArtifactWritten(yomiPath)
            assertArtifactWritten(tangoPath)
            assertArtifactWritten(tokenPath)
        } finally {
            tempDir.toFile().deleteRecursively()
        }
    }

    @Test
    fun buildFullDictionaryArtifactsFromRealSources() {
        assumeTrue(
            java.lang.Boolean.getBoolean("dictionaryBuild.full"),
            "Set -DdictionaryBuild.full=true or run ./gradlew dictionaryBuildTest",
        )

        val tempDir = Files.createTempDirectory("dictionary-build-full-")
        try {
            val elapsed = measureTime {
                val dictionaries = buildFinalList(
                    listOf(
                        "/dictionary00.txt",
                        "/dictionary01.txt",
                        "/dictionary02.txt",
                        "/dictionary03.txt",
                        "/dictionary04.txt",
                        "/dictionary05.txt",
                        "/dictionary06.txt",
                        "/dictionary07.txt",
                        "/dictionary08.txt",
                        "/dictionary09.txt",
                        "/suffix.txt",
                    ),
                )

                val tokenArray = TokenArray()
                val posTablePath = tempDir.resolve("pos_table.dat")
                val posTableForBuildPath = tempDir.resolve("pos_table_for_build.dat")
                tokenArray.buildPOSTable(dictionaries, mode = 1, outputPath = posTablePath.toString())
                tokenArray.buildPOSTableWithIndex(dictionaries, mode = 1, outputPath = posTableForBuildPath.toString())

                buildAndWriteDictionaryArtifacts(
                    dictionaryList = dictionaries,
                    yomiOutputPath = tempDir.resolve("yomi.dat").toString(),
                    tangoOutputPath = tempDir.resolve("tango.dat").toString(),
                    tokenOutputPath = tempDir.resolve("token.dat").toString(),
                    mode = 1,
                    skipKanaOnlyTango = true,
                    posTableForBuildPath = posTableForBuildPath.toString(),
                )

                buildConnectionIds(tempDir.resolve("connectionId.dat"))

                assertArtifactWritten(posTablePath)
                assertArtifactWritten(posTableForBuildPath)
                assertArtifactWritten(tempDir.resolve("yomi.dat"))
                assertArtifactWritten(tempDir.resolve("tango.dat"))
                assertArtifactWritten(tempDir.resolve("token.dat"))
                assertArtifactWritten(tempDir.resolve("connectionId.dat"))
            }

            val elapsedMs = elapsed.inWholeMilliseconds
            writeLatestReport(elapsedMs)

            if (java.lang.Boolean.getBoolean("dictionaryBuild.updateBaseline")) {
                writeBaseline(elapsedMs)
            } else {
                assertWithinRegressionBudget(elapsedMs)
            }
        } finally {
            tempDir.toFile().deleteRecursively()
        }
    }

    private fun buildFinalList(fileList: List<String>) =
        (DicUtils().getListDictionary(fileList) +
                Constants.DIC_LIST +
                Constants.CUSTOM_LIST +
                Constants.NAME_LIST +
                Constants.FIXED_LIST +
                Constants.DIFFICULT_LIST +
                Constants.SYMBOL_LIST +
                Constants.NAME_MUSIC_LIST +
                Constants.NAME_IT_LIST +
                Constants.VERB_LIST +
                Constants.DOMAIN +
                Constants.ERA +
                Constants.PLACE +
                Constants.WORDS +
                Constants.ZENKANKU_LIST +
                Constants.ADDS_NEW_WORDS +
                Constants.PHISIC_NOUN_LIST +
                Constants.FIGHT_NAME +
                Constants.FOOD_NAME +
                Constants.ENTERTAIMENT_NAME +
                Constants.RESCORE_WORDS)
            .groupBy(Dictionary::yomi)
            .toSortedMap(compareBy({ it.length }, { it }))

    private fun buildConnectionIds(outputPath: Path) {
        val lines = object {}::class.java.getResourceAsStream("/connection_single_column.txt")
            ?.bufferedReader()
            ?.readLines()
            ?: error("connection_single_column.txt was not found")

        val connectionIds = lines.drop(1).map(String::toShort).toShortArray()
        ConnectionIdBuilder().writeShortArrayAsBytes(connectionIds, outputPath.toString())
    }

    private fun assertArtifactWritten(path: Path) {
        assertTrue(path.exists(), "Expected artifact to exist: $path")
        assertTrue(path.fileSize() > 0, "Expected artifact to be non-empty: $path")
    }

    private fun assertWithinRegressionBudget(elapsedMs: Long) {
        val baseline = readBaseline()
        val ratioLimit = (baseline.fullBuildMs * baseline.allowedRegressionRatio).toLong()
        val absoluteLimit = baseline.fullBuildMs + baseline.allowedRegressionMs
        val limitMs = maxOf(ratioLimit, absoluteLimit)

        println(
            "dictionary build full: ${elapsedMs.milliseconds} " +
                    "(baseline=${baseline.fullBuildMs.milliseconds}, limit=${limitMs.milliseconds})"
        )

        assertTrue(
            elapsedMs <= limitMs,
            "Full dictionary build regressed: current=${elapsedMs}ms, baseline=${baseline.fullBuildMs}ms, limit=${limitMs}ms. " +
                    "If this regression is expected, run ./gradlew updateDictionaryBuildBaseline.",
        )
    }

    private fun readBaseline(): DictionaryBuildBaseline {
        require(baselineFile.exists()) {
            "Missing baseline file at $baselineFile. Run ./gradlew updateDictionaryBuildBaseline."
        }

        val properties = Properties()
        baselineFile.inputStream().use(properties::load)
        return DictionaryBuildBaseline(
            fullBuildMs = properties.getProperty("full_build_ms").toLong(),
            allowedRegressionRatio = properties.getProperty("allowed_regression_ratio", "1.20").toDouble(),
            allowedRegressionMs = properties.getProperty("allowed_regression_ms", "3000").toLong(),
        )
    }

    private fun writeLatestReport(elapsedMs: Long) {
        val properties = Properties()
        properties.setProperty("full_build_ms", elapsedMs.toString())
        properties.setProperty("recorded_at", Instant.now().toString())
        Files.createDirectories(latestReportFile.parent)
        latestReportFile.outputStream().use { out ->
            properties.store(out, "Latest dictionary build performance result")
        }
    }

    private fun writeBaseline(elapsedMs: Long) {
        val existing = if (baselineFile.exists()) readBaseline() else null
        val properties = Properties()
        properties.setProperty("full_build_ms", elapsedMs.toString())
        properties.setProperty("allowed_regression_ratio", existing?.allowedRegressionRatio?.toString() ?: "1.20")
        properties.setProperty("allowed_regression_ms", existing?.allowedRegressionMs?.toString() ?: "3000")
        properties.setProperty("recorded_at", Instant.now().toString())
        Files.createDirectories(baselineFile.parent)
        baselineFile.outputStream().use { out ->
            properties.store(out, "Dictionary build performance baseline")
        }
        println("Updated dictionary build baseline: ${elapsedMs.milliseconds}")
    }

    private data class DictionaryBuildBaseline(
        val fullBuildMs: Long,
        val allowedRegressionRatio: Double,
        val allowedRegressionMs: Long,
    )
}
