package mozc_runtime

import kotlin.test.Test

class MozcPredictorGoldenTest {
    @Test
    fun predictionResultMatchesOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("prediction/predict.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.prediction.Predictor")
    }
}
