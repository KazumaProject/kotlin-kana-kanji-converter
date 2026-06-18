package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.converter.Connector
import kotlin.test.Test
import kotlin.test.assertEquals

class MozcConnectorGoldenTest {
    @Test
    fun connectionCostsMatchOfficialMozc() {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val connector = Connector(dataManager.connectorData)
        val fixture = MozcDictionaryGoldenSupport.readConnectorFixture(
            MozcGoldenTestSupport.fixture("connector/connector_cost.json"),
        )

        assertEquals("24.11.oss", fixture.engineDataVersion)
        fixture.costs.forEachIndexed { index, expected ->
            assertEquals(index, expected.order, "connector fixture order")
            assertEquals(
                expected.cost,
                connector.cost(expected.leftId, expected.rightId),
                "connector cost label=${expected.label} leftId=${expected.leftId} rightId=${expected.rightId}",
            )
        }
    }
}
