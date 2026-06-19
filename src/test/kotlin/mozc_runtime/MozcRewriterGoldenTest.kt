package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.CandidateFilter
import mozc_runtime.converter.Connector
import mozc_runtime.converter.ConversionOptions
import mozc_runtime.converter.ImmutableConverter
import mozc_runtime.converter.InnerSegment
import mozc_runtime.converter.Lattice
import mozc_runtime.converter.NBestGenerator
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.DictionaryImpl
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.UserDictionary
import mozc_runtime.dictionary.UserPos
import mozc_runtime.dictionary.system.SystemDictionary
import mozc_runtime.dictionary.system.ValueDictionary
import mozc_runtime.prediction.Predictor
import mozc_runtime.rewriter.Rewriter
import mozc_runtime.rewriter.RewriterRequest
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class MozcRewriterGoldenTest {
    @Test
    fun rewrittenCandidatesMatchOfficialMozc() {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        val posMatcher = PosMatcher(dataManager.posMatcherData)
        val posGroup = PosGroup(dataManager.posGroupData)
        val userPos = UserPos(dataManager.userPosTokenData, dataManager.userPosStringData)
        val systemDictionary = SystemDictionary.fromMozcDataManager(dataManager)
        val dictionary = DictionaryImpl(
            systemDictionary,
            ValueDictionary(systemDictionary.valueTrie(), posMatcher.getSuggestOnlyWordId()),
            UserDictionary(listOf()),
        )
        val connector = Connector(dataManager.connectorData)
        val segmenter = mozc_runtime.converter.Segmenter(dataManager, posMatcher)
        val converter = ImmutableConverter(
            dictionary = dictionary,
            connector = connector,
            segmenter = segmenter,
            posMatcher = posMatcher,
            posGroup = posGroup,
            userDictionary = UserDictionary(listOf()),
        )
        val nbestGenerator = NBestGenerator(segmenter, connector, posMatcher, Lattice())
        val candidateFilter = CandidateFilter(posMatcher)
        val predictor = Predictor.fromMozcDataManager(dataManager)
        val fixture = MozcDictionaryGoldenSupport.readRewriterFixture(
            MozcGoldenTestSupport.fixture("rewriter/rewriter.json"),
        )
        val clock = Clock.fixed(Instant.parse(fixture.fixedTime), ZoneOffset.UTC)
        val rewriter = Rewriter.fromMozcDataManager(dataManager, posMatcher, posGroup, dictionary, clock)

        assertEquals("24.11.oss", fixture.engineDataVersion)
        assertTrue(userPos.getPosList().isNotEmpty())
        assertTrue(converter.toString().isNotEmpty())
        assertTrue(candidateFilter.filterCandidates(ConversionOptions(), "", listOf()).isEmpty())
        assertTrue(nbestGenerator.toString().isNotEmpty())
        assertTrue(predictor.predict("ありがとう").isNotEmpty())

        fixture.cases.forEach { case ->
            assertEquals("CONVERSION", case.requestType, "requestType input=${case.input}")
            val segments = buildSegments(case.beforeRewrite)
            val updated = rewriter.rewrite(
                RewriterRequest(
                    key = case.input,
                    requestType = RequestType.CONVERSION,
                    rawText = case.input,
                    compositionText = case.input,
                ),
                segments,
            )
            assertTrue(updated || case.beforeRewrite == case.afterRewrite, "rewrite flag input=${case.input}")
            val actual = flattenCandidates(segments)
            assertCandidates(case.afterRewrite, actual, case.input)
        }
    }

    private fun buildSegments(candidates: List<GoldenConverterCandidate>): Segments {
        val segments = Segments()
        var currentKey: String? = null
        var segment = segments.addSegment()
        candidates.forEach { expected ->
            if (currentKey == null) {
                currentKey = expected.key
                segment.setKey(expected.key)
            } else if (expected.key != currentKey) {
                segment = segments.addSegment()
                segment.setKey(expected.key)
                currentKey = expected.key
            }
            val candidate = segment.addCandidate()
            candidate.key = expected.key
            candidate.value = expected.value
            candidate.contentKey = expected.contentKey
            candidate.contentValue = expected.contentValue
            candidate.cost = expected.cost
            candidate.wcost = expected.wcost
            candidate.structureCost = expected.structureCost
            candidate.lid = expected.lid
            candidate.rid = expected.rid
            candidate.attributes = Attribute.bitsOf(expected.attributes)
            candidate.consumedKeySize = expected.consumedKeySize
            candidate.description = expected.description
            candidate.category = Candidate.Category.valueOf(expected.category)
            expected.innerSegments.forEach { inner ->
                candidate.innerSegments += InnerSegment(
                    key = inner.key,
                    value = inner.value,
                    contentKey = inner.contentKey,
                    contentValue = inner.contentValue,
                )
            }
        }
        return segments
    }

    private fun flattenCandidates(segments: Segments): List<GoldenConverterCandidate> =
        buildList {
            segments.conversionSegments().forEach { segment ->
                segment.candidates().forEach { candidate ->
                    add(
                        GoldenConverterCandidate(
                            index = size,
                            key = candidate.key,
                            value = candidate.value,
                            contentKey = candidate.contentKey,
                            contentValue = candidate.contentValue,
                            cost = candidate.cost,
                            wcost = candidate.wcost,
                            structureCost = candidate.structureCost,
                            lid = candidate.lid,
                            rid = candidate.rid,
                            attributes = Attribute.namesOf(candidate.attributes),
                            consumedKeySize = candidate.consumedKeySize,
                            innerSegments = candidate.innerSegments.mapIndexed { innerIndex, inner ->
                                GoldenInnerSegment(
                                    index = innerIndex,
                                    key = inner.key,
                                    value = inner.value,
                                    contentKey = inner.contentKey,
                                    contentValue = inner.contentValue,
                                )
                            },
                            description = candidate.description,
                            category = candidate.category.name,
                        ),
                    )
                }
            }
        }

    private fun assertCandidates(
        expected: List<GoldenConverterCandidate>,
        actual: List<GoldenConverterCandidate>,
        input: String,
    ) {
        assertEquals(
            expected.size,
            actual.size,
            "candidate count input=$input missing=${missingValues(expected, actual)} extra=${missingValues(actual, expected)} expectedValues=${expected.map { it.value }} actualValues=${actual.map { it.value }}",
        )
        assertEquals(
            expected.map { it.value } - actual.map { it.value }.toSet(),
            listOf(),
            "removed candidates input=$input expectedValues=${expected.map { it.value }} actualValues=${actual.map { it.value }}",
        )
        assertEquals(
            actual.map { it.value } - expected.map { it.value }.toSet(),
            listOf(),
            "inserted candidates input=$input expectedValues=${expected.map { it.value }} actualValues=${actual.map { it.value }}",
        )
        expected.forEachIndexed { index, expectedCandidate ->
            val actualCandidate = actual[index]
            assertEquals(expectedCandidate, actualCandidate, "candidate input=$input index=$index")
        }
    }

    private fun missingValues(left: List<GoldenConverterCandidate>, right: List<GoldenConverterCandidate>): List<String> {
        val counts = right.groupingBy { it.value }.eachCount().toMutableMap()
        val missing = ArrayList<String>()
        left.forEach { candidate ->
            val count = counts[candidate.value] ?: 0
            if (count == 0) {
                missing += candidate.value
            } else {
                counts[candidate.value] = count - 1
            }
        }
        return missing
    }
}
