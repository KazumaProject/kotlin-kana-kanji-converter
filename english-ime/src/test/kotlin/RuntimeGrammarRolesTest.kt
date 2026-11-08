import grammar.*
import java.io.*
import java.nio.ByteBuffer
import java.nio.file.Files
import java.util.Arrays
import java.util.zip.CRC32
import kotlin.test.*

class RuntimeGrammarRolesTest {
    @Test
    fun frontCodingPreservesRolesAcrossBlocksAndLegacyFiles() = fixture { root, lexicon, compact ->
        val v1 = root.resolve("legacy.erol")
        val v2 = root.resolve("packed.erol")
        legacy(compact, v1)
        writeRuntimeGrammarRoles(compact, v2.toPath())
        assertTrue(v2.length() < v1.length() * 0.8, "Shared name prefixes should reduce the actual index")
        val readers = listOf(v1, v2).map { RuntimeGrammarRoles.load(it.toPath(), categoryFileHash(it)) }
        val keys = lexicon.forms.map { it.key.surface }.toSet()
        val probes = keys + keys.map { it.lowercase() } + keys.map { it + "!" } +
            listOf("", "A", "Long Shared Prefix Person 0031!", "ZZZ", "Pokém", "東京")
        for (key in probes) {
            val expected = lexicon.lookup(key).flatMap { it.dictionaries }.toSet()
            for (reader in readers) assertEquals(expected, reader.lookup(key, lookupKey(key)), key)
        }
    }

    @Test
    fun rejectsInvalidBlocksLengthsMasksAndCountsWithValidChecksums() = fixture { root, _, compact ->
        val file = root.resolve("packed.erol")
        writeRuntimeGrammarRoles(compact, file.toPath())
        val valid = file.readBytes()
        val header = ByteBuffer.wrap(valid)
        val rows = header.getInt(32)
        val text = header.getInt(36)
        val mutations: List<(ByteBuffer) -> Unit> = listOf(
            { it.putInt(rows, 1) }, // Unreferenced prefix bytes.
            { it.put(text, 1) }, // First key cannot inherit bytes from another block.
            { it.put(text + 1, 0) }, // Empty suffix.
            { it.putShort(text + 2, (-1).toShort()) }, // Unknown mask (fixture lengths fit one byte).
            { it.putInt(24, 1) }, // Wrong directory size/record count.
            { for (i in 0..4) it.put(text + i, 0xff.toByte()) }, // Overflowing varint.
        )
        for (mutate in mutations) {
            val bytes = valid.copyOf()
            mutate(ByteBuffer.wrap(bytes))
            ByteBuffer.wrap(bytes).putInt(12, CRC32().apply { update(bytes, 40, bytes.size - 40) }.value.toInt())
            file.writeBytes(bytes)
            assertFailsWith<IllegalArgumentException> {
                RuntimeGrammarRoles.load(file.toPath(), categoryFileHash(file))
            }
        }
        file.writeBytes(valid)
        assertFailsWith<IllegalArgumentException> { RuntimeGrammarRoles.load(file.toPath(), "0".repeat(64)) }
    }

    private fun fixture(block: (File, Lexicon, CompactGrammarRoles) -> Unit) {
        val root = Files.createTempDirectory("front-coded-roles").toFile()
        try {
            root.resolve("categories.tsv").writeText("category\tdefinition\texamples\nnoun\tNoun\tword\nnoun_proper\tName\tName\n")
            val names = (0..199).map { "Long Shared Prefix Person " + it.toString().padStart(4, '0') } +
                listOf("Pokémon", "Pokémons", "東京さん", "東京さま", "long shared prefix person 0032")
            root.resolve("forms.tsv").writeText("lexeme_id\tlemma\tsurface\tevidence\n" +
                names.mapIndexed { i, s -> "n$i\t$s\t$s\thttps://example.org/name\n" }.joinToString(""))
            root.resolve("memberships.tsv").writeText("category\tlexeme_id\tsurface\n" +
                names.mapIndexed { i, s -> "${if (s.first().isLowerCase()) "noun" else "noun_proper"}\tn$i\t$s\n" }.joinToString(""))
            val lexicon = Lexicon.load(root)
            val full = root.resolve("full.ecat")
            writeCompactCategories(lexicon, full)
            block(root, lexicon, CompactGrammarRoles.load(full.toPath(), categoryFileHash(full)))
        } finally { root.deleteRecursively() }
    }

    // Legacy wire fixture: v1 has an offset+mask per key and unshared UTF-8 text.
    private fun legacy(source: CompactGrammarRoles, file: File) {
        val entries = source.runtimeEntries().map { (k, m) -> k.toByteArray() to m }
            .sortedWith { a, b -> Arrays.compareUnsigned(a.first, b.first) }.toList()
        val masks = entries.map { it.second }.distinct().withIndex().associate { it.value to it.index }
        val stream = ByteArrayOutputStream()
        val out = DataOutputStream(stream)
        out.write(ByteArray(40))
        source.categoryNames.forEach { out.writeShort(it.toByteArray().size); out.write(it.toByteArray()) }
        val maskStart = stream.size()
        masks.keys.forEach { it.forEach(out::writeLong) }
        val rows = stream.size()
        var offset = 0
        entries.forEach { (k, m) -> out.writeInt(offset); out.writeShort(masks.getValue(m)); offset += k.size }
        out.writeInt(offset)
        val text = stream.size()
        entries.forEach { out.write(it.first) }
        val bytes = stream.toByteArray()
        val crc = CRC32().apply { update(bytes, 40, bytes.size - 40) }.value.toInt()
        ByteBuffer.wrap(bytes).apply {
            listOf(0x45524F4C, 1, bytes.size, crc, source.categoryNames.size, masks.size, entries.size,
                maskStart, rows, text).forEach(::putInt)
        }
        file.writeBytes(bytes)
    }
}
