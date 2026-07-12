package com.kazumaproject.ngram.system

import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SystemNgramDictionaryTest {
    @Test
    fun typedLouds_matchesExactAndPosPattern_withoutAdjustment() {
        val rules = listOf(
            rule(
                "cleaning.cloth-object-wipe",
                SystemNgramElement.Word("布"),
                SystemNgramElement.Word("で"),
                SystemNgramElement.Pos(SystemNgramPosClass.NOUN),
                SystemNgramElement.Word("を"),
                SystemNgramElement.Word("拭く"),
            ),
            rule(
                "clothing.wear",
                SystemNgramElement.Word("服"),
                SystemNgramElement.Word("を"),
                SystemNgramElement.Word("着る"),
            ),
        )
        val dictionary = SystemNgramDictionary.build(rules, byteArrayOf(0, SystemNgramPosClass.NOUN.binaryId.toByte()))
        val matcher = dictionary.newMatcher()

        assertTrue(
            dictionary.matches(
                listOf(
                    SystemNgramQueryToken("布"),
                    SystemNgramQueryToken("で"),
                    SystemNgramQueryToken("机", SystemNgramPosClass.NOUN),
                    SystemNgramQueryToken("を"),
                    SystemNgramQueryToken("拭く"),
                )
            )
        )
        assertTrue(
            dictionary.matches(
                listOf(
                    SystemNgramQueryToken("布"),
                    SystemNgramQueryToken("で"),
                    SystemNgramQueryToken("東京", SystemNgramPosClass.PROPER_NOUN),
                    SystemNgramQueryToken("を"),
                    SystemNgramQueryToken("拭く"),
                )
            )
        )
        assertTrue(dictionary.matches(listOf(SystemNgramQueryToken("服"), SystemNgramQueryToken("を"), SystemNgramQueryToken("着る"))))
        assertFalse(
            dictionary.matches(
                listOf(
                    SystemNgramQueryToken("布"),
                    SystemNgramQueryToken("で"),
                    SystemNgramQueryToken("速く", SystemNgramPosClass.ADVERB),
                    SystemNgramQueryToken("を"),
                    SystemNgramQueryToken("拭く"),
                )
            )
        )
        val encodedWords = intArrayOf(
            dictionary.findWordId("服"),
            dictionary.findWordId("を"),
            dictionary.findWordId("着る"),
        )
        assertTrue(matcher.matchesEncoded(encodedWords, IntArray(3)))
    }

    @Test
    fun binary_roundTripsAndRejectsCorruption() {
        val dictionary = SystemNgramDictionary.build(
            listOf(
                rule(
                    "clothing.wear",
                    SystemNgramElement.Word("服"),
                    SystemNgramElement.Word("を"),
                    SystemNgramElement.Word("着る"),
                )
            ),
            byteArrayOf(0),
        )
        val directory = Files.createTempDirectory("system-ngram-test").toFile()
        val file = directory.resolve("system_ngram.dat")
        dictionary.writeTo(file)
        val secondFile = directory.resolve("system_ngram_second.dat")
        dictionary.writeTo(secondFile)
        assertTrue(file.readBytes().contentEquals(secondFile.readBytes()))
        val loaded = SystemNgramDictionary.readFrom(file)

        assertEquals(1, loaded.ruleCount)
        assertTrue(loaded.matches(listOf(SystemNgramQueryToken("服"), SystemNgramQueryToken("を"), SystemNgramQueryToken("着る"))))

        val corrupted = file.readBytes().also { it[it.lastIndex] = (it.last() + 1).toByte() }
        val corruptedFile = directory.resolve("corrupted.dat").also { it.writeBytes(corrupted) }
        assertFailsWith<IllegalArgumentException> { SystemNgramDictionary.readFrom(corruptedFile) }
    }

    @Test
    fun sourceParser_usesReadablePatternsAndRejectsDuplicates() {
        val directory = Files.createTempDirectory("system-ngram-source").toFile()
        directory.resolve("rules.ngram").writeText(
            "# 行頭の#で無効化できます\n" +
                "服 + を + 着る\n" +
                "布 + で + [名詞] + を + 拭く\n" +
                "\"C++\" + を + 使う\n"
        )
        val parsed = SystemNgramRuleParser.parseDirectory(directory)
        assertEquals(3, parsed.size)
        assertEquals(SystemNgramElement.Pos(SystemNgramPosClass.NOUN), parsed[1].elements[2])
        assertEquals(SystemNgramElement.Word("C++"), parsed[2].elements[0])

        directory.resolve("duplicate.ngram").writeText("服 + を + 着る\n")
        assertFailsWith<IllegalArgumentException> { SystemNgramRuleParser.parseDirectory(directory) }
    }

    private fun rule(id: String, vararg elements: SystemNgramElement): SystemNgramRule = SystemNgramRule(
        elements = elements.toList(),
        sourceFile = "$id.ngram",
        sourceLine = 1,
    )
}
