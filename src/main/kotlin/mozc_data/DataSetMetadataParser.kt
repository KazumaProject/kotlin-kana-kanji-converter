package mozc_data

data class DataSetMetadata(
    val entries: List<Entry>,
) {
    data class Entry(
        val name: String,
        val offset: Long,
        val size: Long,
    )
}

class DataSetMetadataParser {
    fun parse(bytes: ByteArray): DataSetMetadata {
        val reader = ProtoReader(bytes)
        val entries = mutableListOf<DataSetMetadata.Entry>()
        while (!reader.isAtEnd()) {
            val field = reader.readField()
            when {
                field.number == 1 && field.wireType == WireType.LengthDelimited.id -> {
                    entries += parseEntry(reader.readLengthDelimited())
                }
                else -> reader.skip(field.wireType)
            }
        }
        return DataSetMetadata(entries)
    }

    private fun parseEntry(bytes: ByteArray): DataSetMetadata.Entry {
        val reader = ProtoReader(bytes)
        var name: String? = null
        var offset: Long? = null
        var size: Long? = null
        while (!reader.isAtEnd()) {
            val field = reader.readField()
            when {
                field.number == 1 && field.wireType == WireType.LengthDelimited.id -> {
                    name = reader.readLengthDelimited().toString(Charsets.UTF_8)
                }
                field.number == 2 && field.wireType == WireType.Varint.id -> {
                    offset = reader.readVarint64AsLong()
                }
                field.number == 3 && field.wireType == WireType.Varint.id -> {
                    size = reader.readVarint64AsLong()
                }
                else -> reader.skip(field.wireType)
            }
        }
        return DataSetMetadata.Entry(
            name = requireNotNull(name) { "DataSetMetadata entry is missing name" },
            offset = requireNotNull(offset) { "DataSetMetadata entry is missing offset: name=$name" },
            size = requireNotNull(size) { "DataSetMetadata entry is missing size: name=$name" },
        )
    }
}

internal enum class WireType(val id: Int) {
    Varint(0),
    Fixed64(1),
    LengthDelimited(2),
    Fixed32(5),
}

internal data class ProtoField(val number: Int, val wireType: Int)

internal class ProtoReader(private val bytes: ByteArray) {
    private var index: Int = 0

    fun isAtEnd(): Boolean = index == bytes.size

    fun readField(): ProtoField {
        val tag = readVarint64AsLong()
        require(tag != 0L) { "Invalid protobuf tag 0 at byte offset=$index" }
        val number = (tag ushr 3).toInt()
        val wireType = (tag and 0x7L).toInt()
        require(number > 0) { "Invalid protobuf field number: $number" }
        return ProtoField(number, wireType)
    }

    fun readLengthDelimited(): ByteArray {
        val length = readVarint64AsLong().toIntExact("length-delimited size")
        require(length >= 0) { "Negative length-delimited size: $length" }
        require(index <= bytes.size - length) {
            "Length-delimited field exceeds metadata size: offset=$index length=$length metadataSize=${bytes.size}"
        }
        return bytes.copyOfRange(index, index + length).also {
            index += length
        }
    }

    fun readVarint64AsLong(): Long {
        var result = 0L
        var shift = 0
        while (shift < 64) {
            require(index < bytes.size) { "Unexpected end of protobuf varint" }
            val b = bytes[index++].toInt() and 0xFF
            result = result or ((b and 0x7F).toLong() shl shift)
            if ((b and 0x80) == 0) {
                require(result >= 0) { "uint64 value exceeds signed Long range" }
                return result
            }
            shift += 7
        }
        error("Malformed protobuf varint")
    }

    fun skip(wireType: Int) {
        when (wireType) {
            WireType.Varint.id -> readVarint64AsLong()
            WireType.Fixed64.id -> skipBytes(Long.SIZE_BYTES)
            WireType.LengthDelimited.id -> skipBytes(readVarint64AsLong().toIntExact("length-delimited skip size"))
            WireType.Fixed32.id -> skipBytes(Int.SIZE_BYTES)
            else -> error("Unsupported protobuf wire type: $wireType")
        }
    }

    private fun skipBytes(count: Int) {
        require(count >= 0) { "Negative protobuf skip size: $count" }
        require(index <= bytes.size - count) {
            "Protobuf skip exceeds metadata size: offset=$index count=$count metadataSize=${bytes.size}"
        }
        index += count
    }
}

internal fun Long.toIntExact(label: String): Int {
    require(this <= Int.MAX_VALUE) { "$label exceeds Int range: $this" }
    return toInt()
}
