package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.prediction.Predictor
import kotlin.test.Test
import kotlin.test.assertEquals

class MozcZeroQueryGoldenTest {
    @Test
    fun zeroQueryResultMatchesOfficialMozc() {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val predictor = Predictor.fromMozcDataManager(dataManager)
        val fixture = MozcDictionaryGoldenSupport.readZeroQueryFixture(
            MozcGoldenTestSupport.fixture("prediction/zero_query.json"),
        )
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.prediction.ZeroQueryDict")

        assertEquals("24.11.oss", fixture.engineDataVersion)
        assertEquals(
            listOf("ありがとう", "おはよう", "こんにちは", "こんばんは", "よろしく"),
            fixture.cases.map { it.context },
        )
        fixture.cases.forEach { case ->
            val actual = predictor.zeroQuery(case.context).mapIndexed { index, result ->
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
            assertEquals(case.results.size, actual.size, "candidate count context=${case.context}")
            assertEquals(case.results, actual, "zero query results context=${case.context}")
        }
    }
}
