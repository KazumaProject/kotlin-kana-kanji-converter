package mozc_runtime

import kotlin.test.Test

class MozcSegmenterGoldenTest {
    @Test
    fun segmenterBoundaryTablesMatchOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("conversion/segmenter_boundary.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.converter.Segmenter")
    }
}
