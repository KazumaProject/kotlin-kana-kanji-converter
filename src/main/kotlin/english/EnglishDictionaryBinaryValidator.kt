package com.kazumaproject.english

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import java.io.ByteArrayInputStream
import java.io.ObjectInputStream
import java.nio.file.Files
import java.nio.file.Path
import java.util.BitSet
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

data class EnglishDictionaryBinaryValidation(
    val readingCount: Int,
    val entryCount: Int,
    val nonTerminalPrefixCount: Int,
    val maxTermId: Int,
)

/** Checks the compiled dictionary, including the token order used by the IME's exact lookup. */
object EnglishDictionaryBinaryValidator {
    fun validate(
        expected: List<Dictionary>,
        yomiPath: Path,
        tangoPath: Path,
        tokenPath: Path,
        posTablePath: Path,
    ): EnglishDictionaryBinaryValidation = validateBytes(
        expected,
        Files.readAllBytes(yomiPath),
        Files.readAllBytes(tangoPath),
        Files.readAllBytes(tokenPath),
        Files.readAllBytes(posTablePath),
    )

    /** Reads the published layout directly; unrelated release assets are checked by the packager. */
    fun validateReleaseZip(
        expected: List<Dictionary>,
        releaseZipPath: Path,
    ): EnglishDictionaryBinaryValidation = ZipFile(releaseZipPath.toFile()).use { zip ->
        fun asset(name: String): ByteArray {
            val path = "app/src/main/assets/$name"
            val entries = zip.entries().asSequence().filter { it.name == path }.toList()
            require(entries.size == 1 && !entries.single().isDirectory) {
                "English dictionary release must contain exactly one $path"
            }
            return zip.getInputStream(entries.single()).use { it.readBytes() }
        }

        fun dictionary(name: String): ByteArray =
            ZipInputStream(ByteArrayInputStream(asset("english_reading/$name.zip"))).use { inner ->
                val entry = inner.nextEntry
                require(entry != null && !entry.isDirectory && entry.name == name) {
                    "English dictionary inner ZIP must contain $name"
                }
                val bytes = inner.readBytes()
                require(bytes.isNotEmpty() && inner.nextEntry == null) {
                    "English dictionary inner ZIP must contain only a nonempty $name"
                }
                bytes
            }

        validateBytes(expected, dictionary("yomi.dat"), dictionary("tango.dat"), dictionary("token.dat"), asset("pos_table.dat"))
    }

    private fun validateBytes(
        expected: List<Dictionary>,
        yomiBytes: ByteArray,
        tangoBytes: ByteArray,
        tokenBytes: ByteArray,
        posTableBytes: ByteArray,
    ): EnglishDictionaryBinaryValidation {
        require(expected.isNotEmpty()) { "Expected English dictionary must not be empty" }
        val grouped = expected.groupBy { it.yomi }
        require(grouped.keys.none(String::isEmpty)) { "Expected English readings must not be empty" }

        val yomi = objectInput(yomiBytes).use { LOUDSWithTermId().readExternalNotCompress(it) }
        val tango = objectInput(tangoBytes).use { LOUDS().readExternalNotCompress(it) }
        // This reader mutates its receiver but returns a new, empty TokenArray.
        val tokens = TokenArray().also { receiver ->
            objectInput(tokenBytes).use { receiver.readExternalNotCompress(it) }
        }
        objectInput(posTableBytes).use {
            tokens.leftIds = (it.readObject() as ShortArray).toList()
            tokens.rightIds = (it.readObject() as ShortArray).toList()
        }
        require(tokens.leftIds.isNotEmpty() && tokens.leftIds.size == tokens.rightIds.size) {
            "English dictionary POS table has invalid column lengths"
        }
        // Count serialized postings as well, so orphan postings cannot escape per-reading checks.
        objectInput(tokenBytes).use {
            val pos = it.readObject() as ShortArray
            val costs = it.readObject() as ShortArray
            val nodes = it.readObject() as IntArray
            val bits = it.readObject() as BitSet
            require(pos.size == expected.size && costs.size == pos.size && nodes.size == pos.size && bits.cardinality() == pos.size) {
                "English dictionary posting count differs from expected entries: expected=${expected.size}, actual=${pos.size}"
            }
        }

        val registered = linkedSetOf<String>()
        var node = yomi.isLeaf.nextSetBit(0)
        while (node >= 0) {
            registered += yomi.getLetter(node)
            node = yomi.isLeaf.nextSetBit(node + 1)
        }
        require(registered == grouped.keys && registered.size == yomi.isLeaf.cardinality()) {
            "English dictionary readings differ: missing=${(grouped.keys - registered).take(5)}, extra=${(registered - grouped.keys).take(5)}"
        }
        require(yomi.termIdsSave.size == grouped.size) { "English dictionary term ID count differs from reading count" }
        val termIds = hashSetOf<Int>()
        grouped.forEach { (reading, rows) ->
            val nodeIndex = yomi.getNodeIndex(reading)
            require(nodeIndex > 0) { "Registered English reading does not resolve exactly: $reading" }
            val termId = yomi.getTermId(nodeIndex)
            require(termId in 1..Short.MAX_VALUE.toInt()) {
                "English reading term ID exceeds the IME signed Short range: reading=$reading, termId=$termId"
            }
            require(termIds.add(termId)) { "English reading term ID is duplicated: reading=$reading, termId=$termId" }
            val postings = tokens.getListDictionaryByYomiTermId(termId)
            require(postings.size == rows.size) {
                "English posting count differs for $reading: expected=${rows.size}, actual=${postings.size}"
            }
            rows.zip(postings).forEachIndexed { index, (row, posting) ->
                val pos = posting.posTableIndex.toInt()
                require(pos in tokens.leftIds.indices) { "English POS index is out of bounds: reading=$reading, index=$pos" }
                require(posting.nodeId >= 0) { "English surface must be stored explicitly: reading=$reading, nodeId=${posting.nodeId}" }
                val actual = Dictionary(reading, tokens.leftIds[pos], tokens.rightIds[pos], posting.wordCost, tango.getLetter(posting.nodeId))
                require(actual == row) {
                    "English posting differs at reading=$reading, position=$index: expected=$row, actual=$actual"
                }
            }
        }
        require(termIds == (1..grouped.size).toSet()) { "English dictionary term IDs do not cover all posting groups" }
        val nonTerminalPrefixes = grouped.keys.asSequence()
            .flatMap { reading -> (1 until reading.length).asSequence().map(reading::take) }
            .filterNot(grouped::containsKey).toSet()
        (nonTerminalPrefixes + "").forEach { prefix ->
            val nodeIndex = yomi.getNodeIndex(prefix)
            require(nodeIndex == -1 && yomi.getTermId(nodeIndex) == -1) {
                "Nonterminal English reading incorrectly resolves: $prefix"
            }
        }
        return EnglishDictionaryBinaryValidation(grouped.size, expected.size, nonTerminalPrefixes.size, termIds.max())
    }

    private fun objectInput(bytes: ByteArray): ObjectInputStream = ObjectInputStream(ByteArrayInputStream(bytes))
}
