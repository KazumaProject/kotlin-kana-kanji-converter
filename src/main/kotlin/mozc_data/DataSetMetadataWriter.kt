package mozc_data

import java.io.ByteArrayOutputStream

class DataSetMetadataWriter {
    fun write(metadata: DataSetMetadata): ByteArray {
        val out = ByteArrayOutputStream()
        metadata.entries.forEach { entry ->
            val entryBytes = writeEntry(entry)
            out.writeTag(1, WireType.LengthDelimited.id)
            out.writeVarint(entryBytes.size.toLong())
            out.write(entryBytes)
        }
        return out.toByteArray()
    }

    private fun writeEntry(entry: DataSetMetadata.Entry): ByteArray {
        require(entry.name.isNotEmpty()) { "DataSetMetadata entry name must not be empty" }
        require(entry.offset >= 0) { "DataSetMetadata entry offset must be non-negative: name=${entry.name}" }
        require(entry.size >= 0) { "DataSetMetadata entry size must be non-negative: name=${entry.name}" }
        val out = ByteArrayOutputStream()
        val nameBytes = entry.name.toByteArray(Charsets.UTF_8)
        out.writeTag(1, WireType.LengthDelimited.id)
        out.writeVarint(nameBytes.size.toLong())
        out.write(nameBytes)
        out.writeTag(2, WireType.Varint.id)
        out.writeVarint(entry.offset)
        out.writeTag(3, WireType.Varint.id)
        out.writeVarint(entry.size)
        return out.toByteArray()
    }
}

internal fun ByteArrayOutputStream.writeTag(number: Int, wireType: Int) {
    require(number > 0) { "protobuf field number must be positive" }
    writeVarint((number.toLong() shl 3) or wireType.toLong())
}

internal fun ByteArrayOutputStream.writeVarint(value: Long) {
    require(value >= 0) { "uint64 value exceeds supported range: $value" }
    var x = value
    while (x >= 0x80L) {
        write(((x and 0x7FL) or 0x80L).toInt())
        x = x ushr 7
    }
    write(x.toInt())
}
