package mozc_runtime.dictionary.file

import mozc_runtime.MozcDictionaryGoldenSupport
import mozc_runtime.dictionary.system.SystemDictionary
import mozc_runtime.dictionary.system.SystemDictionaryCodec
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class DictionaryFileCodecTest {
    @Test
    fun officialDictSectionContainsExpectedInternalSections() {
        val file = MozcDictionaryGoldenSupport.dictionaryFile()
        val codec = SystemDictionaryCodec()

        listOf(
            codec.sectionNameForKey(),
            codec.sectionNameForValue(),
            codec.sectionNameForTokens(),
            codec.sectionNameForPos(),
        ).forEach { sectionName ->
            val section = file.sectionOrNull(sectionName)
            assertNotNull(section, "Missing dictionary internal section: $sectionName")
            assertTrue(section.isReadOnly, "Dictionary section must be read-only: $sectionName")
            assertTrue(section.remaining() > 0, "Dictionary section must not be empty: $sectionName")
        }
    }

    @Test
    fun sectionRangesStayWithinDictionaryImage() {
        val image = MozcDictionaryGoldenSupport.dictionarySection()
        val sections = DictionaryFile(image).sections()
        sections.forEach { section ->
            assertTrue(section.offset >= 0, "section offset")
            assertTrue(section.size > 0, "section size")
            assertTrue(section.offset <= image.remaining() - section.size, "section range")
        }
    }

    @Test
    fun brokenSectionNameIsDetectedWhenSystemDictionaryRequiresSections() {
        val image = MozcDictionaryGoldenSupport.dictionarySection()
        val bytes = ByteArray(image.remaining())
        val copy = image.asReadOnlyBuffer()
        copy.position(0)
        copy.get(bytes)
        bytes[12] = (bytes[12].toInt() xor 0x40).toByte()

        val broken = DictionaryFile(java.nio.ByteBuffer.wrap(bytes))
        assertFailsWith<IllegalStateException> {
            SystemDictionary(broken)
        }
    }

    @Test
    fun brokenSectionSizeIsRejected() {
        val image = MozcDictionaryGoldenSupport.dictionarySection()
        val broken = MozcDictionaryGoldenSupport.corruptInt32LittleEndian(image, 8, Int.MAX_VALUE)

        assertFailsWith<IllegalArgumentException> {
            DictionaryFile(broken)
        }
    }

    @Test
    fun brokenFileMagicIsRejected() {
        val image = MozcDictionaryGoldenSupport.dictionarySection()
        val broken = MozcDictionaryGoldenSupport.corruptInt32LittleEndian(image, 0, 20110702)

        assertFailsWith<IllegalArgumentException> {
            DictionaryFile(broken)
        }
    }
}
