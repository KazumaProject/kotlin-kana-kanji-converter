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
private const val ROW_SIZE = Int.SIZE_BYTES + Short.SIZE_BYTES

/** EROL v1 stores sorted UTF-8 keys and shared masks. Non-normalized keys store only additional roles. */
internal class RuntimeGrammarRoles private constructor(private val data: ByteBuffer) : GrammarRoles {
    private val maskCount = data.getInt(20)
    private val rowCount = data.getInt(24)
    private val masks = data.getInt(28)
    private val rows = data.getInt(32)
    private val text = data.getInt(36)
    private val names: List<String>
    private val words: Int

    init {
        val count = data.getInt(16)
        require(count in 1..1024 && maskCount in 1..65_536 && rowCount > 0) { "Invalid role index counts" }
        words = (count + 63) / 64
        require(masks in HEADER_SIZE..data.capacity() && rows in masks..data.capacity() &&
            text in rows..data.capacity() && rows.toLong() == masks + maskCount.toLong() * words * Long.SIZE_BYTES &&
            text.toLong() == rows + rowCount.toLong() * ROW_SIZE + Int.SIZE_BYTES) { "Invalid role index sections" }
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

    override fun lookup(surface: String, normalized: String): Set<String> {
        val bits = LongArray(words)
        collect(normalized, bits)
        if (surface != normalized) collect(surface, bits)
        return decodeRoles(bits, names)
    }

    private fun collect(surface: String, bits: LongArray) {
        val key = surface.toByteArray(Charsets.UTF_8)
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

    private fun keyStart(index: Int) = text + data.getInt(rows + index * ROW_SIZE)
    private fun maskId(row: Int) = data.getShort(row + Int.SIZE_BYTES).toInt() and 0xffff
    private fun maskStart(id: Int) = masks + id * words * Long.SIZE_BYTES

    companion object {
        private val CATEGORY_NAME = Regex("[a-z][a-z0-9_]*")

        fun load(path: Path, expectedHash: String): RuntimeGrammarRoles =
            readGrammarIndex(path, expectedHash, MAGIC, HEADER_SIZE, ::RuntimeGrammarRoles)
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
    var keyOffset = 0
    for ((key, mask) in entries) {
        data.writeInt(keyOffset)
        data.writeShort(masks.getValue(mask))
        keyOffset += key.size
    }
    data.writeInt(keyOffset)
    val textStart = stream.size()
    entries.forEach { data.write(it.first) }
    val bytes = stream.toByteArray()
    val crc = CRC32().apply { update(bytes, HEADER_SIZE, bytes.size - HEADER_SIZE) }
    ByteBuffer.wrap(bytes).apply {
        listOf(MAGIC, 1, bytes.size, crc.value.toInt(), source.categoryNames.size, masks.size, entries.size,
            masksStart, rowsStart, textStart).forEach(::putInt)
    }
    output.toFile().writeBytes(bytes)
}
