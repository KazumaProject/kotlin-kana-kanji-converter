import grammar.Lexicon
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.util.Locale
import java.util.zip.CRC32

/** ECAT v1: shared UTF-8 strings, numeric lexical references and shared membership masks. */
internal fun writeCompactCategories(lexicon: Lexicon, output: File) {
    val strings = linkedMapOf<String, Int>()
    fun string(value: String) = strings.getOrPut(value) { strings.size }
    val categories = lexicon.categories
    require(categories.size in 1..1024 && lexicon.forms.size in 1..1_000_000) { "Category data exceeds ECAT v1 limits" }
    val categoryIds = categories.mapIndexed { i, c -> c.name to i }.toMap()
    val words = (categories.size + 63) / 64
    val categoryRows = categories.map { intArrayOf(string(it.name), string(it.definition), string(it.examples)) }
    val lexemes = linkedMapOf<String, Int>()
    val lexicalRows = mutableListOf<IntArray>()
    val masks = linkedMapOf<List<Long>, Int>()
    val formRows = lexicon.forms.map { form ->
        val lexeme = lexemes.getOrPut(form.key.lexemeId) {
            lexicalRows += intArrayOf(string(form.key.lexemeId), string(form.lemma))
            lexicalRows.lastIndex
        }
        val mask = LongArray(words)
        form.dictionaries.forEach { name -> val id = categoryIds.getValue(name); mask[id / 64] = mask[id / 64] or (1L shl (id % 64)) }
        val maskId = masks.getOrPut(mask.toList()) { masks.size }
        intArrayOf(lexeme, string(form.key.surface), string(form.evidence), maskId)
    }
    val exact = linkedMapOf<String, MutableList<Int>>()
    val fallback = linkedMapOf<String, MutableList<Int>>()
    lexicon.forms.forEachIndexed { index, form ->
        exact.getOrPut(form.key.surface) { mutableListOf() }.add(index)
        if (form.key.surface == form.key.surface.lowercase(Locale.ROOT)) {
            val key = form.key.surface.replace('’', '\'').lowercase(Locale.ROOT)
            fallback.getOrPut(key) { mutableListOf() }.add(index)
        }
    }
    fun indexRows(groups: Map<String, List<Int>>): Pair<List<IntArray>, List<Int>> {
        val encoded = groups.keys.associateWith { it.toByteArray(Charsets.UTF_8) }
        val sorted = groups.keys.sortedWith { a, b ->
            val left = encoded.getValue(a); val right = encoded.getValue(b)
            var comparison = 0
            for (i in 0 until minOf(left.size, right.size)) {
                comparison = (left[i].toInt() and 255).compareTo(right[i].toInt() and 255)
                if (comparison != 0) break
            }
            if (comparison == 0) left.size.compareTo(right.size) else comparison
        }
        val postings = mutableListOf<Int>()
        val rows = sorted.map { key ->
            intArrayOf(string(key), postings.size, groups.getValue(key).size).also { postings.addAll(groups.getValue(key)) }
        }
        return rows to postings
    }
    val (exactRows, exactPostings) = indexRows(exact)
    val (fallbackRows, fallbackPostings) = indexRows(fallback)
    val text = strings.keys.map { it.toByteArray(Charsets.UTF_8) }
    val stream = ByteArrayOutputStream()
    val data = DataOutputStream(stream)
    repeat(24) { data.writeInt(0) }
    val offsets = mutableListOf<Int>()
    offsets += stream.size()
    var textOffset = 0
    text.forEach { data.writeInt(textOffset); textOffset += it.size }
    data.writeInt(textOffset)
    offsets += stream.size()
    text.forEach(data::write)
    offsets += stream.size()
    categoryRows.forEach { row -> row.forEach(data::writeInt) }
    offsets += stream.size()
    lexicalRows.forEach { row -> row.forEach(data::writeInt) }
    offsets += stream.size()
    masks.keys.forEach { mask -> mask.forEach(data::writeLong) }
    offsets += stream.size()
    formRows.forEach { row -> row.forEach(data::writeInt) }
    offsets += stream.size()
    exactRows.forEach { row -> row.forEach(data::writeInt) }
    offsets += stream.size()
    exactPostings.forEach(data::writeInt)
    offsets += stream.size()
    fallbackRows.forEach { row -> row.forEach(data::writeInt) }
    offsets += stream.size()
    fallbackPostings.forEach(data::writeInt)
    offsets += stream.size()
    val bytes = stream.toByteArray()
    require(bytes.size <= 268_435_456) { "Compact category file is too large" }
    val crc = CRC32().apply { update(bytes, 96, bytes.size - 96) }
    val header = ByteBuffer.wrap(bytes)
    listOf(0x45434154, 1, bytes.size, crc.value.toInt(), categories.size, text.size, lexicalRows.size,
        masks.size, formRows.size, exactRows.size, fallbackRows.size, words).forEach(header::putInt)
    offsets.forEach(header::putInt)
    header.putInt(0)
    output.writeBytes(bytes)
}
