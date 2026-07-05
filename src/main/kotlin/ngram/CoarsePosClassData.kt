package com.kazumaproject.ngram

import com.kazumaproject.mozc.MozcIdDefParser
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.io.path.createDirectories
import kotlin.io.path.isRegularFile

const val COARSE_POS_CLASS_FORMAT = "COARSE_POS_CLASS_LEFT_ID_TABLE"
const val COARSE_POS_CLASS_VERSION = 1
const val COARSE_POS_CLASS_KEY_MODE = "MOZC_ID_DEF_LEFT_ID_BYTE_CLASS"
const val COARSE_POS_CLASS_MAPPING_POLICY = "LEFT_ID_POS1_V1"

interface CoarsePosClassTable {
    fun classify(leftId: Int): ContextualCorrectionCoarseClass

    fun classify(leftId: Short): ContextualCorrectionCoarseClass =
        classify(leftId.toInt())

    fun classify(leftId: Short, rightId: Short): ContextualCorrectionCoarseClass {
        val byLeft = classify(leftId)
        return if (byLeft != ContextualCorrectionCoarseClass.UNKNOWN) byLeft else classify(rightId)
    }
}

object EmptyCoarsePosClassTable : CoarsePosClassTable {
    override fun classify(leftId: Int): ContextualCorrectionCoarseClass =
        ContextualCorrectionCoarseClass.UNKNOWN
}

data class CoarsePosClassBuild(
    val classesByLeftId: ByteArray,
    val sourceChecksumHex: String,
    val classCounts: Map<ContextualCorrectionCoarseClass, Int>,
) {
    val idCount: Int
        get() = classesByLeftId.size

    val maxId: Int
        get() = classesByLeftId.lastIndex
}

data class CoarsePosClassManifest(
    val format: String,
    val version: Int,
    val keyMode: String,
    val mappingPolicy: String,
    val sourceFile: String,
    val idDefEntryCount: Int,
    val maxId: Int,
    val classCounts: Map<ContextualCorrectionCoarseClass, Int>,
    val dictionaryBuildId: String,
    val contentChecksum: String,
    val sourceChecksum: String,
    val byteSize: Long,
)

data class CoarsePosClassWriteResult(
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
)

data class CoarsePosClassVerificationResult(
    val verifiedIdCount: Int,
    val elapsedNanos: Long,
)

object CoarsePosClassMapper {
    fun classifyIdDefName(name: String): ContextualCorrectionCoarseClass {
        val pos1 = name.substringBefore(',')
        return when (pos1) {
            "名詞" -> ContextualCorrectionCoarseClass.NOUN
            "助詞" -> ContextualCorrectionCoarseClass.PARTICLE
            "動詞" -> ContextualCorrectionCoarseClass.VERB
            "助動詞" -> ContextualCorrectionCoarseClass.AUX
            "記号" -> ContextualCorrectionCoarseClass.SYMBOL
            else -> ContextualCorrectionCoarseClass.UNKNOWN
        }
    }
}

object CoarsePosClassBuilder {
    fun build(idDefPath: Path): CoarsePosClassBuild {
        require(idDefPath.isRegularFile()) { "Missing id.def for coarse POS class generation: $idDefPath" }
        val entries = MozcIdDefParser.parse(idDefPath)
        val classes = ByteArray(entries.last().id + 1) {
            ContextualCorrectionCoarseClass.UNKNOWN.id.toByte()
        }
        entries.forEach { entry ->
            classes[entry.id] = CoarsePosClassMapper.classifyIdDefName(entry.name).id.toByte()
        }
        val counts = ContextualCorrectionCoarseClass.entries.associateWith { coarseClass ->
            classes.count { (it.toInt() and 0xff) == coarseClass.id }
        }
        return CoarsePosClassBuild(
            classesByLeftId = classes,
            sourceChecksumHex = sha256Hex(Files.readAllBytes(idDefPath)),
            classCounts = counts,
        )
    }
}

class CoarsePosClassDataWriter {
    fun write(outputPath: Path, build: CoarsePosClassBuild): CoarsePosClassWriteResult {
        outputPath.parent?.createDirectories()
        val bytes = toByteArray(build)
        Files.write(outputPath, bytes)
        return CoarsePosClassWriteResult(
            dictionaryBuildIdHex = bytes.copyOfRange(CPC_BUILD_ID_OFFSET, CPC_BUILD_ID_OFFSET + CPC_SHA_256_BYTES).toHex(),
            contentChecksumHex = bytes.copyOfRange(CPC_CHECKSUM_OFFSET, CPC_CHECKSUM_OFFSET + CPC_SHA_256_BYTES).toHex(),
            byteSize = bytes.size.toLong(),
        )
    }

    fun toByteArray(build: CoarsePosClassBuild): ByteArray {
        require(build.classesByLeftId.isNotEmpty()) { "Coarse POS class table must not be empty" }
        build.classesByLeftId.forEachIndexed { index, rawClass ->
            ContextualCorrectionCoarseClass.fromId(rawClass.toInt() and 0xff)
            require(index == 0 || index <= Short.MAX_VALUE) {
                "Coarse POS class leftId exceeds Short range: $index"
            }
        }
        val sourceChecksum = build.sourceChecksumHex.hexToBytes()
        val buildId = buildId(sourceChecksum, build.classesByLeftId)
        val writer = CoarsePosClassLeWriter()
        writer.writeAscii(CPC_MAGIC)
        writer.writeInt(COARSE_POS_CLASS_VERSION)
        writer.writeInt(build.classesByLeftId.size)
        writer.writeBytes(sourceChecksum)
        writer.writeBytes(buildId)
        writer.writeBytes(ByteArray(CPC_SHA_256_BYTES))
        writer.writeBytes(build.classesByLeftId)

        val bytes = writer.toByteArray()
        val checksum = coarsePosClassChecksum(bytes)
        checksum.copyInto(bytes, CPC_CHECKSUM_OFFSET)
        return bytes
    }

    private fun buildId(sourceChecksum: ByteArray, classesByLeftId: ByteArray): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update("CPC1-build-v1".toByteArray(Charsets.US_ASCII))
        digest.update(sourceChecksum)
        digest.updateIntCpc(classesByLeftId.size)
        digest.update(classesByLeftId)
        return digest.digest()
    }
}

class CoarsePosClassDataReader {
    fun read(inputPath: Path, verifyChecksum: Boolean = true): LoadedCoarsePosClassTable {
        require(inputPath.isRegularFile()) { "Coarse POS class data does not exist: $inputPath" }
        return readBytes(Files.readAllBytes(inputPath), verifyChecksum)
    }

    fun readBytes(bytes: ByteArray, verifyChecksum: Boolean = true): LoadedCoarsePosClassTable {
        require(bytes.size >= CPC_HEADER_SIZE) { "Coarse POS class data is too small: ${bytes.size}" }
        if (verifyChecksum) {
            val expected = bytes.copyOfRange(CPC_CHECKSUM_OFFSET, CPC_CHECKSUM_OFFSET + CPC_SHA_256_BYTES)
            val actualInput = bytes.copyOf()
            actualInput.fill(0, CPC_CHECKSUM_OFFSET, CPC_CHECKSUM_OFFSET + CPC_SHA_256_BYTES)
            val actual = coarsePosClassChecksum(actualInput)
            require(expected.contentEquals(actual)) {
                "Coarse POS class checksum mismatch: expected=${expected.toHex()} actual=${actual.toHex()}"
            }
        }

        val reader = CoarsePosClassLeReader(bytes)
        require(reader.readAscii(4) == CPC_MAGIC) { "Invalid coarse POS class magic" }
        val version = reader.readInt()
        require(version == COARSE_POS_CLASS_VERSION) { "Unsupported coarse POS class version: $version" }
        val idCount = reader.readInt()
        require(idCount > 0) { "Invalid coarse POS class id count: $idCount" }
        val sourceChecksum = reader.readBytes(CPC_SHA_256_BYTES)
        val buildId = reader.readBytes(CPC_SHA_256_BYTES)
        val checksum = reader.readBytes(CPC_SHA_256_BYTES)
        val classesByLeftId = reader.readBytes(idCount)
        require(reader.isAtEnd()) { "Unexpected trailing bytes in coarse POS class data" }
        classesByLeftId.forEachIndexed { index, rawClass ->
            ContextualCorrectionCoarseClass.fromId(rawClass.toInt() and 0xff)
            require(index <= Short.MAX_VALUE) { "Coarse POS class leftId exceeds Short range: $index" }
        }
        return LoadedCoarsePosClassTable(
            classesByLeftId = classesByLeftId,
            sourceChecksumHex = sourceChecksum.toHex(),
            dictionaryBuildIdHex = buildId.toHex(),
            contentChecksumHex = checksum.toHex(),
            byteSize = bytes.size.toLong(),
        )
    }
}

class LoadedCoarsePosClassTable(
    private val classesByLeftId: ByteArray,
    val sourceChecksumHex: String,
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
) : CoarsePosClassTable {
    val idCount: Int
        get() = classesByLeftId.size

    override fun classify(leftId: Int): ContextualCorrectionCoarseClass {
        if (leftId !in classesByLeftId.indices) {
            return ContextualCorrectionCoarseClass.UNKNOWN
        }
        return ContextualCorrectionCoarseClass.fromId(classesByLeftId[leftId].toInt() and 0xff)
    }

    fun rawClassId(leftId: Int): Int =
        if (leftId in classesByLeftId.indices) classesByLeftId[leftId].toInt() and 0xff
        else ContextualCorrectionCoarseClass.UNKNOWN.id
}

object CoarsePosClassManifestWriter {
    fun write(outputPath: Path, manifest: CoarsePosClassManifest) {
        outputPath.parent?.createDirectories()
        Files.writeString(outputPath, toJson(manifest))
    }

    fun toJson(manifest: CoarsePosClassManifest): String = buildString {
        appendLine("{")
        appendLine("  \"format\": ${coarsePosClassJsonString(manifest.format)},")
        appendLine("  \"version\": ${manifest.version},")
        appendLine("  \"keyMode\": ${coarsePosClassJsonString(manifest.keyMode)},")
        appendLine("  \"mappingPolicy\": ${coarsePosClassJsonString(manifest.mappingPolicy)},")
        appendLine("  \"sourceFile\": ${coarsePosClassJsonString(manifest.sourceFile)},")
        appendLine("  \"idDefEntryCount\": ${manifest.idDefEntryCount},")
        appendLine("  \"maxId\": ${manifest.maxId},")
        appendLine("  \"classCounts\": {")
        ContextualCorrectionCoarseClass.entries.forEachIndexed { index, coarseClass ->
            val comma = if (index == ContextualCorrectionCoarseClass.entries.lastIndex) "" else ","
            appendLine("    \"${coarseClass.name}\": ${manifest.classCounts[coarseClass] ?: 0}$comma")
        }
        appendLine("  },")
        appendLine("  \"dictionaryBuildId\": ${coarsePosClassJsonString(manifest.dictionaryBuildId)},")
        appendLine("  \"contentChecksum\": ${coarsePosClassJsonString(manifest.contentChecksum)},")
        appendLine("  \"sourceChecksum\": ${coarsePosClassJsonString(manifest.sourceChecksum)},")
        appendLine("  \"byteSize\": ${manifest.byteSize}")
        appendLine("}")
    }
}

object CoarsePosClassGenerator {
    fun generate(idDefPath: Path, outputDataPath: Path, outputManifestPath: Path): CoarsePosClassManifest {
        val build = CoarsePosClassBuilder.build(idDefPath)
        val writeResult = CoarsePosClassDataWriter().write(outputDataPath, build)
        val manifest = CoarsePosClassManifest(
            format = COARSE_POS_CLASS_FORMAT,
            version = COARSE_POS_CLASS_VERSION,
            keyMode = COARSE_POS_CLASS_KEY_MODE,
            mappingPolicy = COARSE_POS_CLASS_MAPPING_POLICY,
            sourceFile = idDefPath.toString(),
            idDefEntryCount = build.idCount,
            maxId = build.maxId,
            classCounts = build.classCounts,
            dictionaryBuildId = writeResult.dictionaryBuildIdHex,
            contentChecksum = writeResult.contentChecksumHex,
            sourceChecksum = build.sourceChecksumHex,
            byteSize = writeResult.byteSize,
        )
        CoarsePosClassManifestWriter.write(outputManifestPath, manifest)
        return manifest
    }
}

object CoarsePosClassVerifier {
    fun verify(idDefPath: Path, dataPath: Path): CoarsePosClassVerificationResult {
        val startedAt = System.nanoTime()
        val build = CoarsePosClassBuilder.build(idDefPath)
        val table = CoarsePosClassDataReader().read(dataPath)
        require(table.idCount == build.idCount) {
            "Coarse POS class id count mismatch: expected=${build.idCount} actual=${table.idCount}"
        }
        require(table.sourceChecksumHex == build.sourceChecksumHex) {
            "Coarse POS class source checksum mismatch: expected=${build.sourceChecksumHex} actual=${table.sourceChecksumHex}"
        }
        build.classesByLeftId.forEachIndexed { leftId, rawClass ->
            val expected = rawClass.toInt() and 0xff
            val actual = table.rawClassId(leftId)
            require(actual == expected) {
                "Coarse POS class mismatch: leftId=$leftId expected=$expected actual=$actual"
            }
        }
        return CoarsePosClassVerificationResult(
            verifiedIdCount = build.idCount,
            elapsedNanos = System.nanoTime() - startedAt,
        )
    }
}

object CoarsePosClassPerformanceProbe {
    fun run(idDefPath: Path, dataPath: Path): String {
        val runtime = Runtime.getRuntime()
        runtime.gc()
        val heapBefore = runtime.totalMemory() - runtime.freeMemory()
        val loadStart = System.nanoTime()
        val table = CoarsePosClassDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart
        runtime.gc()
        val heapAfter = runtime.totalMemory() - runtime.freeMemory()

        val probes = IntArray(table.idCount) { it }
        repeat(5) {
            measureClassify(table, probes, minOps = 100_000)
        }
        val classifyNs = measureClassify(table, probes, minOps = 2_000_000)
        val verifyStart = System.nanoTime()
        val verified = CoarsePosClassVerifier.verify(idDefPath, dataPath)
        val verifyNanos = System.nanoTime() - verifyStart

        return buildString {
            appendLine("coarse_pos_class_probe:")
            appendLine("  binarySizeBytes=${Files.size(dataPath)}")
            appendLine("  loadTimeMs=${loadNanos / 1_000_000.0}")
            appendLine("  heapDeltaBytes=${heapAfter - heapBefore}")
            appendLine("  classifyNsOp=${"%.3f".format(classifyNs)}")
            appendLine("  lookupCount=${maxOf(1, (2_000_000 + probes.size - 1) / probes.size) * probes.size}")
            appendLine("  idCount=${table.idCount}")
            appendLine("  verificationTimeMs=${verifyNanos / 1_000_000.0}")
            appendLine("  verifiedIdCount=${verified.verifiedIdCount}")
        }
    }

    private fun measureClassify(table: CoarsePosClassTable, probes: IntArray, minOps: Int): Double {
        var hits = 0
        var operations = 0
        val repeats = maxOf(1, (minOps + probes.size - 1) / probes.size)
        val startedAt = System.nanoTime()
        repeat(repeats) {
            probes.forEach { leftId ->
                hits += table.classify(leftId).id
                operations += 1
            }
        }
        coarsePosBlackhole = hits
        return (System.nanoTime() - startedAt).toDouble() / operations
    }

    @Volatile
    private var coarsePosBlackhole: Int = 0
}

private class CoarsePosClassLeWriter {
    private val bytes = ArrayList<Byte>()

    fun writeAscii(value: String) {
        writeBytes(value.toByteArray(Charsets.US_ASCII))
    }

    fun writeBytes(value: ByteArray) {
        value.forEach { bytes += it }
    }

    fun writeInt(value: Int) {
        repeat(Int.SIZE_BYTES) { shift ->
            bytes += ((value ushr (shift * 8)) and 0xff).toByte()
        }
    }

    fun toByteArray(): ByteArray = ByteArray(bytes.size) { bytes[it] }
}

private class CoarsePosClassLeReader(private val bytes: ByteArray) {
    private var offset = 0

    fun readAscii(length: Int): String = readBytes(length).toString(Charsets.US_ASCII)

    fun readBytes(length: Int): ByteArray {
        require(length >= 0) { "Invalid coarse POS class read length: $length" }
        require(offset + length <= bytes.size) { "Unexpected end of coarse POS class data" }
        return bytes.copyOfRange(offset, offset + length).also { offset += length }
    }

    fun readInt(): Int {
        require(offset + Int.SIZE_BYTES <= bytes.size) { "Unexpected end of coarse POS class data" }
        var result = 0
        repeat(Int.SIZE_BYTES) { shift ->
            result = result or ((bytes[offset++].toInt() and 0xff) shl (shift * 8))
        }
        return result
    }

    fun isAtEnd(): Boolean = offset == bytes.size
}

private fun MessageDigest.updateIntCpc(value: Int) {
    update(
        byteArrayOf(
            (value and 0xff).toByte(),
            ((value ushr 8) and 0xff).toByte(),
            ((value ushr 16) and 0xff).toByte(),
            ((value ushr 24) and 0xff).toByte(),
        )
    )
}

private fun coarsePosClassChecksum(bytesWithZeroChecksum: ByteArray): ByteArray =
    MessageDigest.getInstance("SHA-256").digest(bytesWithZeroChecksum)

private fun sha256Hex(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).toHex()

private fun String.hexToBytes(): ByteArray {
    require(length == CPC_SHA_256_BYTES * 2) { "Expected SHA-256 hex string, length=$length" }
    return ByteArray(CPC_SHA_256_BYTES) { index ->
        substring(index * 2, index * 2 + 2).toInt(16).toByte()
    }
}

private fun coarsePosClassJsonString(value: String): String = buildString {
    append('"')
    value.forEach { ch ->
        when (ch) {
            '\\' -> append("\\\\")
            '"' -> append("\\\"")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> append(ch)
        }
    }
    append('"')
}

private const val CPC_MAGIC = "CPC1"
private const val CPC_SHA_256_BYTES = 32
private const val CPC_SOURCE_CHECKSUM_OFFSET = 4 + Int.SIZE_BYTES * 2
private const val CPC_BUILD_ID_OFFSET = CPC_SOURCE_CHECKSUM_OFFSET + CPC_SHA_256_BYTES
private const val CPC_CHECKSUM_OFFSET = CPC_BUILD_ID_OFFSET + CPC_SHA_256_BYTES
private const val CPC_HEADER_SIZE = CPC_CHECKSUM_OFFSET + CPC_SHA_256_BYTES
