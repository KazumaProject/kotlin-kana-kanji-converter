import dictionary.BuildDictionary
import louds.LOUDS
import louds.louds_with_term_id.LOUDSWithTermId
import succinctBitVector.SuccinctBitVector
import tokenArray.TokenArray
import java.io.File
import java.io.ObjectInputStream
import java.nio.file.Files
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class LegacyDictionaryBuilderTest {
    @Test
    fun reproducesTheFourV23ReleasePayloads() {
        val source = File("data/1-grams_score_cost_pos_combined_with_ner.zip")
        val rows = BuildDictionary.loadDictionaryFromZip(source)
        assertEquals(100074, rows.size)
        assertTrue(rows.any { it.reading == "i" && it.word == "I" && it.cost.toInt() == 700 })
        assertTrue(rows.any { it.reading == "dont" && it.word == "don't" && it.cost.toInt() == 900 })
        assertFalse(rows.any { it.reading == "a" })
        val output = Files.createTempDirectory("english-ime-v23").toFile()
        try {
            buildLegacyDictionary(source, output)
            val expected = mapOf(
                "reading.dat" to "07abb50547414c62035e293ec1389a09ad4718c296f486bf338fac6472dc07a1",
                "word.dat" to "7d726e5d1e8ff8f84f87299a83c456daed9aac86640cbb1c561db44170c52439",
                "token.dat" to "288363a562769da07d280f4e4c9dfc857223983149bbee2ddf344d0e74830dc2",
                "qwerty_glide_index.dat" to "7360f6b37521f606a14c235c6b115072fe3bce695dc946e917978c8cbb12dea5",
            )
            for ((name, digest) in expected) {
                assertEquals(digest, MessageDigest.getInstance("SHA-256")
                    .digest(output.resolve(name).readBytes()).joinToString("") { "%02x".format(it) }, name)
            }

            val readings = output.read("reading.dat") { LOUDSWithTermId().readExternalNotCompress(it) }
            val words = output.read("word.dat") { LOUDS().readExternalNotCompress(it) }
            val tokens = TokenArray().also { array -> output.read("token.dat") { array.readExternal(it) } }
            val readingIndex = SuccinctBitVector(readings.LBS)
            val leafIndex = SuccinctBitVector(readings.isLeaf)
            val wordIndex = SuccinctBitVector(words.LBS)
            val tokenIndex = SuccinctBitVector(tokens.bitvector)
            fun candidates(input: String): List<Pair<String, Int>> {
                val node = readings.getNodeIndex(input, readingIndex)
                if (node < 0 || !readings.isLeaf[node]) return emptyList()
                val term = readings.getTermId(node, leafIndex)
                return tokens.getListDictionaryByYomiTermId(term, tokenIndex).map {
                    (if (it.nodeId == -1) input else words.getLetter(it.nodeId, wordIndex)) to it.wordCost.toInt()
                }
            }
            assertEquals(102050, tokens.wordCostList.size)
            assertEquals(101104, readings.isLeaf.cardinality())
            assertEquals(emptyList(), candidates("a"))
            assertEquals(listOf("i" to 700), candidates("i"))
            assertEquals(listOf("dont" to 900), candidates("dont"))
            assertEquals(listOf("iOS" to 1500), candidates("ios"))
        } finally {
            output.deleteRecursively()
        }
    }

    private fun <T> File.read(name: String, block: (ObjectInputStream) -> T): T =
        ObjectInputStream(resolve(name).inputStream().buffered()).use(block)
}
