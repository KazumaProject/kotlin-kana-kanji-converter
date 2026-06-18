package mozc_runtime

import kotlin.test.Test

class MozcKotlinEngineGoldenTest {
    @Test
    fun finalEngineResultMatchesOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("conversion/engine_startconversion.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.engine.MozcKotlinEngine")
    }
}
