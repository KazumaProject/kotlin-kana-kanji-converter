package engine

import com.kazumaproject.engine.KanaKanjiEngine
import kotlin.math.max
import java.io.File
import java.util.Properties
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class KanaKanjiEngineAccuracyTest {

    private lateinit var engine: KanaKanjiEngine

    @BeforeTest
    fun setUp() {
        engine = KanaKanjiEngine().apply { buildEngineForTest() }
    }

    @Test
    fun mozcEvaluationOkCasesMeetBaseline() {
        val supportedCases = loadMozcEvaluationCases()
            .filter { it.status == "OK:" }
            .filter { isSupportedMozcCommand(it.command) }

        val candidateCache = supportedCases
            .groupBy { it.input }
            .mapValues { (_, casesForInput) ->
                val requiredCandidates = casesForInput.fold(1) { acc, case ->
                    max(acc, requiredCandidatesFor(case.command))
                }
                engine.nBestPath(casesForInput.first().input, requiredCandidates)
            }

        val results = supportedCases.map { case ->
            val candidates = candidateCache.getValue(case.input)
            MozcEvaluationResult(
                case = case,
                passed = evaluateMozcCase(case, candidates),
            )
        }

        val passedCount = results.count { it.passed }
        val passRate = passedCount.toDouble() / results.size
        val baseline = readMozcEvaluationBaseline()
        val minAcceptedPassCount = max(
            (baseline.passedCases * baseline.allowedRegressionRatio).toInt(),
            baseline.passedCases - baseline.allowedRegressionCases,
        )

        assertEquals(
            baseline.supportedOkCases,
            results.size,
            "Supported Mozc OK case count changed. If the evaluation dataset was intentionally updated, refresh the baseline.",
        )
        assertTrue(
            passedCount >= minAcceptedPassCount,
            "Mozc evaluation regressed: passed=$passedCount/${results.size} ($passRate), baseline=${baseline.passedCases}/${baseline.supportedOkCases}.",
        )

        println(
            "mozc evaluation: supportedOk=${results.size} passed=$passedCount passRate=$passRate " +
                    "baseline=${baseline.passedCases}/${baseline.supportedOkCases} minAccepted=$minAcceptedPassCount"
        )
    }

    private fun loadCases(): List<AccuracyCase> {
        val file = File("src/test/resources/engine/accuracy_cases.tsv")
        return file.readLines()
            .drop(1)
            .filter { it.isNotBlank() }
            .map { line ->
                val (category, input, expected, topN) = line.split('\t')
                AccuracyCase(
                    category = category,
                    input = input,
                    expected = expected.split('|').toSet(),
                    topN = topN.toInt(),
                )
            }
    }

    private fun loadMozcEvaluationCases(): List<MozcEvaluationCase> {
        val file = File("src/test/resources/engine/mozc_evaluation.tsv")
        return file.readLines()
            .filter { it.isNotBlank() && !it.startsWith('#') }
            .map { line ->
                val parts = line.split('\t')
                MozcEvaluationCase(
                    status = parts[0],
                    input = parts[1],
                    output = parts[2],
                    command = parts[3],
                    argument = parts[4],
                    version = parts[5],
                )
            }
    }

    private fun isSupportedMozcCommand(command: String): Boolean {
        return command == "Conversion Match" ||
                command == "Conversion Not Match" ||
                command == "Conversion Expected" ||
                command.startsWith("Conversion Expected ")
    }

    private fun requiredCandidatesFor(command: String): Int {
        if (command == "Conversion Match" || command == "Conversion Not Match" || command == "Conversion Expected") {
            return 1
        }

        return command.removePrefix("Conversion Expected ").trim().toInt()
    }

    private fun evaluateMozcCase(case: MozcEvaluationCase, candidates: List<String>): Boolean {
        val topCandidate = candidates.firstOrNull() ?: return false
        return when (case.command) {
            "Conversion Match" -> topCandidate.contains(case.argument)
            "Conversion Not Match" -> !topCandidate.contains(case.argument)
            "Conversion Expected" -> topCandidate == case.argument
            else -> {
                val requiredCandidates = requiredCandidatesFor(case.command)
                candidates.take(requiredCandidates).contains(case.argument)
            }
        }
    }

    private fun readMozcEvaluationBaseline(): MozcEvaluationBaseline {
        val properties = Properties()
        File("src/test/resources/engine/mozc_evaluation_baseline.properties")
            .inputStream()
            .use(properties::load)

        return MozcEvaluationBaseline(
            supportedOkCases = properties.getProperty("supported_ok_cases").toInt(),
            passedCases = properties.getProperty("passed_cases").toInt(),
            allowedRegressionRatio = properties.getProperty("allowed_regression_ratio", "0.98").toDouble(),
            allowedRegressionCases = properties.getProperty("allowed_regression_cases", "5").toInt(),
        )
    }

    private data class AccuracyCase(
        val category: String,
        val input: String,
        val expected: Set<String>,
        val topN: Int,
    )

    private data class CaseResult(
        val case: AccuracyCase,
        val candidates: List<String>,
    )

    private data class MozcEvaluationCase(
        val status: String,
        val input: String,
        val output: String,
        val command: String,
        val argument: String,
        val version: String,
    )

    private data class MozcEvaluationResult(
        val case: MozcEvaluationCase,
        val passed: Boolean,
    )

    private data class MozcEvaluationBaseline(
        val supportedOkCases: Int,
        val passedCases: Int,
        val allowedRegressionRatio: Double,
        val allowedRegressionCases: Int,
    )
}
