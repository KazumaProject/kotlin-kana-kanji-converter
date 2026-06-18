package mozc_runtime.converter

// Ported from mozc/src/converter/inner_segment.h
data class InnerSegment(
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
)

// Ported from mozc/src/converter/inner_segment.h
object InnerSegmentBoundary {
    fun encodeLengths(
        keyLength: Int,
        valueLength: Int,
        contentKeyLength: Int,
        contentValueLength: Int,
    ): Int? {
        val fixedContentKeyLength = contentKeyLength.takeIf { it in 1..keyLength } ?: keyLength
        val fixedContentValueLength = contentValueLength.takeIf { it in 1..valueLength } ?: valueLength
        if (
            keyLength !in 1..UByte.MAX_VALUE.toInt() ||
            valueLength !in 1..UByte.MAX_VALUE.toInt() ||
            fixedContentKeyLength !in 1..UByte.MAX_VALUE.toInt() ||
            fixedContentValueLength !in 1..UByte.MAX_VALUE.toInt()
        ) {
            return null
        }
        return keyLength or
            (valueLength shl 8) or
            (fixedContentKeyLength shl 16) or
            (fixedContentValueLength shl 24)
    }

    fun decodeLengths(encoded: Int): Lengths =
        Lengths(
            keyLength = encoded and 0xff,
            valueLength = (encoded ushr 8) and 0xff,
            contentKeyLength = (encoded ushr 16) and 0xff,
            contentValueLength = (encoded ushr 24) and 0xff,
        )

    data class Lengths(
        val keyLength: Int,
        val valueLength: Int,
        val contentKeyLength: Int,
        val contentValueLength: Int,
    )
}
