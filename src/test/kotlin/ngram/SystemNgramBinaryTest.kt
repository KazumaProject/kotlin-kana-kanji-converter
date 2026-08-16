package com.kazumaproject.ngram

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SystemNgramBinaryTest {
    @Test
    fun deterministicScorelessBinaryBuild() {
        val root = File(System.getProperty("user.dir"))
        val rules = NgramSourceParser.parseDirectory(root.resolve("src/main/ngram"))
        assertTrue(rules.all { rule -> rule.features.size in 2..5 })
        val temp = createTempDirectory("ngram-binary").toFile()
        val first = temp.resolve("first.dat")
        val second = temp.resolve("second.dat")
        SystemNgramBinaryBuilder.build(rules, root.resolve("src/main/resources/id.def"), first)
        SystemNgramBinaryBuilder.build(rules.reversed(), root.resolve("src/main/resources/id.def"), second)
        assertContentEquals(first.readBytes(), second.readBytes())
        assertTrue(first.length() > NgramEncoding.HEADER_SIZE)
    }

    @Test
    fun sourceRejectsScores() {
        val file = createTempDirectory("ngram-source").resolve("bad.ngram").toFile()
        file.writeText("\"服\" + \"を\" + \"着る\" score=1")
        assertFailsWith<IllegalArgumentException> { NgramSourceParser.parseFile(file) }
    }

    @Test
    fun sourceAcceptsSingleNodeWildcard() {
        val file = createTempDirectory("ngram-wildcard").resolve("wildcard.ngram").toFile()
        file.writeText("\"布\" + \"で\" + * + \"を\" + \"拭く\"")
        val rule = NgramSourceParser.parseFile(file).single()
        assertTrue(rule.features[2] === NgramFeature.Any)
    }

    @Test
    fun unigramSourceAcceptsOnlyLiteralWords() {
        val root = createTempDirectory("unigram-source").toFile()
        root.resolve("words.ngram").writeText("\"今日\"\n\"明日\"")

        val rules = NgramSourceParser.parseUnigramDirectory(root)

        assertEquals(listOf("今日", "明日"), rules.map { (it.features.single() as NgramFeature.Word).value })
    }

    @Test
    fun unigramSourceRejectsMultiWordAndNonWordRules() {
        val multiWordRoot = createTempDirectory("unigram-multi-word").toFile()
        multiWordRoot.resolve("bad.ngram").writeText("\"今日\" + \"は\"")
        assertFailsWith<IllegalArgumentException> {
            NgramSourceParser.parseUnigramDirectory(multiWordRoot)
        }

        val nonWordRoot = createTempDirectory("unigram-non-word").toFile()
        nonWordRoot.resolve("bad.ngram").writeText("*")
        assertFailsWith<IllegalArgumentException> {
            NgramSourceParser.parseUnigramDirectory(nonWordRoot)
        }
    }

    @Test
    fun unigramBinaryUsesOptInVersion4() {
        val root = createTempDirectory("unigram-binary").toFile()
        root.resolve("words.ngram").writeText("\"今日\"\n\"明日\"")
        val rules = NgramSourceParser.parseUnigramDirectory(root)
        val output = root.resolve("system_ngram_unigram.dat")

        val report = SystemNgramBinaryBuilder.build(
            rules = rules,
            idDef = File(System.getProperty("user.dir")).resolve("src/main/resources/id.def"),
            output = output,
            formatVersion = NgramEncoding.UNIGRAM_VERSION,
        )

        val bytes = output.readBytes()
        val version = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(4)
        assertEquals(NgramEncoding.UNIGRAM_VERSION, version)
        assertEquals(2, report.ruleCount)
        SystemNgramBinaryReader(bytes).verify()
    }

    @Test
    fun version3RejectsUnigramRules() {
        val rules = listOf(
            NgramRule(
                features = listOf(NgramFeature.Word("今日")),
                source = "test",
                lineNumber = 1,
            ),
        )

        assertFailsWith<IllegalArgumentException> {
            SystemNgramBinaryBuilder.build(
                rules = rules,
                idDef = File(System.getProperty("user.dir")).resolve("src/main/resources/id.def"),
                output = createTempDirectory("v3-unigram-rejected").resolve("out.dat").toFile(),
            )
        }
    }

    @Test
    fun wordSetFeatureExpandsIncludedWordLists() {
        val root = createTempDirectory("ngram-word-set").toFile()
        root.resolve("appliance.words").writeText("冷蔵庫\n洗濯機\n")
        root.resolve("kaitai.words").writeText("@include \"appliance.words\"\n家\n冷蔵庫\nマグロ\n")
        root.resolve("kaitai.ngram").writeText("words(\"kaitai.words\") + \"を\" + \"解体\"")

        val values = NgramSourceParser.parseDirectory(root).map { rule ->
            rule.features.joinToString("") { (it as NgramFeature.Word).value }
        }

        assertEquals(listOf("冷蔵庫を解体", "洗濯機を解体", "家を解体", "マグロを解体"), values)
    }

    @Test
    fun wordListIncludeCycleIsRejected() {
        val root = createTempDirectory("ngram-word-cycle").toFile()
        root.resolve("first.words").writeText("@include \"second.words\"")
        root.resolve("second.words").writeText("@include \"first.words\"")
        root.resolve("cycle.ngram").writeText("words(\"first.words\") + \"を\" + \"解体\"")

        val failure = assertFailsWith<IllegalArgumentException> {
            NgramSourceParser.parseDirectory(root)
        }

        assertTrue(failure.message.orEmpty().contains("Cyclic .words include"))
    }

    @Test
    fun checkedInKaitaiWordSetExpandsDirectAndIncludedTargets() {
        val root = File(System.getProperty("user.dir"))
        val rules = NgramSourceParser.parseDirectory(root.resolve("src/main/ngram"))
        val exactValues = rules.mapNotNull { rule ->
            rule.features.map { (it as? NgramFeature.Word)?.value ?: return@mapNotNull null }
        }.toSet()

        val expectedTargets = setOf("家", "バイク", "車", "家屋", "建物", "マグロ", "家具", "組織", "冷蔵庫")
        expectedTargets.forEach { target ->
            assertTrue(listOf(target, "を", "解体") in exactValues, "Missing expanded rule for $target")
        }
    }

    @Test
    fun checkedInConversionPreferenceRulesArePresent() {
        val root = File(System.getProperty("user.dir"))
        val rules = NgramSourceParser.parseDirectory(root.resolve("src/main/ngram"))
        val exactValues = rules.mapNotNull { rule ->
            rule.features.map { (it as? NgramFeature.Word)?.value ?: return@mapNotNull null }
        }.toSet()

        val expectedRules = setOf(
            listOf("で", "いう", "と"),
            listOf("いり", "ます"),
            listOf("インクジェット", "紙"),
        )
        expectedRules.forEach { expected ->
            assertTrue(expected in exactValues, "Missing conversion preference rule: $expected")
        }
    }

    @Test
    fun checkedInUnigramSourceIsAvailable() {
        val root = File(System.getProperty("user.dir"))
        val rules = NgramSourceParser.parseUnigramDirectory(root.resolve("src/main/ngram-unigram"))
        assertEquals(471, rules.size)
        assertTrue(rules.any { it.features == listOf(NgramFeature.Word("エモ散らかす")) })
        assertTrue(rules.any { it.features == listOf(NgramFeature.Word("リジェネレーション")) })
        assertTrue(rules.any { it.features == listOf(NgramFeature.Word("吸引量")) })
        assertFalse(rules.any { it.features == listOf(NgramFeature.Word("今日")) })
    }

    @Test
    fun checkedInAtokUnigramDictionaryMatchesTheUnigramSource() {
        val root = File(System.getProperty("user.dir"))
        val dictionaryLines = root.resolve("src/main/resources/atok-unigram-dictionary.txt")
            .readLines(Charsets.UTF_8)
        val dictionaryPairs = dictionaryLines
            .filter { it.isNotBlank() && !it.trimStart().startsWith("#") }
            .map { line ->
                val fields = line.split('\t', limit = 5)
                assertEquals(5, fields.size)
                fields[0] to fields[4]
            }
        val sourceRules = NgramSourceParser.parseUnigramDirectory(root.resolve("src/main/ngram-unigram"))
        val sourceSurfaces = sourceRules.map { (it.features.single() as NgramFeature.Word).value }.toSet()
        val commentedPairs = root.resolve("src/main/ngram-unigram/atok-unigram.ngram")
            .readLines(Charsets.UTF_8)
            .mapNotNull { line ->
                val comment = line.trim().removePrefix("# ")
                if (!line.trimStart().startsWith("# ") || " -> " !in comment) return@mapNotNull null
                val separator = comment.indexOf(" -> ")
                comment.substring(0, separator) to comment.substring(separator + 4)
            }

        assertEquals(471, dictionaryPairs.size)
        assertEquals(471, dictionaryPairs.toSet().size)
        assertEquals(471, commentedPairs.size)
        assertEquals(commentedPairs.toSet(), dictionaryPairs.toSet())
        assertEquals(sourceSurfaces, dictionaryPairs.map { it.second }.toSet())
    }

    @Test
    fun checkedInAtokArchiveNgramSourceIsAvailable() {
        val root = File(System.getProperty("user.dir"))
        val rules = NgramSourceParser.parseFile(root.resolve("src/main/ngram/atok-2026-08-06.ngram"))

        assertEquals(35, rules.size)
        assertTrue(rules.all { it.features.size in 2..5 })
        assertTrue(
            rules.any {
                it.features == listOf(NgramFeature.Word("今"), NgramFeature.Word("離席中です"))
            },
        )
        assertTrue(
            rules.any {
                it.features == listOf(
                    NgramFeature.Word("立って"),
                    NgramFeature.Word("半畳"),
                    NgramFeature.Word("寝て"),
                    NgramFeature.Word("一畳"),
                )
            },
        )
    }
}
