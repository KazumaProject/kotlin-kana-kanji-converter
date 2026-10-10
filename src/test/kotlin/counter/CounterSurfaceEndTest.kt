package com.kazumaproject.counter

import java.io.File
import java.lang.reflect.Modifier
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.zip.CRC32
import kotlin.test.*

class CounterSurfaceEndTest {
    private val source = CounterSourceParser.parse(File("src/main/counter"))
    private fun bytes() = CounterDictionary.compile(source)
    private fun header(bytes: ByteArray): ByteArray = bytes.also {
        ByteBuffer.wrap(it).order(ByteOrder.LITTLE_ENDIAN).putInt(8, it.size - 16)
            .putInt(12, CRC32().apply { update(it, 16, it.size - 16) }.value.toInt())
    }
    private fun legacy(bytes: ByteArray) = header(bytes.copyOf(bytes.size - 8196))
    private fun expected(): Set<Char> = buildSet {
        source.units.mapNotNullTo(this) { it.surface.lastOrNull() }
        source.surfaces.mapNotNullTo(this) { it.surface.lastOrNull() }
        source.exceptions.mapNotNullTo(this) { it.suffix.lastOrNull() }
        addAll("0123456789０１２３４５６７８９〇零一二三四五六七八九十百千万億兆京半".toList())
    }

    @Test fun unchangedLegacyPayloadAndDeterministicExtension() {
        val compiled = bytes(); val old = legacy(compiled)
        assertEquals(49523, compiled.size)
        assertEquals(41327, old.size)
        assertEquals(1, ByteBuffer.wrap(compiled).order(ByteOrder.LITTLE_ENDIAN).getInt(4))
        assertEquals("7decaa2574df37bd341898f08a655afed0a7987f956ce7fef3bfa5a42f732e08",
            MessageDigest.getInstance("SHA-256").digest(old).joinToString("") { "%02x".format(it) })
        assertContentEquals(compiled, bytes())
        assertEquals(1024, ByteBuffer.wrap(compiled).order(ByteOrder.LITTLE_ENDIAN).getInt(old.size))
    }

    @Test fun everyUtf16ValueMatchesIndependentExpectedSetAndLegacyFallback() {
        val compiled = bytes(); val current = CounterDictionary.read(compiled).converter()
        val old = CounterDictionary.read(legacy(compiled)).converter(); val expected = expected()
        for (code in 0..65535) {
            val text = "prefix" + code.toChar()
            assertEquals(code.toChar() in expected, current.mayEndQuantitySurface(text), "U+${code.toString(16)}")
            assertTrue(old.mayEndQuantitySurface(text))
        }
        assertFalse(current.mayEndQuantitySurface("")); assertFalse(old.mayEndQuantitySurface(""))
        for (s in listOf("123本", "二粒", "午後3時半", "12:30", "日本", "本", "１２３本", "百二十三本"))
            assertTrue(current.mayEndQuantitySurface(s), s)
        for (s in listOf("買う", "出会う", "")) assertFalse(current.mayEndQuantitySurface(s), s)
    }

    @Test fun boundaryBitsAndFinalSurrogateUseCharRatherThanCodePoint() {
        val chars = listOf(0, 63, 64, 127, 128, 0xd800, 0xdc00, 65535).map(Int::toChar)
        // Patch only test index words: UTF-8 tables cannot represent unpaired surrogates.
        val modified = bytes()
        val data = ByteBuffer.wrap(modified).order(ByteOrder.LITTLE_ENDIAN)
        val start = modified.size - 8192
        chars.forEach { ch ->
            val offset = start + (ch.code ushr 6) * 8
            data.putLong(offset, data.getLong(offset) or (1L shl (ch.code and 63)))
        }
        val c = CounterDictionary.read(header(modified)).converter()
        chars.forEach { assertTrue(c.mayEndQuantitySurface("x$it")) }
        assertTrue(c.mayEndQuantitySurface("\ud800\udc00"))
        assertFalse(c.mayEndQuantitySurface("x\udc01"))
    }

    @Test fun conversionsAndOrderingMatchWithAndWithoutIndexAndNoCandidateIsFiltered() {
        val compiled = bytes(); val current = CounterDictionary.read(compiled).converter()
        val old = CounterDictionary.read(legacy(compiled)).converter()
        val inputs = buildSet {
            File("src/main/counter/cases.tsv").readLines().drop(1).filter { it.isNotBlank() && !it.startsWith('#') }.forEach { add(it.substringBefore('\t')) }
            source.exceptions.forEach { add(it.reading) }
            source.endings.forEach { add("123" + it.reading) }
            for (n in listOf("0", "123", "１２３", "ひゃくにじゅうさん", Long.MAX_VALUE.toString())) add(n + "まい")
            for (h in 0..23) for (m in 0..59) {
                add("${h}じ${m}ふん"); add("ごご${h}じはん")
            }
        }
        for (input in inputs) for (aliases in listOf(false, true)) for (limit in listOf(Int.MAX_VALUE, 2)) {
            val a = current.convert(input, limit = limit, includeAliases = aliases)
            assertEquals(old.convert(input, limit = limit, includeAliases = aliases), a, input)
            a.candidates.forEach { assertTrue(current.mayEndQuantitySurface(it.value), "$input -> ${it.value}") }
        }
        for (h in 0..23) for (m in 0..59) for (second in 0..59) {
            val input = "${h}じ${m}ふん${second}びょう"
            val result = current.convert(input)
            assertEquals(old.convert(input), result, input)
            result.candidates.forEach { assertTrue(current.mayEndQuantitySurface(it.value), it.value) }
        }
        assertTrue(source.exceptions.any { it.suffix.isEmpty() })
        // Cover every alternate surface independently, even if no golden case reaches that unit.
        source.surfaces.forEach { assertTrue(current.mayEndQuantitySurface("123" + it.surface)) }
        source.exceptions.forEach { assertTrue(current.mayEndQuantitySurface("123" + it.suffix)) }
    }

    @Test fun rejectsInvalidIndexStructureEvenWithCorrectCrc() {
        val compiled = bytes(); val offset = compiled.size - 8196
        for (count in listOf(0,1023,1025,-1,Int.MAX_VALUE)) {
            val altered = compiled.clone()
            ByteBuffer.wrap(altered).order(ByteOrder.LITTLE_ENDIAN).putInt(offset,count)
            assertFailsWith<IllegalArgumentException> { CounterDictionary.read(header(altered)) }
        }
        for (length in listOf(offset + 1, offset + 4, compiled.size - 8, compiled.size - 1, compiled.size + 1, compiled.size + 8))
            assertFailsWith<IllegalArgumentException> { CounterDictionary.read(header(compiled.copyOf(length))) }
        for (version in listOf(0,2,99)) {
            val altered = compiled.clone()
            ByteBuffer.wrap(altered).order(ByteOrder.LITTLE_ENDIAN).putInt(4,version)
            assertFailsWith<IllegalArgumentException> { CounterDictionary.read(altered) }
        }
        assertFailsWith<IllegalArgumentException> { CounterDictionary.read(compiled.clone().also { it[it.lastIndex]=(it.last().toInt() xor 1).toByte() }) }
        assertFailsWith<IllegalArgumentException> { CounterDictionary.read(compiled.copyOf(compiled.size-1)) }
        assertTrue(CounterDictionary.read(legacy(compiled)).converter().mayEndQuantitySurface("買う"))
    }

    @Test fun ownedPrivateArrayIsSharedAcrossConvertersAndIndependentOfInputBuffer() {
        val input = bytes(); val dictionary = CounterDictionary.read(input)
        val field = CounterDictionary::class.java.declaredFields.single { it.type == LongArray::class.java }
        assertTrue(Modifier.isPrivate(field.modifiers)); field.isAccessible = true
        val owned = field.get(dictionary)
        val converters = List(10) { dictionary.converter() }
        assertSame(owned,field.get(dictionary))
        val reference = CounterConverter::class.java.declaredFields.single { it.type == CounterDictionary::class.java }
        reference.isAccessible = true
        converters.forEach { assertSame(dictionary, reference.get(it)) }
        assertTrue(CounterConverter::class.java.declaredFields.none { it.type == LongArray::class.java && !Modifier.isStatic(it.modifiers) })
        assertTrue(CounterDictionary::class.java.methods.none { it.returnType == LongArray::class.java })
        input.fill(0)
        converters.forEach { assertTrue(it.mayEndQuantitySurface("123本")); assertFalse(it.mayEndQuantitySurface("買う")) }
    }
}
