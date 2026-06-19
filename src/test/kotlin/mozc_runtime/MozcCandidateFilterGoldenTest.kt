package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.CandidateFilter
import mozc_runtime.converter.ConversionOptions
import mozc_runtime.converter.RequestType
import mozc_runtime.dictionary.PosMatcher
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class MozcCandidateFilterGoldenTest {
    @Test
    fun filteredCandidateSetMatchesOfficialMozc() {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val posMatcher = PosMatcher(dataManager.posMatcherData)
        val fixture = MozcDictionaryGoldenSupport.readCandidateFilterFixture(
            MozcGoldenTestSupport.fixture("converter/candidate_filter.json"),
        )

        assertEquals("24.11.oss", fixture.engineDataVersion)
        fixture.cases.forEach { case ->
            assertNotEquals(
                case.beforeFilter,
                case.afterFilter,
                "fixture must contain a real before/after delta input=${case.input}",
            )
            val filter = CandidateFilter(posMatcher)
            val before = case.beforeFilter.map { expected ->
                Candidate().also { candidate ->
                    candidate.key = expected.key
                    candidate.value = expected.value
                    candidate.contentKey = expected.key
                    candidate.contentValue = expected.value
                    candidate.lid = expected.lid
                    candidate.rid = expected.rid
                    candidate.cost = expected.cost
                    candidate.wcost = expected.cost
                    candidate.structureCost = 0
                    candidate.attributes = Attribute.bitsOf(expected.attributes)
                }
            }
            val actual = filter.filterCandidates(
                options = ConversionOptions(requestType = RequestType.CONVERSION),
                originalKey = case.input,
                candidates = before,
            )

            val actualGolden = actual.map { candidate ->
                GoldenFilterCandidate(
                    key = candidate.key,
                    value = candidate.value,
                    lid = candidate.lid,
                    rid = candidate.rid,
                    cost = candidate.cost,
                    attributes = Attribute.namesOf(candidate.attributes),
                )
            }
            assertEquals(case.afterFilter, actualGolden, "afterFilter input=${case.input}")

            val removed = case.beforeFilter.filterNot { it in case.afterFilter }
            val actualRemoved = case.beforeFilter.filterNot { it in actualGolden }
            assertEquals(removed, actualRemoved, "removed candidate set input=${case.input}")
        }
    }
}
