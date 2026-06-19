package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.engine.MozcConversionRequest
import mozc_runtime.engine.MozcKotlinEngine
import mozc_runtime.engine.MozcModules
import mozc_runtime.engine.MozcRequestType
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals

class MozcKotlinEngineGoldenTest {
    @Test
    fun finalEngineResultMatchesOfficialMozc() {
        val fixture = MozcDictionaryGoldenSupport.readEngineFixture(
            MozcGoldenTestSupport.fixture("engine/mozc_kotlin_engine.json"),
        )
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val fixedTime = Instant.parse(fixture.fixedTime)
        val modules = MozcModules.fromMozcDataManager(dataManager, fixedTime)
        val engine = MozcKotlinEngine(modules)
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.engine.MozcKotlinEngine")

        assertEquals("24.11.oss", fixture.engineDataVersion)
        assertEquals("2011-04-18T15:06:31Z", fixture.fixedTime)

        fixture.cases.forEach { case ->
            val requestType = MozcRequestType.valueOf(case.requestType)
            val actual = engine.evaluate(
                MozcConversionRequest(
                    requestType = requestType,
                    input = case.input,
                    context = case.context,
                    maxCandidates = 20,
                    fixedTime = fixedTime,
                ),
            )
            assertEquals(requestType, actual.requestType, "requestType input=${case.input}")
            assertEquals(case.input, actual.input, "input requestType=${case.requestType}")
            assertEquals(case.context, actual.context, "context requestType=${case.requestType} input=${case.input}")
            assertEquals(fixture.engineDataVersion, actual.dataVersion, "dataVersion input=${case.input}")
            assertEquals(case.segments.size, actual.segments.size, "segment count requestType=${case.requestType} input=${case.input}")

            case.segments.forEachIndexed { segmentIndex, expectedSegment ->
                val actualSegment = actual.segments[segmentIndex]
                assertEquals(expectedSegment.index, actualSegment.index, "segment index requestType=${case.requestType} input=${case.input}")
                assertEquals(expectedSegment.key, actualSegment.key, "segment key requestType=${case.requestType} input=${case.input} segment=$segmentIndex")
                assertEquals(
                    expectedSegment.candidates.size,
                    actualSegment.candidates.size,
                    "candidate count requestType=${case.requestType} input=${case.input} segment=$segmentIndex expected=${expectedSegment.candidates.map { it.value }} actual=${actualSegment.candidates.map { it.value }}",
                )
                expectedSegment.candidates.forEachIndexed { candidateIndex, expectedCandidate ->
                    val actualCandidate = actualSegment.candidates[candidateIndex]
                    val comparable = GoldenEngineCandidate(
                        index = actualCandidate.index,
                        key = actualCandidate.key,
                        value = actualCandidate.value,
                        contentKey = actualCandidate.contentKey,
                        contentValue = actualCandidate.contentValue,
                        cost = actualCandidate.cost,
                        wcost = actualCandidate.wcost,
                        structureCost = actualCandidate.structureCost,
                        lid = actualCandidate.lid,
                        rid = actualCandidate.rid,
                        attributes = actualCandidate.attributes,
                        description = actualCandidate.description,
                        category = actualCandidate.category,
                        innerSegments = actualCandidate.innerSegments.map { inner ->
                            GoldenInnerSegment(
                                index = inner.index,
                                key = inner.key,
                                value = inner.value,
                                contentKey = inner.contentKey,
                                contentValue = inner.contentValue,
                            )
                        },
                        source = actualCandidate.source,
                        types = actualCandidate.types,
                        consumedKeySize = actualCandidate.consumedKeySize,
                    )
                    assertEquals(
                        expectedCandidate,
                        comparable,
                        "candidate requestType=${case.requestType} input=${case.input} segment=$segmentIndex candidate=$candidateIndex",
                    )
                }
            }
        }
    }
}
