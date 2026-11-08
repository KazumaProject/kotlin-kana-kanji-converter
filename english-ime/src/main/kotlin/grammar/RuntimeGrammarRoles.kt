package grammar

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.nio.ByteBuffer
import java.nio.file.Path
import java.util.Arrays
import java.util.zip.CRC32

internal const val RUNTIME_ROLES_FILE = "categories.erol"
private const val MAGIC = 0x45524F4C // EROL
private const val HEADER_SIZE = 40
private const val BLOCK_SIZE = 32
private const val MAX_KEY_BYTES = 1_048_576
private const val ROW_SIZE = Int.SIZE_BYTES + Short.SIZE_BYTES

/** EROL v2 front-codes sorted UTF-8 keys in independently searchable 32-key blocks. Reads v1 too. */
internal class RuntimeGrammarRoles private constructor(private val data: ByteBuffer) : GrammarRoles {
    private val version = data.getInt(4)
    private var blockKeys = IntArray(0)
    private var blockLengths = IntArray(0)
    private var maxKeyBytes = 0
    private val maskCount = data.getInt(20)
    private val rowCount = data.getInt(24)
    private val masks = data.getInt(28)
    private val rows = data.getInt(32)
    private val text = data.getInt(36)
    private val names: List<String>
    private val words: Int

    init {
        val count = data.getInt(16)
        require(count in 1..1024 && maskCount in 1..65_536 && rowCount in 1..data.capacity() / 4) { "Invalid role index counts" }
        words = (count + 63) / 64
        require(masks in HEADER_SIZE..data.capacity() && rows in masks..data.capacity() &&
            text in rows..data.capacity() && rows.toLong() == masks + maskCount.toLong() * words * Long.SIZE_BYTES &&
            text.toLong() == rows + (if (version == 1) rowCount.toLong() * ROW_SIZE + Int.SIZE_BYTES
                else ((rowCount.toLong() + BLOCK_SIZE - 1) / BLOCK_SIZE + 1) * Int.SIZE_BYTES)) { "Invalid role index sections" }
        val reader = data.duplicate().position(HEADER_SIZE).limit(masks)
        names = List(count) {
            require(reader.remaining() >= Short.SIZE_BYTES) { "Truncated category names" }
            val size = reader.short.toInt() and 0xffff
            require(size in 1..reader.remaining()) { "Invalid category name length" }
            ByteArray(size).also { reader.get(it) }.toString(Charsets.UTF_8)
        }
        require(!reader.hasRemaining() && names.toSet().size == count &&
            names.all { it.matches(CATEGORY_NAME) }) { "Invalid category names" }
        if (count % 64 != 0) {
            for (id in 0 until maskCount) {
                require(data.getLong(maskStart(id) + (words - 1) * Long.SIZE_BYTES) ushr (count % 64) == 0L) {
                    "Invalid category bit"
                }
            }
        }
        if (version == 2) validateBlocks() else {
            require(data.getInt(rows) == 0 && data.getInt(rows + rowCount * ROW_SIZE) == data.capacity() - text) {
                "Invalid role index text length"
            }
            var last = text
            for (i in 0 until rowCount) {
                val row = rows + i * ROW_SIZE
                val start = keyStart(i)
                val end = keyStart(i + 1)
                require(end in (start + 1)..data.capacity() && maskId(row) < maskCount) { "Invalid role index row" }
                if (i > 0) {
                    var prefix = 0
                    while (prefix < minOf(start - last, end - start) && data.get(last + prefix) == data.get(start + prefix)) {
                        prefix++
                    }
                    require(prefix < end - start &&
                        (prefix == start - last ||
                            java.lang.Byte.compareUnsigned(data.get(last + prefix), data.get(start + prefix)) < 0)) {
                        "Invalid or unordered role index key"
                    }
                }
                last = start
            }
        }
    }

    override fun lookup(surface: String, normalized: String): Set<String> {
        val bits = LongArray(words)
        collect(normalized, bits)
        if (surface != normalized) collect(surface, bits)
        return decodeRoles(bits, names)
    }

    private fun collect(surface: String, bits: LongArray) {
        val key = surface.toByteArray(Charsets.UTF_8)
        if (version == 2) { collectBlock(key, bits); return }
        var low = 0
        var high = rowCount - 1
        while (low <= high) {
            val mid = (low + high) ushr 1
            val start = keyStart(mid)
            val order = compareKey(data, key, start, keyStart(mid + 1) - start)
            when {
                order < 0 -> high = mid - 1
                order > 0 -> low = mid + 1
                else -> {
                    val mask = maskStart(maskId(rows + mid * ROW_SIZE))
                    for (word in bits.indices) bits[word] = bits[word] or data.getLong(mask + word * Long.SIZE_BYTES)
                    return
                }
            }
        }
    }

    private fun validateBlocks() {
        val blocks = (rowCount + BLOCK_SIZE - 1) / BLOCK_SIZE
        blockKeys = IntArray(blocks)
        blockLengths = IntArray(blocks)
        require(data.getInt(rows) == 0 && data.getInt(rows + blocks * 4) == data.capacity() - text) {
            "Invalid block directory"
        }
        var previous = ByteArray(64)
        var current = ByteArray(64)
        var previousLength = 0
        for (block in 0 until blocks) {
            val start = text + data.getInt(rows + block * 4)
            val end = text + data.getInt(rows + (block + 1) * 4)
            require(start in text until data.capacity() && end in (start + 1)..data.capacity()) { "Invalid block range" }
            val reader = data.duplicate().position(start).limit(end)
            repeat(minOf(BLOCK_SIZE, rowCount - block * BLOCK_SIZE)) { index ->
                val prefix = reader.readUnsigned()
                val suffix = reader.readUnsigned()
                require((index != 0 || prefix == 0) && prefix <= previousLength &&
                    suffix in 1..MAX_KEY_BYTES && prefix <= MAX_KEY_BYTES - suffix && reader.remaining() >= 2 &&
                    suffix <= reader.remaining() - 2) { "Invalid front-coded key" }
                val mask = reader.short.toInt() and 0xffff
                require(mask < maskCount) { "Invalid block mask" }
                if (index == 0) { blockKeys[block] = reader.position(); blockLengths[block] = suffix }
                val length = prefix + suffix
                if (current.size < length) current = ByteArray(maxOf(length, current.size * 2))
                previous.copyInto(current, 0, 0, prefix)
                reader.get(current, prefix, suffix)
                require(previousLength == 0 ||
                    Arrays.compareUnsigned(previous, 0, previousLength, current, 0, length) < 0) { "Unordered block key" }
                val swap = previous
                previous = current
                current = swap
                previousLength = length
                maxKeyBytes = maxOf(maxKeyBytes, length)
            }
            require(!reader.hasRemaining()) { "Trailing block records" }
        }
    }

    private fun collectBlock(key: ByteArray, bits: LongArray) {
        var low = 0
        var high = blockKeys.lastIndex
        while (low <= high) {
            val mid = (low + high) ushr 1
            if (compareKey(data, key, blockKeys[mid], blockLengths[mid]) < 0) high = mid - 1 else low = mid + 1
        }
        if (high < 0) return
        val reader = data.duplicate().position(text + data.getInt(rows + high * 4))
        val decoded = ByteArray(maxKeyBytes)
        repeat(minOf(BLOCK_SIZE, rowCount - high * BLOCK_SIZE)) {
            val prefix = reader.readUnsigned()
            val suffix = reader.readUnsigned()
            val mask = reader.short.toInt() and 0xffff
            reader.get(decoded, prefix, suffix)
            val order = Arrays.compareUnsigned(key, 0, key.size, decoded, 0, prefix + suffix)
            if (order == 0) {
                val start = maskStart(mask)
                for (word in bits.indices) bits[word] = bits[word] or data.getLong(start + word * 8)
                return
            }
            if (order < 0) return
        }
    }

    private fun keyStart(index: Int) = text + data.getInt(rows + index * ROW_SIZE)
    private fun maskId(row: Int) = data.getShort(row + Int.SIZE_BYTES).toInt() and 0xffff
    private fun maskStart(id: Int) = masks + id * words * Long.SIZE_BYTES

    companion object {
        private val CATEGORY_NAME = Regex("[a-z][a-z0-9_]*")

        fun load(path: Path, expectedHash: String): RuntimeGrammarRoles =
            readGrammarIndex(path, expectedHash, MAGIC, HEADER_SIZE, ::RuntimeGrammarRoles, setOf(1, 2))
    }
}

internal fun writeRuntimeGrammarRoles(source: CompactGrammarRoles, output: Path) {
    val entries = source.runtimeEntries()
        .map { (key, roles) -> key.toByteArray(Charsets.UTF_8) to roles }
        .sortedWith { a, b -> Arrays.compareUnsigned(a.first, b.first) }
        .toList()
    val masks = entries.map { it.second }.distinct().withIndex().associate { it.value to it.index }
    require(masks.size in 1..65_536) { "Runtime category mask count exceeds format limits" }

    val stream = ByteArrayOutputStream()
    val data = DataOutputStream(stream)
    data.write(ByteArray(HEADER_SIZE))
    source.categoryNames.forEach {
        val bytes = it.toByteArray(Charsets.UTF_8)
        require(bytes.size in 1..65_535) { "Runtime category name exceeds format limits" }
        data.writeShort(bytes.size)
        data.write(bytes)
    }
    val masksStart = stream.size()
    masks.keys.forEach { it.forEach(data::writeLong) }
    val rowsStart = stream.size()
    val records = ByteArrayOutputStream()
    val recordWriter = DataOutputStream(records)
    for (block in entries.chunked(BLOCK_SIZE)) {
        data.writeInt(records.size())
        var previous = ByteArray(0)
        for ((key, mask) in block) {
            require(key.size in 1..MAX_KEY_BYTES) { "Invalid runtime key size" }
            var prefix = 0
            while (prefix < minOf(previous.size, key.size) && previous[prefix] == key[prefix]) prefix++
            recordWriter.writeUnsigned(prefix)
            recordWriter.writeUnsigned(key.size - prefix)
            recordWriter.writeShort(masks.getValue(mask))
            recordWriter.write(key, prefix, key.size - prefix)
            previous = key
        }
    }
    data.writeInt(records.size())
    val textStart = stream.size()
    records.writeTo(stream)
    val bytes = stream.toByteArray()
    val crc = CRC32().apply { update(bytes, HEADER_SIZE, bytes.size - HEADER_SIZE) }
    ByteBuffer.wrap(bytes).apply {
        listOf(MAGIC, 2, bytes.size, crc.value.toInt(), source.categoryNames.size, masks.size, entries.size,
            masksStart, rowsStart, textStart).forEach(::putInt)
    }
    output.toFile().writeBytes(bytes)
}

private fun DataOutputStream.writeUnsigned(value: Int) {
    var remaining = value
    while (remaining >= 128) { writeByte((remaining and 127) or 128); remaining = remaining ushr 7 }
    writeByte(remaining)
}

private fun ByteBuffer.readUnsigned(): Int {
    var result = 0
    for (shift in 0..28 step 7) {
        require(hasRemaining()) { "Truncated key length" }
        val byte = get().toInt() and 255
        require(shift != 28 || byte <= 7) { "Overflowing key length" }
        result = result or ((byte and 127) shl shift)
        if (byte < 128) {
            require(shift == 0 || byte != 0) { "Noncanonical key length" }
            return result
        }
    }
    error("Invalid key length")
}
