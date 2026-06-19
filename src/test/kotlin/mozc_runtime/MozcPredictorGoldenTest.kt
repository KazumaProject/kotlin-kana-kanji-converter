package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.prediction.Predictor
import kotlin.test.Test
import kotlin.test.assertEquals

class MozcPredictorGoldenTest {
    @Test
    fun predictionResultMatchesOfficialMozc() {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val predictor = Predictor.fromMozcDataManager(dataManager)
        val fixture = MozcDictionaryGoldenSupport.readPredictionFixture(
            MozcGoldenTestSupport.fixture("prediction/predictor.json"),
        )
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.prediction.Predictor")

        assertEquals("24.11.oss", fixture.engineDataVersion)
        assertEquals(
            listOf(
                "きょ",
                "きょう",
                "ありが",
                "ありがとう",
                "とうき",
                "とうきょう",
                "にほ",
                "にほん",
                "にほんご",
                "わた",
                "わたし",
                "123",
            ),
            fixture.cases.map { it.input },
        )
        fixture.cases.forEach { case ->
            assertEquals("PREDICTION", case.requestType, "requestType input=${case.input}")
            val actual = predictor.predict(case.input).mapIndexed { index, result ->
                GoldenPredictionResult(
                    index = index,
                    key = result.key,
                    value = result.value,
                    contentKey = result.contentKey.ifEmpty { result.key },
                    contentValue = result.contentValue.ifEmpty { result.value },
                    cost = result.cost,
                    wcost = result.wcost,
                    structureCost = result.structureCost,
                    lid = result.lid,
                    rid = result.rid,
                    attributes = result.candidateAttributeNames(),
                    types = result.predictionTypeNames(),
                    candidateSource = result.candidateSource,
                    consumedKeySize = result.consumedKeySize,
                )
            }
            assertEquals(
                case.results.size,
                actual.size,
                "candidate count input=${case.input} expected=${case.results.map { it.value to it.types }} actual=${actual.map { it.value to it.types }}",
            )
            assertEquals(case.results, actual, "prediction results input=${case.input}")
        }
    }
}
