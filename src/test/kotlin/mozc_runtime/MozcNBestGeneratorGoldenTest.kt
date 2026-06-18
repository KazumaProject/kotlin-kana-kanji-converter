package mozc_runtime

import kotlin.test.Test

class MozcNBestGeneratorGoldenTest {
    @Test
    fun candidateOrderAndInnerSegmentsMatchOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("conversion/nbest_generator.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.converter.NBestGenerator")
    }
}
