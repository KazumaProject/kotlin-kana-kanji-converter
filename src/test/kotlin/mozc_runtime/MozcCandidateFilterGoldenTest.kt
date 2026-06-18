package mozc_runtime

import kotlin.test.Test

class MozcCandidateFilterGoldenTest {
    @Test
    fun filteredCandidateSetMatchesOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("conversion/candidate_filter.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.converter.CandidateFilter")
    }
}
