package mozc_runtime

import kotlin.test.Test

class MozcZeroQueryGoldenTest {
    @Test
    fun zeroQueryResultMatchesOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("zero_query/zero_query.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.prediction.ZeroQueryDict")
    }
}
