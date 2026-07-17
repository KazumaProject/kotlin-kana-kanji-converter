package com.kazumaproject.ngram

import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
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
}
