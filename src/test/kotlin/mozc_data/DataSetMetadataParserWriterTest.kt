package mozc_data

import kotlin.test.Test
import kotlin.test.assertEquals

class DataSetMetadataParserWriterTest {
    @Test
    fun metadataRoundTripPreservesEntryOrderAndRanges() {
        val metadata = DataSetMetadata(
            listOf(
                DataSetMetadata.Entry("dict", 8, 12),
                DataSetMetadata.Entry("version", 20, 4),
            )
        )

        val bytes = DataSetMetadataWriter().write(metadata)
        val parsed = DataSetMetadataParser().parse(bytes)

        assertEquals(metadata, parsed)
    }
}
