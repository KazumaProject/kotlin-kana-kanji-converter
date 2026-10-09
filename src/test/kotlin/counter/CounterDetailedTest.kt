package com.kazumaproject.counter

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.PrintStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32
import kotlin.io.path.createTempDirectory
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertFails
import kotlin.test.assertTrue

/** Independent reading fixtures: no production parser, TSV rules or formatter generates expectations. */
class CounterDetailedTest {
    private val directory = File("src/main/counter")
    private fun converter() = CounterDictionary.read(CounterDictionary.compile(CounterSourceParser.parse(directory))).converter()

    private val digits = arrayOf("", "いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう")
    private val hundreds = arrayOf("", "ひゃく", "にひゃく", "さんびゃく", "よんひゃく", "ごひゃく", "ろっぴゃく", "ななひゃく", "はっぴゃく", "きゅうひゃく")
    private val thousands = arrayOf("", "せん", "にせん", "さんぜん", "よんせん", "ごせん", "ろくせん", "ななせん", "はっせん", "きゅうせん")
    private fun group(value: Int): String = thousands[value / 1000] + hundreds[value / 100 % 10] +
        (if (value / 10 % 10 == 0) "" else (if (value / 10 % 10 == 1) "" else digits[value / 10 % 10]) + "じゅう") + digits[value % 10]

    private fun reading(value: Long): String {
        if (value == 0L) return "れい"
        val groups = mutableListOf<Int>()
        var remaining = value
        while (remaining > 0) { groups += (remaining % 10000).toInt(); remaining /= 10000 }
        val names = arrayOf("", "まん", "おく", "ちょう", "けい")
        return buildString {
            for (index in groups.indices.reversed()) {
                if (groups[index] == 0) continue
                var text = group(groups[index])
                // Established large-scale pronunciations, separate from dictionary number parts.
                if (index >= 3) {
                    val replacements = if (index == 4) listOf("ひゃく" to "ひゃっ", "びゃく" to "びゃっ", "ぴゃく" to "ぴゃっ", "ろく" to "ろっ", "じゅう" to "じゅっ", "いち" to "いっ", "はち" to "はっ")
                    else listOf("じゅう" to "じゅっ", "いち" to "いっ", "はち" to "はっ")
                    replacements.firstOrNull { text.endsWith(it.first) }?.let { text = text.dropLast(it.first.length) + it.second }
                }
                append(text); append(names[index])
            }
        }
    }
    private fun hour(value: Int): String = when (value % 10) {
        4 -> group(value - 4) + "よ"; 7 -> group(value - 7) + "しち"; 9 -> group(value - 9) + "く"
        else -> if (value == 0) "れい" else group(value)
    } + "じ"
    private fun minute(value: Int): String {
        if (value == 0) return "れいふん"
        if (value % 10 == 0) return group(value).dropLast(3) + "じゅっぷん"
        val tail = arrayOf("", "いっぷん", "にふん", "さんぷん", "よんぷん", "ごふん", "ろっぷん", "ななふん", "はっぷん", "きゅうふん")
        return group(value / 10 * 10) + tail[value % 10]
    }

    @Test fun exhaustiveSmallKanaQuantitiesAndNotationOrder() {
        val converter = converter()
        for (value in 0..9999) {
            val result = converter.convert(reading(value.toLong()) + "まい")
            assertEquals(value.toLong(), result.quantities.single { it.counterId == "mai" }.number, "value=$value")
            assertEquals("${value}枚", result.candidates.first().value)
            assertEquals(listOf("ascii", "kanji", "fullwidth"), result.candidates.map { it.notation })
            val fullwidth = value.toString().map { ('０'.code + it.digitToInt()).toChar() }.joinToString("") + "枚"
            assertEquals(fullwidth, result.candidates.last().value)
        }
    }

    @Test fun largeKanaQuantitiesAcrossScalesAndDeterministicRandomValues() {
        val converter = converter()
        val random = Random(20261009)
        val values = linkedSetOf(0L, Long.MAX_VALUE, Long.MAX_VALUE - 1)
        for (scale in listOf(10000L, 100000000L, 1000000000000L, 10000000000000000L)) {
            for (factor in listOf(1L, 6L, 8L, 10L, 20L, 100L, 300L, 600L)) {
                val value = scale * factor
                values += value - 1; values += value; values += value + 1
            }
        }
        repeat(2000) { values += random.nextLong(0, Long.MAX_VALUE) }
        for (value in values) {
            val input = reading(value) + "まい"
            val result = converter.convert(input)
            assertEquals(value, result.quantities.singleOrNull { it.counterId == "mai" }?.number, "$value: $input")
            assertEquals("${value}枚", result.candidates.first().value)
        }
    }

    @Test fun exhaustiveKanaClockWithSeconds() {
        val converter = converter()
        for (h in 0..23) for (m in 0..59) for (s in 0..59) {
            val input = hour(h) + minute(m) + reading(s.toLong()) + "びょう"
            val result = converter.convert(input)
            assertEquals(h, result.time?.hour, input)
            assertEquals(m, result.time?.minute, input)
            assertEquals(s, result.time?.second, input)
            val clock = h.toString().padStart(2, '0') + ":" + m.toString().padStart(2, '0') + ":" + s.toString().padStart(2, '0')
            assertEquals(clock, result.candidates.last().value, input)
        }
    }

    @Test fun periodsHalfHoursAndInvalidTimeComponents() {
        val converter = converter()
        for ((prefix, adjustment) in listOf("ごぜん" to 0, "ごご" to 12)) for (h in 0..12) for (s in 0..59) {
            val input = prefix + hour(h) + "はん" + reading(s.toLong()) + "びょう"
            val result = converter.convert(input)
            assertEquals(h % 12 + adjustment, result.time?.hour, input)
            assertEquals(30, result.time?.minute, input)
            assertEquals(s, result.time?.second, input)
            assertEquals(true, result.time?.half, input)
        }
        for (input in listOf("24じ", "25じ", "ごぜん13じ", "ごご23じ", "3じ60ふん", "3じ59ふん60びょう", "3じはん60びょう", "3じはん15ふん", "3じ15ふんはん", "3じ-1ふん")) {
            assertEquals(null, converter.convert(input).time, input)
        }
    }

    @Test fun exhaustiveNativeHPBReadingsAndEightAlternatives() {
        val converter = converter()
        for ((stem, voiced, semi, id, surface) in listOf(
            listOf("ほん", "ぼん", "ぽん", "hon", "本"),
            listOf("ひき", "びき", "ぴき", "hiki", "匹"),
            listOf("はい", "ばい", "ぱい", "hai", "杯"),
        )) for (value in 0..9999) {
            val text = reading(value.toLong())
            val input = when {
                value == 0 -> text + stem
                value % 1000 == 0 -> text + voiced
                value % 100 == 0 -> text.dropLast(1) + "っ" + semi
                value % 10 == 0 -> text.dropLast(3) + "じゅっ" + semi
                value % 10 == 1 -> text.dropLast(2) + "いっ" + semi
                value % 10 == 3 -> text + voiced
                value % 10 == 6 -> text.dropLast(2) + "ろっ" + semi
                value % 10 == 8 -> text.dropLast(2) + "はっ" + semi
                else -> text + stem
            }
            val result = converter.convert(input)
            assertTrue(result.quantities.any { it.counterId == id && it.number == value.toLong() }, input)
            assertTrue(result.candidates.any { it.value == "$value$surface" }, input)
            if (value % 10 == 8) assertTrue(converter.convert(text + stem).quantities.any { it.counterId == id && it.number == value.toLong() }, text + stem)
        }
    }

    @Test fun decimalRangeChecksForEveryRegularCounterAndAlias() {
        val converter = converter()
        val aliases = directory.resolve("surfaces.tsv").readLines().drop(1).filter { it.isNotBlank() && !it.startsWith('#') }.map { it.split('\t') }
        for (line in directory.resolve("counters.tsv").readLines().drop(1).filter { it.isNotBlank() && !it.startsWith('#') }) {
            val row = line.split('\t')
            if (row[5] == "EXCEPTION_ONLY") continue
            val min = row[7].toLong(); val max = if (row[8] == "*") Long.MAX_VALUE else row[8].toLong()
            val values = setOf(0L, 1L, 2L, 4L, 8L, 10L, 101L, 123L, 1000L, 10000L, min, max, max - 1)
            for (value in values) {
                val input = "$value${row[2]}"
                val result = converter.convert(input)
                val matched = result.quantities.any { it.counterId == row[0] && it.number == value }
                assertEquals(value in min..max, matched, "${row[0]}: $input")
                if (matched) {
                    assertTrue(result.candidates.any { it.value == "$value${row[1]}" }, input)
                    for (alias in aliases.filter { it[0] == row[0] }) assertTrue(result.candidates.any { it.value == "$value${alias[1]}" }, "$input: ${alias[1]}")
                    val plain = converter.convert(input, includeAliases = false)
                    assertTrue(plain.candidates.any { it.value == "$value${row[1]}" }, input)
                }
            }
            if (max < Long.MAX_VALUE) assertFalse(converter.convert("${max + 1}${row[2]}").quantities.any { it.counterId == row[0] })
            assertFalse(converter.convert("9223372036854775808${row[2]}").quantities.any { it.counterId == row[0] })
        }
    }

    @Test fun exactInputRejectionsNormalizationAndCandidateLimits() {
        val converter = converter()
        for (input in listOf("", " ", "いっぽん ", " いっぽん", "いっぽんです", "-1まい", "+1まい", "1.5まい", "1,000まい", "いちにまい", "じゅうじゅうまい", "おくまんおくまい", "いっちょういっちょうまい", "いちぜろまい", "いっぽん\n")) assertTrue(converter.convert(input).candidates.isEmpty(), input)
        assertEquals(converter.convert("123ほん").candidates, converter.convert("１２３ホン").candidates)
        assertEquals(converter.convert("いっぽん").candidates, converter.convert("イッポン").candidates)
        for (input in listOf("いっかげつ", "さんじ", "ごごさんじはん", "さんばい", "いちめーとる")) {
            val all = converter.convert(input).candidates
            assertEquals(all.size, all.map { it.value }.distinct().size, input)
            for (limit in 0..all.size + 1) assertEquals(all.take(limit), converter.convert(input, limit = limit).candidates, "$input: limit=$limit")
        }
    }

    @Test fun everyDeclaredExceptionSurvivesBinaryRoundTrip() {
        val converter = converter()
        val surfaces = directory.resolve("counters.tsv").readLines().drop(1).filter { it.isNotBlank() && !it.startsWith('#') }
            .map { it.split('\t') }.associate { it[0] to it[1] }
        for (line in directory.resolve("exceptions.tsv").readLines().drop(1).filter { it.isNotBlank() && !it.startsWith('#') }) {
            val row = line.split('\t')
            val number = row[1].toLong()
            val suffix = when (row[4]) { "@inherit" -> surfaces.getValue(row[0]); "@empty" -> ""; else -> row[4] }
            val result = converter.convert(row[2])
            assertTrue(result.quantities.any { it.counterId == row[0] && it.number == number && it.source == "exception" }, line)
            assertTrue(result.candidates.any { it.value == "$number$suffix" }, line)
        }
    }

    @Test fun shuffledSourceOrderProducesIdenticalDictionary() {
        val temporary = createTempDirectory("counter-shuffled").toFile()
        try {
            val random = Random(123)
            for (file in directory.listFiles()!!.filter { it.extension == "tsv" }) {
                val lines = file.readLines()
                temporary.resolve(file.name).writeText((listOf(lines.first()) + lines.drop(1).shuffled(random)).joinToString("\n", postfix = "\n"))
            }
            assertContentEquals(CounterDictionary.compile(CounterSourceParser.parse(directory)), CounterDictionary.compile(CounterSourceParser.parse(temporary)))
        } finally { temporary.deleteRecursively() }
    }

    @Test fun malformedBinaryWithRecomputedCrcIsRejectedStructurally() {
        val bytes = CounterDictionary.compile(CounterSourceParser.parse(directory))
        val data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        data.position(16)
        var firstStringByte = -1
        repeat(data.int) {
            val size = data.int
            if (size > 0 && firstStringByte < 0) firstStringByte = data.position()
            data.position(data.position() + size)
        }
        val records = linkedMapOf<String, Int>()
        for ((name, width) in listOf("number" to 24, "unit" to 36, "ending" to 12, "exception" to 24, "surface" to 12)) {
            val count = data.int; records[name] = data.position(); data.position(data.position() + count * width)
        }
        val arrays = linkedMapOf<String, Int>()
        repeat(3) { trie ->
            for ((name, width) in listOf("edges" to 4, "labels" to 2, "targets" to 4, "postings" to 4, "outputs" to 4)) {
                val count = data.int; arrays["$trie:$name"] = data.position(); data.position(data.position() + count * width)
            }
        }
        fun rejects(label: String, change: (ByteBuffer) -> Unit) {
            val altered = bytes.clone()
            val buffer = ByteBuffer.wrap(altered).order(ByteOrder.LITTLE_ENDIAN)
            change(buffer)
            buffer.putInt(12, CRC32().apply { update(altered, 16, altered.size - 16) }.value.toInt())
            assertFails(label) { CounterDictionary.read(altered) }
        }
        rejects("magic") { it.putInt(0, 0) }
        rejects("payload size") { it.putInt(8, bytes.size) }
        rejects("UTF-8") { it.put(firstStringByte, 0xff.toByte()) }
        rejects("number string reference") { it.putInt(records.getValue("number"), Int.MAX_VALUE) }
        rejects("number kind") { it.putInt(records.getValue("number") + 12, 99) }
        rejects("negative counter minimum") { it.putLong(records.getValue("unit") + 16, -1) }
        rejects("ending unit reference") { it.putInt(records.getValue("ending"), Int.MAX_VALUE) }
        rejects("terminal code") { it.putInt(records.getValue("ending") + 8, 99) }
        rejects("exception mode") { it.putInt(records.getValue("exception") + 16, 99) }
        rejects("surface priority") { it.putInt(records.getValue("surface") + 8, 0) }
        for (trie in 0..2) {
            rejects("$trie: edge offset") { it.putInt(arrays.getValue("$trie:edges"), -1) }
            rejects("$trie: cyclic target") { it.putInt(arrays.getValue("$trie:targets"), 0) }
            rejects("$trie: posting offset") { it.putInt(arrays.getValue("$trie:postings"), -1) }
            rejects("$trie: output reference") { it.putInt(arrays.getValue("$trie:outputs"), Int.MAX_VALUE) }
        }
    }

    @Test fun cliGoldenMismatchAndFailedBuildPreserveExistingOutput() {
        val temporary = createTempDirectory("counter-cli").toFile()
        val originalOut = System.out; val originalError = System.err
        try {
            System.setOut(PrintStream(ByteArrayOutputStream())); System.setErr(PrintStream(ByteArrayOutputStream()))
            val dictionary = temporary.resolve("dictionary.dat")
            dictionary.writeBytes(CounterDictionary.compile(CounterSourceParser.parse(directory)))
            val badCases = temporary.resolve("cases.tsv")
            badCases.writeText("input\tcounter_id\tascii\tkanji\tfullwidth\tclock\nいっぽん\thon\t2本\t二本\t２本\t\n")
            assertEquals(1, CounterCli.run(listOf("check", "--dictionary", dictionary.path, "--cases", badCases.path)))
            val before = dictionary.readBytes()
            assertFailsWith<IllegalArgumentException> { CounterCli.run(listOf("build", "--source", directory.path, "--dictionary", dictionary.path, "--cases", badCases.path)) }
            assertContentEquals(before, dictionary.readBytes())
        } finally { System.setOut(originalOut); System.setErr(originalError); temporary.deleteRecursively() }
    }
}
