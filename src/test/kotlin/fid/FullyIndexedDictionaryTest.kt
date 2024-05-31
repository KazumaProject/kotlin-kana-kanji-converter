package fid

import com.kazumaproject.fid.FullyIndexedDictionary
import java.util.BitSet
import kotlin.test.BeforeTest
import kotlin.test.Test

class FullyIndexedDictionaryTest {

    private lateinit var fullyIndexedDictionary: FullyIndexedDictionary

    @BeforeTest
    fun setUp() {
        val bitSet = BitSet(256)
        bitSet.set(1)
        bitSet.set(3)
        bitSet.set(6)

        bitSet.set(72)
        bitSet.set(85)
        bitSet.set(99)

        bitSet.set(111)
        bitSet.set(112)
        bitSet.set(114)
        bitSet.set(127)

        bitSet.set(136)
        bitSet.set(156)

        bitSet.set(192)
        bitSet.set(192)
        fullyIndexedDictionary = FullyIndexedDictionary(bitSet)
    }

    @Test
    fun `test fully indexed dictionary`() {
        fullyIndexedDictionary.createAuxData()
        fullyIndexedDictionary.rank1(114)
    }
}