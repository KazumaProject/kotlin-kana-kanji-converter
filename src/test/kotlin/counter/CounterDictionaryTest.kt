package com.kazumaproject.counter

import java.io.ByteArrayInputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.zip.CRC32
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class CounterDictionaryTest {
    private val sourceDir = File("src/main/counter")
    private fun bytes(): ByteArray = CounterDictionary.compile(CounterSourceParser.parse(sourceDir))
    private fun converter(): CounterConverter = CounterDictionary.read(bytes()).converter()

    @Test fun goldenReadingsAndRejectionsUseNewlyCompiledBinary() {
        val report = CounterCli.check(converter(), sourceDir.resolve("cases.tsv"))
        assertEquals(0, report["failed"], report.toString())
        assertTrue((report["total"] as Int) >= 80)
    }

    @Test fun deterministicCompactBuildAndStreamLoading() {
        val source = CounterSourceParser.parse(sourceDir)
        val compiled = CounterDictionary.compile(source)
        // Source file order is canonicalized by the parser; trie construction itself is independent of insertion order.
        val first = CounterTrie.build(source.endings.mapIndexed { i, e -> e.reading to i }, true)
        val second = CounterTrie.build(source.endings.mapIndexed { i, e -> e.reading to i }.reversed(), true)
        assertContentEquals(first.edges, second.edges)
        assertContentEquals(first.outputs, second.outputs)
        assertContentEquals(compiled, bytes())
        val dictionary = CounterDictionary.read(ByteArrayInputStream(compiled))
        assertTrue(dictionary.byteSize <= 65536, "Size budget exceeded: ${dictionary.byteSize}")
        assertTrue(dictionary.counterCount >= 100)
        assertTrue(dictionary.numberPartCount < 100)
        assertEquals(listOf("1本", "一本", "１本"), dictionary.converter().convert("いっぽん").candidates.map { it.value })
    }

    @Test fun arbitraryNumbersAndLongBoundaryDoNotRequireExtraEntries() {
        val converter = converter()
        for (number in listOf(0L, 101L, 123L, 2026L, 10001L, 123456789L, Long.MAX_VALUE)) {
            val result = converter.convert("${number}まい")
            assertEquals(number, result.quantities.single { it.counterId == "mai" }.number)
            assertEquals("${number}枚", result.candidates.first().value)
        }
        val maximumReading = "きゅうひゃくにじゅうにけいさんぜんさんびゃくななじゅうにちょうさんびゃくろくじゅうはちおくごせんよんひゃくななじゅうななまんごせんはっぴゃくなな"
        assertEquals(Long.MAX_VALUE, converter.convert(maximumReading + "まい").quantities.single { it.counterId == "mai" }.number)
        assertTrue(converter.convert(maximumReading.dropLast(2) + "はちまい").candidates.isEmpty())
        assertTrue(converter.convert("9223372036854775808まい").candidates.isEmpty())
        assertEquals("九百二十二京三千三百七十二兆三百六十八億五千四百七十七万五千八百七", CounterConverter.numberText(Long.MAX_VALUE, 1))
    }

    @Test fun aliasesRankingLimitAndExactExceptions() {
        val converter = converter()
        val all = converter.convert("いっかげつ").candidates.map { it.value }
        assertTrue(all.indexOf("1か月") < all.indexOf("1ヶ月"))
        assertTrue(all.indexOf("1ヶ月") < all.indexOf("一か月"))
        assertEquals(listOf("1か月", "一か月", "１か月"), converter.convert("いっかげつ", includeAliases = false).candidates.map { it.value })
        assertEquals(all.take(2), converter.convert("いっかげつ", limit = 2).candidates.map { it.value })
        assertTrue(converter.convert("いっかげつ", limit = 0).candidates.isEmpty())
        assertFailsWith<IllegalArgumentException> { converter.convert("いっかげつ", limit = -1) }
        assertTrue(converter.convert("にじゅうひとり").candidates.isEmpty())
        assertTrue(converter.convert("にじゅういちにん").candidates.any { it.value == "21人" })
        assertFalse(converter.convert("とお").candidates.any { it.value.contains("つ") })
    }

    @Test fun timeGrammarAndQuantityGrammarStayDistinct() {
        val converter = converter()
        assertEquals(15, converter.convert("ごごさんじはん").time?.hour)
        assertEquals(30, converter.convert("ごごさんじはん").time?.minute)
        assertEquals(0, converter.convert("ごぜんじゅうにじ").time?.hour)
        assertEquals(12, converter.convert("ごごじゅうにじ").time?.hour)
        assertEquals(null, converter.convert("さんじかん").time)
        assertTrue(converter.convert("さんじかん").candidates.any { it.value == "3時間" })
        assertEquals(null, converter.convert("ろくじゅっぷん").time)
        assertTrue(converter.convert("ろくじゅっぷん").candidates.any { it.value == "60分" })
        for (input in listOf("にじゅうよじ", "ごごじゅうさんじ", "さんじろくじゅっぷん", "さんじろくじゅうびょう")) assertTrue(converter.convert(input).candidates.isEmpty(), input)
        assertEquals(null, converter.convert("にじゅうごじ").time)
        assertTrue(converter.convert("にじゅうごじ").candidates.any { it.value == "25字" })
    }

    @Test fun allHourMinuteBoundariesAndInputBufferOwnership() {
        val bytes = bytes()
        val converter = CounterDictionary.read(bytes).converter()
        bytes.fill(0) // The reader retains its own tables, never the caller's buffer.
        for (hour in 0..23) for (minute in 0..59) {
            val result = converter.convert("${hour}じ${minute}ふん")
            assertEquals(hour, result.time?.hour)
            assertEquals(minute, result.time?.minute)
            assertTrue(result.candidates.any { it.value == "%02d:%02d".format(hour, minute) })
        }
        assertTrue(converter.convert("あ".repeat(129)).candidates.isEmpty())
    }

    @Test fun concurrentConversionsHaveNoMutableSharedScratch() {
        val converter = converter()
        val pool = Executors.newFixedThreadPool(4)
        try {
            val jobs = (0 until 200).map { i -> Callable { converter.convert("${i}まい").candidates.first().value } }
            assertEquals((0 until 200).map { "${it}枚" }, pool.invokeAll(jobs).map { it.get() })
        } finally { pool.shutdownNow() }
    }

    @Test fun rejectsCorruptionTruncationUnsupportedVersionsAndMalformedCounts() {
        val compiled = bytes()
        for (length in listOf(0, 4, 15, compiled.size - 1)) assertFailsWith<IllegalArgumentException> { CounterDictionary.read(compiled.copyOf(length)) }
        val corrupted = compiled.clone().also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }
        assertFailsWith<IllegalArgumentException> { CounterDictionary.read(corrupted) }
        val version = compiled.clone().also { ByteBuffer.wrap(it).order(ByteOrder.LITTLE_ENDIAN).putInt(4, 99) }
        assertFailsWith<IllegalArgumentException> { CounterDictionary.read(version) }
        val malicious = compiled.clone()
        ByteBuffer.wrap(malicious).order(ByteOrder.LITTLE_ENDIAN).putInt(16, Int.MAX_VALUE)
        ByteBuffer.wrap(malicious).order(ByteOrder.LITTLE_ENDIAN).putInt(12, CRC32().apply { update(malicious, 16, malicious.size - 16) }.value.toInt())
        assertFailsWith<IllegalArgumentException> { CounterDictionary.read(malicious) }
        assertFailsWith<IllegalArgumentException> { CounterDictionary.read(ByteArray(CounterDictionary.MAX_BYTES + 1)) }
    }

    @Test fun validatesEditableSourceReferencesRangesAndDuplicates() {
        val directory = createTempDirectory("counter-source").toFile()
        try {
            sourceDir.listFiles()!!.filter { it.extension == "tsv" }.forEach { it.copyTo(directory.resolve(it.name)) }
            val counters = directory.resolve("counters.tsv")
            val original = counters.readText()
            counters.appendText(original.lineSequence().drop(1).first() + "\n")
            assertFailsWith<IllegalArgumentException> { CounterSourceParser.parse(directory) }
            counters.writeText(original.replace("\tH_P_B\t", "\tNONEXISTENT\t"))
            assertFailsWith<IllegalArgumentException> { CounterSourceParser.parse(directory) }
            counters.writeText(original)
            directory.resolve("surfaces.tsv").appendText("missing\tm\t1\n")
            assertFailsWith<IllegalArgumentException> { CounterSourceParser.parse(directory) }
        } finally { directory.deleteRecursively() }
    }

    @Test fun cliArgumentValidationAndJsonEscaping() {
        assertFailsWith<IllegalArgumentException> { CounterCli.run(listOf("convert", "--input")) }
        assertFailsWith<IllegalStateException> { CounterCli.run(listOf("inspect", "--bogus")) }
        assertEquals("\"a\\n\\\"\\\\\\u0001\"", CounterCli.json("a\n\"\\\u0001"))
    }
}
