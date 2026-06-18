package mozc_runtime.dictionary.file

import java.nio.ByteBuffer

// Ported from mozc/src/dictionary/file/dictionary_file.cc
class DictionaryFile(
    image: ByteBuffer,
    private val codec: DictionaryFileCodec = DictionaryFileCodec(),
) {
    private val sections: List<DictionaryFileSection> = codec.readSections(image)

    fun sections(): List<DictionaryFileSection> = sections

    fun sectionOrNull(sectionName: String): ByteBuffer? {
        val encodedName = codec.getSectionName(sectionName)
        return sections.firstOrNull { it.matches(encodedName) }?.data?.asReadOnlyBuffer()
    }

    fun requireSection(sectionName: String): ByteBuffer =
        sectionOrNull(sectionName) ?: error("Missing dictionary file section: $sectionName")
}
