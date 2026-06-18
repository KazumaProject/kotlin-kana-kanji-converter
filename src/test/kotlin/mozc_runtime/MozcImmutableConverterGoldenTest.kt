package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Connector
import mozc_runtime.converter.ConversionOptions
import mozc_runtime.converter.ImmutableConverter
import mozc_runtime.converter.Lattice
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segmenter
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.DictionaryImpl
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.UserDictionary
import mozc_runtime.dictionary.UserPos
import mozc_runtime.dictionary.system.SystemDictionary
import mozc_runtime.dictionary.system.ValueDictionary
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class MozcImmutableConverterGoldenTest {
    @Test
    fun conversionResultMatchesOfficialMozc() {
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
        val segmenter = Segmenter(dataManager, posMatcher)
        val converter = ImmutableConverter(
            dictionary = dictionary,
            connector = connector,
            segmenter = segmenter,
            posMatcher = posMatcher,
            posGroup = posGroup,
            userDictionary = UserDictionary(listOf()),
        )
        val fixture = MozcDictionaryGoldenSupport.readImmutableConverterFixture(
            MozcGoldenTestSupport.fixture("converter/immutable_converter.json"),
        )

        assertEquals("24.11.oss", fixture.engineDataVersion)
        assertTrue(userPos.getPosList().isNotEmpty())
        assertEquals(
            listOf(
                "へんかん",
                "きょう",
                "ありがとう",
                "とうきょう",
                "にほんご",
                "わたしは",
                "これは",
                "かんじ",
                "やまだたろう",
                "123",
                "第一",
            ),
            fixture.cases.map { it.input },
        )

        fixture.cases.forEach { case ->
            assertEquals("CONVERSION", case.requestType, "requestType input=${case.input}")
            val segments = Segments()
            segments.initForConvert(case.input)
            val lattice = Lattice()
            val converted = converter.convert(
                ConversionOptions(
                    requestType = RequestType.CONVERSION,
                    maxConversionCandidatesSize = 1,
                ),
                segments,
                lattice,
            )
            assertTrue(converted, "conversion failed input=${case.input}")

            assertEquals(case.segments.size, segments.conversionSegmentsSize(), "segment count input=${case.input}")
            case.segments.forEachIndexed { segmentIndex, expectedSegment ->
                assertEquals(segmentIndex, expectedSegment.index, "segment fixture index input=${case.input}")
                val actualSegment = segments.conversionSegment(segmentIndex)
                assertEquals(expectedSegment.key, actualSegment.key(), "segment key input=${case.input} segment=$segmentIndex")
                assertTrue(actualSegment.candidatesSize() > 0, "no candidates input=${case.input} segment=$segmentIndex")

                val actualCandidates = actualSegment.candidates()
                assertEquals(expectedSegment.candidates.size, actualCandidates.size, "candidate count input=${case.input} segment=$segmentIndex")
                expectedSegment.candidates.forEachIndexed { candidateIndex, expectedCandidate ->
                    assertEquals(candidateIndex, expectedCandidate.index, "candidate fixture index input=${case.input} segment=$segmentIndex")
                    val actualCandidate = actualCandidates[candidateIndex]
                    assertEquals(expectedCandidate.key, actualCandidate.key, "candidate key input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.value, actualCandidate.value, "candidate value input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.contentKey, actualCandidate.contentKey, "contentKey input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.contentValue, actualCandidate.contentValue, "contentValue input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.lid, actualCandidate.lid, "lid input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.rid, actualCandidate.rid, "rid input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.wcost, actualCandidate.wcost, "wcost input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.cost, actualCandidate.cost, "cost input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.structureCost, actualCandidate.structureCost, "structureCost input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.attributes, Attribute.namesOf(actualCandidate.attributes), "attributes input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.consumedKeySize, actualCandidate.consumedKeySize, "consumedKeySize input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(
                        expectedCandidate.innerSegments,
                        actualCandidate.innerSegments.mapIndexed { innerIndex, inner ->
                            GoldenInnerSegment(
                                index = innerIndex,
                                key = inner.key,
                                value = inner.value,
                                contentKey = inner.contentKey,
                                contentValue = inner.contentValue,
                            )
                        },
                        "innerSegments input=${case.input} segment=$segmentIndex candidate=$candidateIndex",
                    )
                }
            }

            val actualBestPath = buildList {
                var node = lattice.bosNode().next
                while (node != null && node.nodeType != mozc_runtime.converter.Node.NodeType.EOS_NODE) {
                    add(
                        GoldenBestPathNode(
                            key = node.key,
                            value = node.value,
                            lid = node.lid,
                            rid = node.rid,
                            wcost = node.wcost,
                            cost = node.cost,
                        ),
                    )
                    node = node.next
                }
            }
            assertEquals(case.bestPathNodes, actualBestPath, "best path input=${case.input}")
        }
    }
}
