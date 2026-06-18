package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.converter.BoundaryType
import mozc_runtime.converter.Segmenter
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.UserPos
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class MozcSegmenterGoldenTest {
    @Test
    fun segmenterBoundaryTablesMatchOfficialMozc() {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val posMatcher = PosMatcher(dataManager.posMatcherData)
        val posGroup = PosGroup(dataManager.posGroupData)
        val userPos = UserPos(dataManager.userPosTokenData, dataManager.userPosStringData)
        val segmenter = Segmenter(dataManager, posMatcher)
        val fixture = MozcDictionaryGoldenSupport.readSegmenterFixture(
            MozcGoldenTestSupport.fixture("segmenter/segmenter_boundary.json"),
        )

        assertEquals("24.11.oss", fixture.engineDataVersion)
        assertTrue(posGroup.size() >= segmenter.leftSize)
        assertTrue(userPos.getPosList().isNotEmpty())
        assertEquals(
            listOf("へんかん", "きょう", "ありがとう", "とうきょう", "にほんご", "わたしは", "これは", "123", "第一", "山田太郎"),
            fixture.cases.map { it.input },
        )

        fixture.cases.forEach { case ->
            assertTrue(case.checks.isNotEmpty(), "segmenter case has no checks: input=${case.input}")
            case.checks.forEachIndexed { index, expected ->
                assertEquals(index, expected.order, "segmenter fixture order input=${case.input}")
                val expectedType = BoundaryType.valueOf(expected.boundaryType)
                assertEquals(
                    expectedType,
                    segmenter.getBoundaryType(expected.leftPosId, expected.rightPosId),
                    "boundaryType input=${case.input} leftPosId=${expected.leftPosId} rightPosId=${expected.rightPosId}",
                )
                assertEquals(
                    expected.result,
                    segmenter.isBoundary(expected.leftPosId, expected.rightPosId, expectedType),
                    "boundary result input=${case.input} leftPosId=${expected.leftPosId} rightPosId=${expected.rightPosId}",
                )
            }
        }
    }
}
