package mozc_runtime

import mozc_data.MozcDataManager
import mozc_data.MozcDataSetReader
import mozc_runtime.dictionary.Token
import mozc_runtime.dictionary.file.DictionaryFile
import mozc_runtime.dictionary.system.SystemDictionary
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.assertEquals
import kotlin.test.assertTrue

data class GoldenDictionaryFixture(
    val engineDataVersion: String,
    val queries: List<GoldenDictionaryQuery>,
)

data class GoldenDictionaryQuery(
    val query: String,
    val lookupPrefix: List<GoldenToken>,
    val lookupExact: List<GoldenToken>,
    val lookupPredictive: List<GoldenToken>,
    val lookupReverse: List<GoldenToken>,
)

data class GoldenToken(
    val key: String,
    val value: String,
    val lid: Int,
    val rid: Int,
    val cost: Int,
)

data class GoldenConnectorFixture(
    val engineDataVersion: String,
    val costs: List<GoldenConnectorCost>,
)

data class GoldenConnectorCost(
    val leftId: Int,
    val rightId: Int,
    val cost: Int,
    val order: Int,
    val label: String,
)

data class GoldenSegmenterFixture(
    val engineDataVersion: String,
    val cases: List<GoldenSegmenterCase>,
)

data class GoldenSegmenterCase(
    val input: String,
    val checks: List<GoldenSegmenterCheck>,
)

data class GoldenSegmenterCheck(
    val leftPosId: Int,
    val rightPosId: Int,
    val boundaryType: String,
    val result: Boolean,
    val order: Int,
)

data class GoldenImmutableConverterFixture(
    val engineDataVersion: String,
    val cases: List<GoldenImmutableConverterCase>,
)

data class GoldenNBestGeneratorFixture(
    val engineDataVersion: String,
    val cases: List<GoldenNBestGeneratorCase>,
)

data class GoldenNBestGeneratorCase(
    val input: String,
    val requestType: String,
    val segments: List<GoldenConverterSegment>,
)

data class GoldenCandidateFilterFixture(
    val engineDataVersion: String,
    val cases: List<GoldenCandidateFilterCase>,
)

data class GoldenCandidateFilterCase(
    val input: String,
    val beforeFilter: List<GoldenFilterCandidate>,
    val afterFilter: List<GoldenFilterCandidate>,
)

data class GoldenPredictionFixture(
    val engineDataVersion: String,
    val cases: List<GoldenPredictionCase>,
)

data class GoldenPredictionCase(
    val input: String,
    val requestType: String,
    val results: List<GoldenPredictionResult>,
)

data class GoldenZeroQueryFixture(
    val engineDataVersion: String,
    val cases: List<GoldenZeroQueryCase>,
)

data class GoldenZeroQueryCase(
    val context: String,
    val results: List<GoldenPredictionResult>,
)

data class GoldenRewriterFixture(
    val engineDataVersion: String,
    val fixedTime: String,
    val cases: List<GoldenRewriterCase>,
)

data class GoldenEngineFixture(
    val engineDataVersion: String,
    val fixedTime: String,
    val cases: List<GoldenEngineCase>,
)

data class GoldenRewriterCase(
    val input: String,
    val requestType: String,
    val beforeRewrite: List<GoldenConverterCandidate>,
    val afterRewrite: List<GoldenConverterCandidate>,
)

data class GoldenEngineCase(
    val requestType: String,
    val input: String,
    val context: String,
    val segments: List<GoldenEngineSegment>,
)

data class GoldenEngineSegment(
    val index: Int,
    val key: String,
    val candidates: List<GoldenEngineCandidate>,
)

data class GoldenEngineCandidate(
    val index: Int,
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
    val cost: Int,
    val wcost: Int,
    val structureCost: Int,
    val lid: Int,
    val rid: Int,
    val attributes: List<String>,
    val description: String,
    val category: String,
    val innerSegments: List<GoldenInnerSegment>,
    val source: String,
    val types: List<String>,
    val consumedKeySize: Int,
)

data class GoldenPredictionResult(
    val index: Int,
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
    val cost: Int,
    val wcost: Int,
    val structureCost: Int,
    val lid: Int,
    val rid: Int,
    val attributes: List<String>,
    val types: List<String>,
    val candidateSource: String,
    val consumedKeySize: Int,
)

data class GoldenFilterCandidate(
    val key: String,
    val value: String,
    val lid: Int,
    val rid: Int,
    val cost: Int,
    val attributes: List<String>,
)

data class GoldenImmutableConverterCase(
    val input: String,
    val requestType: String,
    val segments: List<GoldenConverterSegment>,
    val bestPathNodes: List<GoldenBestPathNode>,
)

data class GoldenConverterSegment(
    val index: Int,
    val key: String,
    val candidates: List<GoldenConverterCandidate>,
)

data class GoldenConverterCandidate(
    val index: Int,
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
    val cost: Int,
    val wcost: Int,
    val structureCost: Int,
    val lid: Int,
    val rid: Int,
    val attributes: List<String>,
    val consumedKeySize: Int,
    val innerSegments: List<GoldenInnerSegment>,
    val description: String,
    val category: String,
)

data class GoldenInnerSegment(
    val index: Int,
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
)

data class GoldenBestPathNode(
    val key: String,
    val value: String,
    val lid: Int,
    val rid: Int,
    val wcost: Int,
    val cost: Int,
)

object MozcDictionaryGoldenSupport {
    fun systemDictionary(): SystemDictionary {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        return SystemDictionary.fromMozcDataManager(dataManager)
    }

    fun dictionaryFile(): DictionaryFile {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        return DictionaryFile(dataManager.section("dict"))
    }

    fun dictionarySection(): ByteBuffer {
        val dataSet = MozcDataSetReader().read(MozcGoldenTestSupport.officialData())
        val dataManager = MozcDataManager(dataSet.sections)
        return dataManager.section("dict")
    }

    fun readLookupFixture(path: Path): GoldenDictionaryFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "queries")
        return GoldenDictionaryFixture(
            engineDataVersion = root.string("engineDataVersion"),
            queries = root.array("queries").map { queryValue ->
                val query = queryValue.asObject()
                query.requireKeys("query", "lookupPrefix", "lookupExact", "lookupPredictive", "lookupReverse")
                GoldenDictionaryQuery(
                    query = query.string("query"),
                    lookupPrefix = query.tokens("lookupPrefix"),
                    lookupExact = query.tokens("lookupExact"),
                    lookupPredictive = query.tokens("lookupPredictive"),
                    lookupReverse = query.tokens("lookupReverse"),
                )
            },
        )
    }

    fun readConnectorFixture(path: Path): GoldenConnectorFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "costs")
        return GoldenConnectorFixture(
            engineDataVersion = root.string("engineDataVersion"),
            costs = root.array("costs").map { costValue ->
                val cost = costValue.asObject()
                cost.requireKeys("leftId", "rightId", "cost", "order", "label")
                GoldenConnectorCost(
                    leftId = cost.int("leftId"),
                    rightId = cost.int("rightId"),
                    cost = cost.int("cost"),
                    order = cost.int("order"),
                    label = cost.string("label"),
                )
            },
        )
    }

    fun readSegmenterFixture(path: Path): GoldenSegmenterFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "cases")
        return GoldenSegmenterFixture(
            engineDataVersion = root.string("engineDataVersion"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("input", "checks")
                GoldenSegmenterCase(
                    input = case.string("input"),
                    checks = case.array("checks").map { checkValue ->
                        val check = checkValue.asObject()
                        check.requireKeys("leftPosId", "rightPosId", "boundaryType", "result", "order")
                        GoldenSegmenterCheck(
                            leftPosId = check.int("leftPosId"),
                            rightPosId = check.int("rightPosId"),
                            boundaryType = check.string("boundaryType"),
                            result = check.boolean("result"),
                            order = check.int("order"),
                        )
                    },
                )
            },
        )
    }

    fun readImmutableConverterFixture(path: Path): GoldenImmutableConverterFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "cases")
        return GoldenImmutableConverterFixture(
            engineDataVersion = root.string("engineDataVersion"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("input", "requestType", "segments", "bestPathNodes")
                GoldenImmutableConverterCase(
                    input = case.string("input"),
                    requestType = case.string("requestType"),
                    segments = case.array("segments").map { segmentValue ->
                        val segment = segmentValue.asObject()
                        segment.requireKeys("index", "key", "candidates")
                        GoldenConverterSegment(
                            index = segment.int("index"),
                            key = segment.string("key"),
                            candidates = segment.array("candidates").map { candidateValue ->
                                val candidate = candidateValue.asObject()
                                candidate.requireKeys(
                                    "index",
                                    "key",
                                    "value",
                                    "contentKey",
                                    "contentValue",
                                    "cost",
                                    "wcost",
                                    "structureCost",
                                    "lid",
                                    "rid",
                                    "attributes",
                                    "consumedKeySize",
                                    "innerSegments",
                                    "description",
                                    "category",
                                )
                                GoldenConverterCandidate(
                                    index = candidate.int("index"),
                                    key = candidate.string("key"),
                                    value = candidate.string("value"),
                                    contentKey = candidate.string("contentKey"),
                                    contentValue = candidate.string("contentValue"),
                                    cost = candidate.int("cost"),
                                    wcost = candidate.int("wcost"),
                                    structureCost = candidate.int("structureCost"),
                                    lid = candidate.int("lid"),
                                    rid = candidate.int("rid"),
                                    attributes = candidate.stringArray("attributes"),
                                    consumedKeySize = candidate.int("consumedKeySize"),
                                    innerSegments = candidate.array("innerSegments").map { innerValue ->
                                        val inner = innerValue.asObject()
                                        inner.requireKeys("index", "key", "value", "contentKey", "contentValue")
                                        GoldenInnerSegment(
                                            index = inner.int("index"),
                                            key = inner.string("key"),
                                            value = inner.string("value"),
                                            contentKey = inner.string("contentKey"),
                                            contentValue = inner.string("contentValue"),
                                        )
                                    },
                                    description = candidate.string("description"),
                                    category = candidate.string("category"),
                                )
                            },
                        )
                    },
                    bestPathNodes = case.array("bestPathNodes").map { nodeValue ->
                        val node = nodeValue.asObject()
                        node.requireKeys("key", "value", "lid", "rid", "wcost", "cost")
                        GoldenBestPathNode(
                            key = node.string("key"),
                            value = node.string("value"),
                            lid = node.int("lid"),
                            rid = node.int("rid"),
                            wcost = node.int("wcost"),
                            cost = node.int("cost"),
                        )
                    },
                )
            },
        )
    }

    fun readNBestGeneratorFixture(path: Path): GoldenNBestGeneratorFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "cases")
        return GoldenNBestGeneratorFixture(
            engineDataVersion = root.string("engineDataVersion"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("input", "requestType", "segments")
                GoldenNBestGeneratorCase(
                    input = case.string("input"),
                    requestType = case.string("requestType"),
                    segments = case.array("segments").map { segmentValue ->
                        readConverterSegment(segmentValue.asObject())
                    },
                )
            },
        )
    }

    fun readCandidateFilterFixture(path: Path): GoldenCandidateFilterFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "cases")
        return GoldenCandidateFilterFixture(
            engineDataVersion = root.string("engineDataVersion"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("input", "beforeFilter", "afterFilter")
                GoldenCandidateFilterCase(
                    input = case.string("input"),
                    beforeFilter = case.filterCandidates("beforeFilter"),
                    afterFilter = case.filterCandidates("afterFilter"),
                )
            },
        )
    }

    fun readPredictionFixture(path: Path): GoldenPredictionFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "cases")
        return GoldenPredictionFixture(
            engineDataVersion = root.string("engineDataVersion"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("input", "requestType", "results")
                GoldenPredictionCase(
                    input = case.string("input"),
                    requestType = case.string("requestType"),
                    results = case.predictionResults("results"),
                )
            },
        )
    }

    fun readZeroQueryFixture(path: Path): GoldenZeroQueryFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "cases")
        return GoldenZeroQueryFixture(
            engineDataVersion = root.string("engineDataVersion"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("context", "results")
                GoldenZeroQueryCase(
                    context = case.string("context"),
                    results = case.predictionResults("results"),
                )
            },
        )
    }

    fun readRewriterFixture(path: Path): GoldenRewriterFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "fixedTime", "cases")
        return GoldenRewriterFixture(
            engineDataVersion = root.string("engineDataVersion"),
            fixedTime = root.string("fixedTime"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("input", "requestType", "beforeRewrite", "afterRewrite")
                GoldenRewriterCase(
                    input = case.string("input"),
                    requestType = case.string("requestType"),
                    beforeRewrite = case.array("beforeRewrite").map { readConverterCandidate(it.asObject()) },
                    afterRewrite = case.array("afterRewrite").map { readConverterCandidate(it.asObject()) },
                )
            },
        )
    }

    fun readEngineFixture(path: Path): GoldenEngineFixture {
        val root = JsonParser(Files.readString(path)).parseObject()
        root.requireKeys("engineDataVersion", "fixedTime", "cases")
        return GoldenEngineFixture(
            engineDataVersion = root.string("engineDataVersion"),
            fixedTime = root.string("fixedTime"),
            cases = root.array("cases").map { caseValue ->
                val case = caseValue.asObject()
                case.requireKeys("requestType", "input", "context", "segments")
                GoldenEngineCase(
                    requestType = case.string("requestType"),
                    input = case.string("input"),
                    context = case.string("context"),
                    segments = case.array("segments").map { segmentValue ->
                        val segment = segmentValue.asObject()
                        segment.requireKeys("index", "key", "candidates")
                        GoldenEngineSegment(
                            index = segment.int("index"),
                            key = segment.string("key"),
                            candidates = segment.array("candidates").map { candidateValue ->
                                readEngineCandidate(candidateValue.asObject())
                            },
                        )
                    },
                )
            },
        )
    }

    fun collect(block: ((Token) -> Unit) -> Unit): List<GoldenToken> {
        val result = ArrayList<GoldenToken>()
        block { token ->
            result += GoldenToken(
                key = token.key,
                value = token.value,
                lid = token.lid,
                rid = token.rid,
                cost = token.cost,
            )
        }
        return result
    }

    fun assertTokenListEquals(expected: List<GoldenToken>, actual: List<GoldenToken>, label: String) {
        assertEquals(expected.size, actual.size, "$label size")
        expected.indices.forEach { index ->
            assertEquals(expected[index], actual[index], "$label token[$index]")
        }
    }

    fun corruptInt32LittleEndian(source: ByteBuffer, offset: Int, value: Int): ByteBuffer {
        val bytes = ByteArray(source.remaining())
        val copy = source.asReadOnlyBuffer()
        copy.position(0)
        copy.get(bytes)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        buffer.putInt(offset, value)
        return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    }

    private fun readConverterSegment(segment: JsonObject): GoldenConverterSegment {
        segment.requireKeys("index", "key", "candidates")
        return GoldenConverterSegment(
            index = segment.int("index"),
            key = segment.string("key"),
            candidates = segment.array("candidates").map { candidateValue ->
                readConverterCandidate(candidateValue.asObject())
            },
        )
    }

    private fun readConverterCandidate(candidate: JsonObject): GoldenConverterCandidate {
        candidate.requireContainsKeys(
            "index",
            "key",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "innerSegments",
        )
        return GoldenConverterCandidate(
            index = candidate.int("index"),
            key = candidate.string("key"),
            value = candidate.string("value"),
            contentKey = candidate.string("contentKey"),
            contentValue = candidate.string("contentValue"),
            cost = candidate.int("cost"),
            wcost = candidate.int("wcost"),
            structureCost = candidate.int("structureCost"),
            lid = candidate.int("lid"),
            rid = candidate.int("rid"),
            attributes = candidate.stringArray("attributes"),
            consumedKeySize = candidate.optionalInt("consumedKeySize") ?: 0,
            innerSegments = candidate.array("innerSegments").map { innerValue ->
                val inner = innerValue.asObject()
                inner.requireKeys("index", "key", "value", "contentKey", "contentValue")
                GoldenInnerSegment(
                    index = inner.int("index"),
                    key = inner.string("key"),
                    value = inner.string("value"),
                    contentKey = inner.string("contentKey"),
                    contentValue = inner.string("contentValue"),
                )
            },
            description = candidate.optionalString("description") ?: "",
            category = candidate.optionalString("category") ?: "DEFAULT_CATEGORY",
        )
    }

    private fun readEngineCandidate(candidate: JsonObject): GoldenEngineCandidate {
        candidate.requireKeys(
            "index",
            "key",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "description",
            "category",
            "innerSegments",
            "source",
            "types",
            "consumedKeySize",
        )
        return GoldenEngineCandidate(
            index = candidate.int("index"),
            key = candidate.string("key"),
            value = candidate.string("value"),
            contentKey = candidate.string("contentKey"),
            contentValue = candidate.string("contentValue"),
            cost = candidate.int("cost"),
            wcost = candidate.int("wcost"),
            structureCost = candidate.int("structureCost"),
            lid = candidate.int("lid"),
            rid = candidate.int("rid"),
            attributes = candidate.stringArray("attributes"),
            description = candidate.string("description"),
            category = candidate.string("category"),
            innerSegments = candidate.array("innerSegments").map { innerValue ->
                val inner = innerValue.asObject()
                inner.requireKeys("index", "key", "value", "contentKey", "contentValue")
                GoldenInnerSegment(
                    index = inner.int("index"),
                    key = inner.string("key"),
                    value = inner.string("value"),
                    contentKey = inner.string("contentKey"),
                    contentValue = inner.string("contentValue"),
                )
            },
            source = candidate.string("source"),
            types = candidate.stringArray("types"),
            consumedKeySize = candidate.int("consumedKeySize"),
        )
    }

    private fun JsonObject.tokens(name: String): List<GoldenToken> =
        array(name).map { value ->
            val token = value.asObject()
            token.requireKeys("key", "value", "lid", "rid", "cost")
            GoldenToken(
                key = token.string("key"),
                value = token.string("value"),
                lid = token.int("lid"),
                rid = token.int("rid"),
                cost = token.int("cost"),
            )
        }

    private fun JsonObject.filterCandidates(name: String): List<GoldenFilterCandidate> =
        array(name).map { value ->
            val candidate = value.asObject()
            candidate.requireKeys("key", "value", "lid", "rid", "cost", "attributes")
            GoldenFilterCandidate(
                key = candidate.string("key"),
                value = candidate.string("value"),
                lid = candidate.int("lid"),
                rid = candidate.int("rid"),
                cost = candidate.int("cost"),
                attributes = candidate.stringArray("attributes"),
            )
        }

    private fun JsonObject.predictionResults(name: String): List<GoldenPredictionResult> =
        array(name).map { value ->
            val result = value.asObject()
            result.requireKeys(
                "index",
                "key",
                "value",
                "contentKey",
                "contentValue",
                "cost",
                "wcost",
                "structureCost",
                "lid",
                "rid",
                "attributes",
                "types",
                "candidateSource",
                "consumedKeySize",
            )
            GoldenPredictionResult(
                index = result.int("index"),
                key = result.string("key"),
                value = result.string("value"),
                contentKey = result.string("contentKey"),
                contentValue = result.string("contentValue"),
                cost = result.int("cost"),
                wcost = result.int("wcost"),
                structureCost = result.int("structureCost"),
                lid = result.int("lid"),
                rid = result.int("rid"),
                attributes = result.stringArray("attributes"),
                types = result.stringArray("types"),
                candidateSource = result.string("candidateSource"),
                consumedKeySize = result.int("consumedKeySize"),
            )
        }

    private fun JsonObject.stringArray(name: String): List<String> =
        array(name).map { (it as JsonString).value }
}

private sealed interface JsonValue {
    fun asObject(): JsonObject = this as? JsonObject ?: error("Expected JSON object")
}

private class JsonObject(
    private val values: Map<String, JsonValue>,
) : JsonValue {
    fun requireKeys(vararg expected: String) {
        val expectedSet = expected.toSet()
        assertEquals(expectedSet, values.keys, "JSON object keys")
    }

    fun requireContainsKeys(vararg expected: String) {
        val missing = expected.filterNot { it in values }
        assertEquals(listOf(), missing, "JSON object missing keys")
    }

    fun string(name: String): String = (values.getValue(name) as JsonString).value

    fun optionalString(name: String): String? = (values[name] as? JsonString)?.value

    fun int(name: String): Int = (values.getValue(name) as JsonNumber).value

    fun optionalInt(name: String): Int? = (values[name] as? JsonNumber)?.value

    fun boolean(name: String): Boolean = (values.getValue(name) as JsonBoolean).value

    fun array(name: String): List<JsonValue> = (values.getValue(name) as JsonArray).values
}

private data class JsonString(val value: String) : JsonValue

private data class JsonNumber(val value: Int) : JsonValue

private data class JsonBoolean(val value: Boolean) : JsonValue

private data class JsonArray(val values: List<JsonValue>) : JsonValue

private class JsonParser(
    private val text: String,
) {
    private var index = 0

    fun parseObject(): JsonObject {
        val value = parseValue().asObject()
        skipWhitespace()
        assertTrue(index == text.length, "JSON parser stopped before the end: index=$index length=${text.length}")
        return value
    }

    private fun parseValue(): JsonValue {
        skipWhitespace()
        require(index < text.length) { "Unexpected end of JSON" }
        return when (text[index]) {
            '{' -> parseJsonObject()
            '[' -> parseArray()
            '"' -> JsonString(parseString())
            '-', in '0'..'9' -> JsonNumber(parseNumber())
            't', 'f' -> JsonBoolean(parseBoolean())
            else -> error("Unexpected JSON character at $index: ${text[index]}")
        }
    }

    private fun parseJsonObject(): JsonObject {
        expect('{')
        val map = LinkedHashMap<String, JsonValue>()
        skipWhitespace()
        if (peek('}')) {
            expect('}')
            return JsonObject(map)
        }
        while (true) {
            val key = parseString()
            skipWhitespace()
            expect(':')
            require(key !in map) { "Duplicated JSON object key: $key" }
            map[key] = parseValue()
            skipWhitespace()
            if (peek('}')) {
                expect('}')
                break
            }
            expect(',')
        }
        return JsonObject(map)
    }

    private fun parseArray(): JsonArray {
        expect('[')
        val values = ArrayList<JsonValue>()
        skipWhitespace()
        if (peek(']')) {
            expect(']')
            return JsonArray(values)
        }
        while (true) {
            values += parseValue()
            skipWhitespace()
            if (peek(']')) {
                expect(']')
                break
            }
            expect(',')
        }
        return JsonArray(values)
    }

    private fun parseString(): String {
        expect('"')
        val out = StringBuilder()
        while (index < text.length) {
            val ch = text[index++]
            when (ch) {
                '"' -> return out.toString()
                '\\' -> {
                    require(index < text.length) { "JSON escape is truncated" }
                    when (val escaped = text[index++]) {
                        '"' -> out.append('"')
                        '\\' -> out.append('\\')
                        '/' -> out.append('/')
                        'b' -> out.append('\b')
                        'f' -> out.append('\u000C')
                        'n' -> out.append('\n')
                        'r' -> out.append('\r')
                        't' -> out.append('\t')
                        'u' -> {
                            require(index + 4 <= text.length) { "JSON unicode escape is truncated" }
                            val code = text.substring(index, index + 4).toInt(16)
                            out.append(code.toChar())
                            index += 4
                        }
                        else -> error("Invalid JSON escape: $escaped")
                    }
                }
                else -> out.append(ch)
            }
        }
        error("Unterminated JSON string")
    }

    private fun parseNumber(): Int {
        val start = index
        if (text[index] == '-') {
            index += 1
        }
        require(index < text.length && text[index].isDigit()) { "Invalid JSON number at $start" }
        while (index < text.length && text[index].isDigit()) {
            index += 1
        }
        return text.substring(start, index).toInt()
    }

    private fun parseBoolean(): Boolean {
        return when {
            text.startsWith("true", index) -> {
                index += 4
                true
            }
            text.startsWith("false", index) -> {
                index += 5
                false
            }
            else -> error("Invalid JSON boolean at $index")
        }
    }

    private fun skipWhitespace() {
        while (index < text.length && text[index].isWhitespace()) {
            index += 1
        }
    }

    private fun peek(ch: Char): Boolean {
        skipWhitespace()
        return index < text.length && text[index] == ch
    }

    private fun expect(ch: Char) {
        skipWhitespace()
        require(index < text.length && text[index] == ch) {
            "Expected '$ch' at JSON offset $index"
        }
        index += 1
    }
}
