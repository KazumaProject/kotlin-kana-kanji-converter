package com.kazumaproject.grammar

import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.mozc.MozcIdDefParser
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.BitSet

data class ContextGrammar(
    val id: Int,
    val partOfSpeech: String,
    val subdivisions: List<String>,
    val conjugationType: String?,
    val conjugationForm: String?,
    val contextLabel: String?,
)

data class WordGrammar(val left: ContextGrammar, val right: ContextGrammar)

enum class GrammarRole {
    ADJECTIVAL_STEM,
    ADJECTIVAL_ATTRIBUTIVE,
}

/** Non-null fields are combined. Subdivisions are matched at their original id.def levels. */
data class GrammarSelector(
    val partOfSpeech: String? = null,
    val subdivisions: List<String?> = emptyList(),
    val conjugationType: String? = null,
    val conjugationForm: String? = null,
    val role: GrammarRole? = null,
) {
    init {
        require(subdivisions.size <= 3) { "id.def has three POS subdivision fields" }
    }
}

internal class GrammarTable(labels: List<String>) {
    private val contexts = labels.mapIndexed { id, label ->
        val fields = label.split(',', limit = 7)
        require(fields.size == 7) { "Invalid context definition for ID $id" }
        ContextGrammar(id, fields[0], fields.subList(1, 4).toList(),
            fields[4].unlessWildcard(), fields[5].unlessWildcard(), fields[6].unlessWildcard())
    }

    val size get() = contexts.size
    val adjectivalStem = matching(GrammarSelector(role = GrammarRole.ADJECTIVAL_STEM))
    val adjectivalAttributive = matching(GrammarSelector(role = GrammarRole.ADJECTIVAL_ATTRIBUTIVE))

    fun get(id: Short): ContextGrammar = requireNotNull(contexts.getOrNull(id.toInt())) {
        "No grammar definition for context ID $id"
    }

    fun word(left: Short, right: Short) = WordGrammar(get(left), get(right))

    fun matching(selector: GrammarSelector): BitSet = BitSet(size).apply {
        contexts.forEach { context ->
            if (context.id != 0 &&
                (selector.partOfSpeech == null || context.partOfSpeech == selector.partOfSpeech) &&
                selector.subdivisions.withIndex().all { (index, name) ->
                    name == null || context.subdivisions[index] == name
                } &&
                (selector.conjugationType == null || context.conjugationType == selector.conjugationType) &&
                (selector.conjugationForm == null || context.conjugationForm == selector.conjugationForm) &&
                (selector.role == null || context.hasRole(selector.role))
            ) set(context.id)
        }
    }

    private fun ContextGrammar.hasRole(role: GrammarRole): Boolean = when (role) {
        GrammarRole.ADJECTIVAL_STEM -> partOfSpeech == "名詞" && "形容動詞語幹" in subdivisions
        GrammarRole.ADJECTIVAL_ATTRIBUTIVE ->
            partOfSpeech == "助動詞" && conjugationType == "特殊・ダ" && conjugationForm == "体言接続"
    }

    private fun String.unlessWildcard() = takeUnless { it == "*" }
}

/** Optional companion file for a dictionary build. Existing dictionary binaries are read unchanged. */
object GrammarMetadata {
    private const val MAGIC = 0x4B4B4731 // KKG1
    private val contextAssets = listOf("connectionId.dat", "pos_table.dat")

    fun generate(idDef: File, resourceDirectory: File, output: File) {
        val labels = MozcIdDefParser.parse(idDef.toPath()).map { it.name }
        val contextCount = GrammarTable(labels).size
        val matrixLength = resourceDirectory.resolve(contextAssets[0]).length()
        require(matrixLength == contextCount.toLong() * contextCount * Short.SIZE_BYTES) {
            "id.def has $contextCount IDs but the connection matrix has $matrixLength bytes"
        }
        val tokens = TokenArray().apply { readPOSTable(1, resourceDirectory.resolve(contextAssets[1]).path) }
        require(tokens.leftIds.all { it.toInt() in labels.indices } &&
            tokens.rightIds.all { it.toInt() in labels.indices }) { "POS table contains an undefined context ID" }
        val digests = listOf(fingerprint(resourceDirectory.resolve(contextAssets[0])), fingerprint(tokens.leftIds.toShortArray(), tokens.rightIds.toShortArray()))
        val target = output.absoluteFile
        target.parentFile.mkdirs()
        val temporary = Files.createTempFile(target.parentFile.toPath(), "grammar-", ".tmp").toFile()
        try {
            DataOutputStream(temporary.outputStream().buffered()).use { stream ->
                stream.writeInt(MAGIC)
                digests.forEach(stream::write)
                stream.writeInt(labels.size)
                labels.forEach(stream::writeUTF)
            }
            Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        } finally {
            temporary.delete()
        }
    }

    internal fun read(file: File, matrix: ConnectionMatrix, tokens: TokenArray): GrammarTable =
        read(file, fingerprints(matrix, tokens), matrix.size)

    internal fun read(file: File, assetFingerprints: List<ByteArray>, matrixSize: Int): GrammarTable =
        DataInputStream(file.inputStream().buffered()).use { stream ->
            require(stream.readInt() == MAGIC) { "Unsupported grammar metadata format: ${file.path}" }
            contextAssets.zip(assetFingerprints).forEach { (name, digest) ->
                val expected = ByteArray(32).also { stream.readFully(it) }
                require(MessageDigest.isEqual(expected, digest)) { "Grammar metadata does not match $name" }
            }
            val count = stream.readInt()
            require(count == matrixSize && count in 1..(Short.MAX_VALUE.toInt() + 1)) {
                "Grammar metadata context count $count does not match matrix size $matrixSize"
            }
            GrammarTable(List(count) { stream.readUTF() }).also {
                require(stream.read() == -1) { "Unexpected trailing grammar metadata" }
            }
        }

    internal fun fingerprints(matrix: ConnectionMatrix, tokens: TokenArray): List<ByteArray> =
        listOf(fingerprint(matrix.costs), fingerprint(tokens.leftIds.toShortArray(), tokens.rightIds.toShortArray()))

    // Canonical big-endian shorts match the raw matrix encoding. The two POS arrays
    // are hashed in order independently of Java object serialization.
    private fun fingerprint(vararg arrays: ShortArray): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        val bytes = ByteArray(64 * 1024)
        val buffer = ByteBuffer.wrap(bytes).asShortBuffer()
        for (array in arrays) {
            for (offset in array.indices step buffer.capacity()) {
                val count = minOf(buffer.capacity(), array.size - offset)
                buffer.clear()
                buffer.put(array, offset, count)
                digest.update(bytes, 0, count * Short.SIZE_BYTES)
            }
        }
        return digest.digest()
    }

    private fun fingerprint(file: File): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { stream ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest()
    }
}

internal fun main(args: Array<String>) {
    require(args.size == 3) { "Usage: GenerateGrammarMetadata <id.def> <resource directory> <output>" }
    GrammarMetadata.generate(File(args[0]), File(args[1]), File(args[2]))
}
