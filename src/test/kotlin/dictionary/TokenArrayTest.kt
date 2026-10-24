package dictionary

import com.kazumaproject.Louds.Converter
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.prefix.PrefixTree
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals

class TokenArrayTest {
    @Test
    fun readsFinalReadingWhenPostingsEndOnBitSetWordBoundary() {
        val tempDir = Files.createTempDirectory("token-array-final-reading-")
        try {
            val dictionaries = (0 until 32).map { index ->
                val suffix = index.toString().padStart(2, '0')
                Dictionary("よみ$suffix", 1, 1, index.toShort(), "語$suffix")
            }.groupBy { it.yomi }
                .mapValues { (_, values) -> values }
                .toSortedMap(compareBy({ it.length }, { it }))

            val posTablePath = tempDir.resolve("pos_table.dat")
            TokenArray().buildPOSTableWithIndex(dictionaries, 1, posTablePath.toString())

            val tangoTree = PrefixTree().apply {
                dictionaries.values.flatten().forEach { insert(it.tango) }
            }
            val tango = Converter().convert(tangoTree.root).apply { convertListToBitSet() }
            val serialized = ByteArrayOutputStream()
            ObjectOutputStream(serialized).use { output ->
                TokenArray().buildTokenArray(dictionaries, tango, output, 1, posTablePath.toString())
            }

            val tokens = TokenArray().apply {
                ObjectInputStream(ByteArrayInputStream(serialized.toByteArray())).use {
                    readExternalNotCompressStrict(it)
                }
            }

            assertEquals(32, tokens.entryCount)
            assertEquals(1, tokens.getListDictionaryByYomiTermId(32).size)
            assertEquals(31.toShort(), tokens.getListDictionaryByYomiTermId(32).single().wordCost)
        } finally {
            tempDir.toFile().deleteRecursively()
        }
    }
}
