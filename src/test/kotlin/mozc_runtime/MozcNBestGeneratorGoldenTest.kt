package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.BoundaryCheckMode
import mozc_runtime.converter.CandidateMode
import mozc_runtime.converter.Connector
import mozc_runtime.converter.ConversionOptions
import mozc_runtime.converter.ImmutableConverter
import mozc_runtime.converter.Lattice
import mozc_runtime.converter.NBestGenerator
import mozc_runtime.converter.NBestOptions
import mozc_runtime.converter.Node
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segmenter
import mozc_runtime.converter.Segments
import mozc_runtime.dictionary.DictionaryImpl
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import mozc_runtime.dictionary.UserDictionary
import mozc_runtime.dictionary.system.SystemDictionary
import mozc_runtime.dictionary.system.ValueDictionary
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class MozcNBestGeneratorGoldenTest {
    @Test
    fun candidateOrderAndInnerSegmentsMatchOfficialMozc() {
        val runtime = RuntimeParts()
        val fixture = MozcDictionaryGoldenSupport.readNBestGeneratorFixture(
            MozcGoldenTestSupport.fixture("converter/nbest_generator.json"),
        )

        assertEquals("24.11.oss", fixture.engineDataVersion)
        fixture.cases.forEach { case ->
            assertEquals("CONVERSION", case.requestType, "requestType input=${case.input}")
            val options = ConversionOptions(
                requestType = RequestType.CONVERSION,
                maxConversionCandidatesSize = case.segments.maxOf { it.candidates.size },
            )
            val segments = Segments()
            segments.initForConvert(case.input)
            val lattice = Lattice()
            assertTrue(runtime.converter.makeLattice(options, segments, lattice), "makeLattice failed input=${case.input}")
            assertTrue(runtime.converter.viterbi(segments, lattice), "viterbi failed input=${case.input}")

            val actualSegments = buildNBestSegments(
                options = options,
                originalKey = case.input,
                lattice = lattice,
                segmenter = runtime.segmenter,
                connector = runtime.connector,
                posMatcher = runtime.posMatcher,
                expectedSegments = case.segments,
            )

            assertEquals(case.segments.size, actualSegments.size, "segment count input=${case.input}")
            case.segments.forEachIndexed { segmentIndex, expectedSegment ->
                assertEquals(segmentIndex, expectedSegment.index, "segment fixture index input=${case.input}")
                val actualSegment = actualSegments[segmentIndex]
                assertEquals(expectedSegment.key, actualSegment.key(), "segment key input=${case.input} segment=$segmentIndex")
                assertEquals(
                    expectedSegment.candidates.size,
                    actualSegment.candidatesSize(),
                    "candidate count input=${case.input} segment=$segmentIndex actual=${
                        actualSegment.candidates().map { "${it.key}/${it.value}/${it.cost}/${it.wcost}/${it.structureCost}/${it.lid}/${it.rid}/${Attribute.namesOf(it.attributes)}" }
                    }",
                )
                expectedSegment.candidates.forEachIndexed { candidateIndex, expectedCandidate ->
                    assertEquals(candidateIndex, expectedCandidate.index, "candidate fixture index input=${case.input}")
                    val actualCandidate = actualSegment.candidate(candidateIndex)
                    assertEquals(expectedCandidate.key, actualCandidate.key, "candidate key input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.value, actualCandidate.value, "candidate value input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.contentKey, actualCandidate.contentKey, "contentKey input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.contentValue, actualCandidate.contentValue, "contentValue input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.lid, actualCandidate.lid, "lid input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.rid, actualCandidate.rid, "rid input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.cost, actualCandidate.cost, "cost input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.wcost, actualCandidate.wcost, "wcost input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.structureCost, actualCandidate.structureCost, "structureCost input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
                    assertEquals(expectedCandidate.attributes, Attribute.namesOf(actualCandidate.attributes), "attributes input=${case.input} segment=$segmentIndex candidate=$candidateIndex")
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
        }
    }

    private fun buildNBestSegments(
        options: ConversionOptions,
        originalKey: String,
        lattice: Lattice,
        segmenter: Segmenter,
        connector: Connector,
        posMatcher: PosMatcher,
        expectedSegments: List<GoldenConverterSegment>,
    ): List<Segment> {
        val result = ArrayList<Segment>()
        val nbestGenerator = NBestGenerator(segmenter, connector, posMatcher, lattice)
        var prev = lattice.bosNode()
        var beginPos: Int? = null
        var node = lattice.bosNode().next
        while (node != null && node.next != null) {
            if (beginPos == null) {
                beginPos = node.beginPos
            }
            if (!isSegmentEndNode(segmenter, node)) {
                node = node.next
                continue
            }
            val index = result.size
            val segment = Segment()
            segment.setKey(lattice.key().substringByUtf8(beginPos, node.endPos))
            val expected = expectedSegments[index]
            val nbestOptions = NBestOptions(
                boundaryCheckMode = BoundaryCheckMode.STRICT,
                candidateModes = if (expected.candidates.any { it.innerSegments.isNotEmpty() }) {
                    setOf(CandidateMode.FILL_INNER_SEGMENT_INFO)
                } else {
                    emptySet()
                },
            )
            nbestGenerator.reset(prev, node.next ?: lattice.eosNode(), nbestOptions)
            nbestGenerator.setCandidates(options, originalKey, expected.candidates.size, segment)
            insertDummyCandidates(segment, expected.candidates.size)
            result += segment
            prev = node
            beginPos = null
            node = node.next
        }
        return result
    }

    private fun isSegmentEndNode(segmenter: Segmenter, node: Node): Boolean {
        val next = node.next ?: return true
        if (next.nodeType == Node.NodeType.EOS_NODE) {
            return true
        }
        return segmenter.isBoundary(node, next, false)
    }

    private fun insertDummyCandidates(segment: Segment, expandSize: Int) {
        val lastCandidate = if (segment.candidatesSize() > 0) segment.candidate(segment.candidatesSize() - 1) else null
        if (segment.candidatesSize() == 0 ||
            (segment.candidatesSize() < expandSize && isHiragana(segment.key()))
        ) {
            val candidate = segment.addCandidate()
            if (lastCandidate != null) {
                candidate.copyFrom(lastCandidate)
            }
            candidate.key = segment.key()
            candidate.value = segment.key()
            candidate.contentKey = segment.key()
            candidate.contentValue = segment.key()
            if (lastCandidate != null) {
                candidate.cost = lastCandidate.cost + 1
                candidate.wcost = lastCandidate.wcost + 1
                candidate.structureCost = lastCandidate.structureCost + 1
            }
            candidate.attributes = 0
            if (candidate.key.codePointCount(0, candidate.key.length) <= 1) {
                candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
            }
        }
        val katakanaValue = hiraganaToKatakana(segment.key())
        if (segment.candidatesSize() > 0 &&
            segment.candidatesSize() < expandSize &&
            isKatakana(katakanaValue)
        ) {
            val reference = segment.candidate(segment.candidatesSize() - 1)
            val candidate = segment.addCandidate()
            candidate.key = segment.key()
            candidate.value = katakanaValue
            candidate.contentKey = segment.key()
            candidate.contentValue = katakanaValue
            candidate.cost = reference.cost + 1
            candidate.wcost = reference.wcost + 1
            candidate.structureCost = reference.structureCost + 1
            candidate.lid = reference.lid
            candidate.rid = reference.rid
            if (candidate.key.codePointCount(0, candidate.key.length) <= 1) {
                candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
            }
        }
    }

    private fun isHiragana(value: String): Boolean =
        value.isNotEmpty() && value.codePoints().allMatch { it in 0x3041..0x309f || it == 0x30fc }

    private fun isKatakana(value: String): Boolean =
        value.isNotEmpty() && value.codePoints().allMatch { it in 0x30a1..0x30ff || it in 0x31f0..0x31ff || it == 0x30fc }

    private fun hiraganaToKatakana(value: String): String =
        buildString {
            value.codePoints().forEachOrdered { codePoint ->
                appendCodePoint(if (codePoint in 0x3041..0x3096) codePoint + 0x60 else codePoint)
            }
        }

    private fun String.substringByUtf8(begin: Int?, end: Int): String {
        val start = begin ?: 0
        val bytes = toByteArray(Charsets.UTF_8)
        return String(bytes, start, end - start, Charsets.UTF_8)
    }

    private class RuntimeParts {
        val posMatcher: PosMatcher
        val segmenter: Segmenter
        val connector: Connector
        val converter: ImmutableConverter

        init {
            val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
            val dataManager = MozcDataManager(dataSet.sections)
            posMatcher = PosMatcher(dataManager.posMatcherData)
            val posGroup = PosGroup(dataManager.posGroupData)
            val systemDictionary = SystemDictionary.fromMozcDataManager(dataManager)
            val dictionary = DictionaryImpl(
                systemDictionary,
                ValueDictionary(systemDictionary.valueTrie(), posMatcher.getSuggestOnlyWordId()),
                UserDictionary(listOf()),
            )
            connector = Connector(dataManager.connectorData)
            segmenter = Segmenter(dataManager, posMatcher)
            converter = ImmutableConverter(
                dictionary = dictionary,
                connector = connector,
                segmenter = segmenter,
                posMatcher = posMatcher,
                posGroup = posGroup,
                userDictionary = UserDictionary(listOf()),
            )
        }
    }
}
