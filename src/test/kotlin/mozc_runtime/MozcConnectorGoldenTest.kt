package mozc_runtime

import kotlin.test.Test

class MozcConnectorGoldenTest {
    @Test
    fun connectionCostsMatchOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("dictionary/connector_cost.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.converter.Connector")
    }
}
