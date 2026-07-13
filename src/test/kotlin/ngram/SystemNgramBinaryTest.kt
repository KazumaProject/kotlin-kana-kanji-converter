package com.kazumaproject.ngram

import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertContentEquals
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
}
