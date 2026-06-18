package mozc_runtime.dictionary.file

import java.nio.ByteBuffer

// Ported from mozc/src/dictionary/file/dictionary_file.cc
// Ported from mozc/src/dictionary/file/section.h
class DictionaryFileSection(
    val encodedName: ByteArray,
    val offset: Int,
    val size: Int,
    data: ByteBuffer,
) {
    val data: ByteBuffer = data.asReadOnlyBuffer()

    init {
        require(encodedName.size == DictionaryFileCodec.FingerprintByteLength) {
            "Dictionary file section name must be ${DictionaryFileCodec.FingerprintByteLength} bytes: actual=${encodedName.size}"
        }
        require(offset >= 0) { "Dictionary file section offset is negative: $offset" }
        require(size >= 0) { "Dictionary file section size is negative: $size" }
        require(this.data.remaining() == size) {
            "Dictionary file section size mismatch: declared=$size actual=${this.data.remaining()}"
        }
    }

    fun nameHex(): String = encodedName.joinToString(separator = "") { "%02x".format(it.toInt() and 0xff) }

    fun matches(name: ByteArray): Boolean = encodedName.contentEquals(name)
}
