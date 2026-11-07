package grammar

import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.file.Path
import java.nio.file.StandardOpenOption.READ
import java.security.MessageDigest
import java.util.HexFormat
import java.util.zip.CRC32

internal fun interface GrammarRoles {
    fun lookup(surface: String, normalized: String): Set<String>
}

/** Reads the ECAT v1 indexes written by writeCompactCategories. Only category names are decoded eagerly. */
internal class CompactGrammarRoles private constructor(private val data: ByteBuffer) : GrammarRoles {
    private val categoryCount = data.getInt(16)
    private val stringCount = data.getInt(20)
    private val lexemeCount = data.getInt(24)
    private val maskCount = data.getInt(28)
    private val formCount = data.getInt(32)
    private val exactCount = data.getInt(36)
    private val fallbackCount = data.getInt(40)
    private val maskWords = data.getInt(44)

    private val stringOffsets = data.getInt(48)
    private val text = data.getInt(52)
    private val categories = data.getInt(56)
    private val lexemes = data.getInt(60)
    private val masks = data.getInt(64)
    private val forms = data.getInt(68)
    private val exact = data.getInt(72)
    private val exactPostings = data.getInt(76)
    private val fallback = data.getInt(80)
    private val fallbackPostings = data.getInt(84)
    private val end = data.getInt(88)

    private val categoryNames: List<String>

    init {
        require(categoryCount in 1..1024 && maskWords == (categoryCount + 63) / 64) { "Invalid category count" }
        require(stringCount > 0 && lexemeCount > 0 && maskCount > 0 && formCount in 1..1_000_000 &&
            exactCount > 0 && fallbackCount >= 0) { "Invalid table count" }
        require(stringOffsets == HEADER_SIZE && end == data.capacity() && categories >= text &&
            data.getInt(92) == 0) { "Invalid section offsets" }
        checkSection(stringOffsets, text, stringCount.toLong() + 1, Int.SIZE_BYTES)
        checkSection(categories, lexemes, categoryCount.toLong(), CATEGORY_ROW)
        checkSection(lexemes, masks, lexemeCount.toLong(), LEXEME_ROW)
        checkSection(masks, forms, maskCount.toLong(), maskWords * Long.SIZE_BYTES)
        checkSection(forms, exact, formCount.toLong(), FORM_ROW)
        checkSection(exact, exactPostings, exactCount.toLong(), INDEX_ROW)
        checkSection(fallback, fallbackPostings, fallbackCount.toLong(), INDEX_ROW)

        var previous = 0
        for (id in 0..stringCount) {
            val offset = data.getInt(stringOffsets + id * Int.SIZE_BYTES)
            require(offset in previous..(categories - text) && (id != 0 || offset == 0)) { "Invalid string offset" }
            previous = offset
        }
        require(previous == categories - text) { "Invalid string table size" }
        val nameIds = List(categoryCount) { id -> data.getInt(categories + id * CATEGORY_ROW) }
        require(nameIds.toSet().size == categoryCount) { "Duplicate category name reference" }
        categoryNames = nameIds.map(::stringAt)
        require(categoryNames.toSet().size == categoryCount &&
            categoryNames.all { it.matches(CATEGORY_NAME) }) { "Invalid category names" }

        val usedLastBits = categoryCount % 64
        if (usedLastBits != 0) {
            for (id in 0 until maskCount) {
                require(data.getLong(maskOffset(id) + (maskWords - 1) * Long.SIZE_BYTES) ushr usedLastBits == 0L) {
                    "Invalid category bit"
                }
            }
        }
        for (id in 0 until formCount) {
            val row = forms + id * FORM_ROW
            require(data.getInt(row + FORM_MASK) in 0 until maskCount) { "Invalid form mask" }
        }
        checkIndex(exact, exactCount, exactPostings, fallback)
        checkIndex(fallback, fallbackCount, fallbackPostings, end)
    }

    override fun lookup(surface: String, normalized: String): Set<String> {
        val bits = LongArray(maskWords)
        // A lowercase, normalized spelling is already included in the fallback index.
        if (surface != normalized) {
            collect(surface.toByteArray(Charsets.UTF_8), exact, exactCount, exactPostings, bits)
        }
        collect(normalized.toByteArray(Charsets.UTF_8), fallback, fallbackCount, fallbackPostings, bits)
        if (bits.all { it == 0L }) return emptySet()
        return buildSet {
            for (word in bits.indices) {
                var remaining = bits[word]
                while (remaining != 0L) {
                    add(categoryNames[word * 64 + remaining.countTrailingZeroBits()])
                    remaining = remaining and (remaining - 1)
                }
            }
        }
    }

    private fun collect(key: ByteArray, index: Int, count: Int, postings: Int, bits: LongArray) {
        var low = 0
        var high = count - 1
        while (low <= high) {
            val mid = (low + high) ushr 1
            val row = index + mid * INDEX_ROW
            val id = data.getInt(row)
            val start = stringStart(id)
            val length = stringStart(id + 1) - start
            var order = 0
            for (i in 0 until minOf(key.size, length)) {
                order = (key[i].toInt() and 255) - (data.get(start + i).toInt() and 255)
                if (order != 0) break
            }
            if (order == 0) order = key.size - length
            when {
                order < 0 -> high = mid - 1
                order > 0 -> low = mid + 1
                else -> {
                    val first = data.getInt(row + 4)
                    val size = data.getInt(row + 8)
                    for (i in first until first + size) {
                        val form = data.getInt(postings + i * Int.SIZE_BYTES)
                        val mask = maskOffset(data.getInt(forms + form * FORM_ROW + FORM_MASK))
                        for (word in bits.indices) {
                            bits[word] = bits[word] or data.getLong(mask + word * Long.SIZE_BYTES)
                        }
                    }
                    return
                }
            }
        }
    }

    private fun checkIndex(index: Int, count: Int, postings: Int, postingsEnd: Int) {
        require(postingsEnd >= postings && (postingsEnd - postings) % Int.SIZE_BYTES == 0) { "Invalid postings size" }
        val postingCount = (postingsEnd - postings) / Int.SIZE_BYTES
        var next = 0
        var previousId = -1
        for (i in 0 until count) {
            val row = index + i * INDEX_ROW
            val id = data.getInt(row)
            val start = data.getInt(row + 4)
            val size = data.getInt(row + 8)
            require(id in 0 until stringCount && (previousId < 0 || compareStrings(previousId, id) < 0)) {
                "Invalid or unordered index key"
            }
            require(start == next && size in 1..(postingCount - next)) { "Invalid posting range" }
            next += size
            previousId = id
        }
        require(next == postingCount) { "Unreferenced postings" }
        for (i in 0 until postingCount) {
            require(data.getInt(postings + i * Int.SIZE_BYTES) in 0 until formCount) { "Invalid posting form" }
        }
    }

    private fun compareStrings(left: Int, right: Int): Int {
        val start = stringStart(left)
        val other = stringStart(right)
        val length = stringStart(left + 1) - start
        val otherLength = stringStart(right + 1) - other
        for (i in 0 until minOf(length, otherLength)) {
            val order = (data.get(start + i).toInt() and 255) - (data.get(other + i).toInt() and 255)
            if (order != 0) return order
        }
        return length - otherLength
    }

    private fun checkSection(start: Int, end: Int, count: Long, width: Int) {
        require(start in HEADER_SIZE..data.capacity() && end in start..data.capacity() &&
            count * width == (end - start).toLong()) { "Invalid section size" }
    }

    private fun stringStart(id: Int) = text + data.getInt(stringOffsets + id * Int.SIZE_BYTES)

    private fun stringAt(id: Int): String {
        require(id in 0 until stringCount) { "Invalid category name reference" }
        val start = stringStart(id)
        val length = stringStart(id + 1) - start
        require(length in 1..data.capacity() - start) { "Invalid category name size" }
        val bytes = ByteArray(length)
        data.get(start, bytes)
        return bytes.toString(Charsets.UTF_8)
    }

    private fun maskOffset(id: Int) = masks + id * maskWords * Long.SIZE_BYTES

    companion object {
        private const val HEADER_SIZE = 96
        private const val MAX_SIZE = 268_435_456
        private const val CATEGORY_ROW = 12
        private const val LEXEME_ROW = 8
        private const val FORM_ROW = 16
        private const val FORM_MASK = 12
        private const val INDEX_ROW = 12
        private val CATEGORY_NAME = Regex("[a-z][a-z0-9_]*")

        fun load(file: Path, expectedHash: String?): CompactGrammarRoles {
            try {
                val mapped = FileChannel.open(file, READ).use { channel ->
                    val size = channel.size()
                    require(size in HEADER_SIZE.toLong()..MAX_SIZE.toLong()) { "Invalid file size" }
                    channel.map(FileChannel.MapMode.READ_ONLY, 0, size)
                }
                require(mapped.getInt(0) == 0x45434154 && mapped.getInt(4) == 1 &&
                    mapped.getInt(8) == mapped.capacity()) { "Invalid ECAT v1 header" }
                val crc = CRC32().apply { update(mapped.duplicate().position(HEADER_SIZE)) }
                require(crc.value.toInt() == mapped.getInt(12)) { "Invalid payload checksum" }
                if (expectedHash != null) {
                    val digest = MessageDigest.getInstance("SHA-256").apply { update(mapped.duplicate()) }
                    require(HexFormat.of().formatHex(digest.digest()) == expectedHash) { "Bundle SHA-256 mismatch" }
                }
                return CompactGrammarRoles(mapped)
            } catch (failure: IllegalArgumentException) {
                throw IllegalArgumentException("Invalid compact grammar $file: ${failure.message}", failure)
            }
        }
    }
}
