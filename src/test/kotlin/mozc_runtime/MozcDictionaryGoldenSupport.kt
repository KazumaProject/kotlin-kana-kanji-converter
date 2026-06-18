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

    fun string(name: String): String = (values.getValue(name) as JsonString).value

    fun int(name: String): Int = (values.getValue(name) as JsonNumber).value

    fun array(name: String): List<JsonValue> = (values.getValue(name) as JsonArray).values
}

private data class JsonString(val value: String) : JsonValue

private data class JsonNumber(val value: Int) : JsonValue

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
