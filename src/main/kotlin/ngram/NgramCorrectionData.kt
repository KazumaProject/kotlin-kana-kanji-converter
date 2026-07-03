package com.kazumaproject.ngram

import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.io.path.createDirectories

const val NGRAM_CORRECTION_FORMAT = "NGRAM_CORRECTION_EXACT"
const val NGRAM_CORRECTION_VERSION = 1
const val NGRAM_CORRECTION_LOOKUP_MODE = "READING_UTF8_EXACT_TO_SURFACE_SEQUENCE"
const val NGRAM_CORRECTION_CANDIDATE_ORDER = "source_manifest_order_then_source_row_order"

data class NgramCorrectionCandidate(
    val order: Int,
    val reading: String,
    val surfaces: List<String>,
) {
    val surfaceText: String
        get() = surfaces.joinToString("")
}

interface BinaryNgramCorrectionDictionary {
    fun lookup(reading: String): List<NgramCorrectionCandidate>
    fun lookupBest(reading: String): NgramCorrectionCandidate? = lookup(reading).firstOrNull()
}

object EmptyBinaryNgramCorrectionDictionary : BinaryNgramCorrectionDictionary {
    override fun lookup(reading: String): List<NgramCorrectionCandidate> = emptyList()
}

data class NgramCorrectionCompiledData(
    val sourceReadResult: NgramSourceReadResult,
    val candidates: List<NgramCorrectionCandidate>,
    val duplicateCount: Int,
    val skippedCount: Int,
)

data class NgramCorrectionManifest(
    val format: String,
    val version: Int,
    val lookupMode: String,
    val candidateOrder: String,
    val sourceFiles: List<String>,
    val sourceRowCount: Int,
    val candidateCount: Int,
    val readingCount: Int,
    val duplicateCount: Int,
    val skippedCount: Int,
    val entryCountByOrder: Map<Int, Int>,
    val dictionaryBuildId: String,
    val contentChecksum: String,
    val byteSize: Long,
)

data class NgramCorrectionWriteResult(
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
)

object NgramCorrectionCompiler {
    fun compile(sourceDirectory: Path): NgramCorrectionCompiledData {
        val sourceReadResult = NgramSourceTsvReader().readDirectory(sourceDirectory)
        val candidates = mutableListOf<NgramCorrectionCandidate>()
        val seen = linkedSetOf<NgramRuleKey>()
        var duplicateCount = 0
        sourceReadResult.rules.forEach { rawRule ->
            val rule = NgramRuleNormalizer.normalize(rawRule)
            val key = NgramRuleNormalizer.run { rule.key() }
            if (!seen.add(key)) {
                duplicateCount += 1
            } else {
                candidates += NgramCorrectionCandidate(
                    order = rule.order,
                    reading = rule.reading,
                    surfaces = rule.surfaces.take(rule.order),
                )
            }
        }
        return NgramCorrectionCompiledData(
            sourceReadResult = sourceReadResult,
            candidates = candidates,
            duplicateCount = duplicateCount,
            skippedCount = 0,
        )
    }
}

class NgramCorrectionDataWriter {
    fun write(outputPath: Path, candidates: List<NgramCorrectionCandidate>): NgramCorrectionWriteResult {
        outputPath.parent?.createDirectories()
        val bytes = toByteArray(candidates)
        Files.write(outputPath, bytes)
        return NgramCorrectionWriteResult(
            dictionaryBuildIdHex = bytes.copyOfRange(CORRECTION_BUILD_ID_OFFSET, CORRECTION_BUILD_ID_OFFSET + SHA_256_BYTES).toHex(),
            contentChecksumHex = bytes.copyOfRange(CORRECTION_CHECKSUM_OFFSET, CORRECTION_CHECKSUM_OFFSET + SHA_256_BYTES).toHex(),
            byteSize = bytes.size.toLong(),
        )
    }

    fun toByteArray(candidates: List<NgramCorrectionCandidate>): ByteArray {
        candidates.forEach(::requireValidCandidate)
        val orderedCandidates = candidates
            .withIndex()
            .sortedWith(compareBy<IndexedValue<NgramCorrectionCandidate>> { it.value.reading }.thenBy { it.index })
            .map { it.value }
        val groups = orderedCandidates
            .withIndex()
            .groupBy({ it.value.reading }, { it.index })
            .toSortedMap()
        val stringPool = CorrectionStringPool()
        groups.keys.forEach(stringPool::put)
        orderedCandidates.forEach { candidate ->
            candidate.surfaces.forEach(stringPool::put)
        }
        val buildId = buildId(orderedCandidates)

        val writer = CorrectionLeWriter()
        writer.writeAscii(CORRECTION_MAGIC)
        writer.writeInt(NGRAM_CORRECTION_VERSION)
        writer.writeInt(groups.size)
        writer.writeInt(orderedCandidates.size)
        writer.writeInt(stringPool.byteSize)
        writer.writeBytes(buildId)
        writer.writeBytes(ByteArray(SHA_256_BYTES))

        groups.forEach { (reading, indexes) ->
            val ref = stringPool.ref(reading)
            writer.writeInt(ref.offset)
            writer.writeInt(ref.length)
            writer.writeInt(indexes.first())
            writer.writeInt(indexes.size)
        }
        orderedCandidates.forEach { candidate ->
            writer.writeInt(candidate.order)
            for (index in 0 until NGRAM_SECTION_COUNT) {
                val surface = candidate.surfaces.getOrNull(index).orEmpty()
                val ref = if (surface.isEmpty()) CorrectionStringRef(0, 0) else stringPool.ref(surface)
                writer.writeInt(ref.offset)
                writer.writeInt(ref.length)
            }
        }
        writer.writeBytes(stringPool.toByteArray())

        val bytes = writer.toByteArray()
        buildId.copyInto(bytes, CORRECTION_BUILD_ID_OFFSET)
        val checksum = checksum(bytes)
        checksum.copyInto(bytes, CORRECTION_CHECKSUM_OFFSET)
        return bytes
    }

    private fun buildId(candidates: List<NgramCorrectionCandidate>): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update("NGC1-build-v1".toByteArray(Charsets.US_ASCII))
        candidates.forEach { candidate ->
            digest.updateInt(candidate.order)
            digest.updateUtf8(candidate.reading)
            candidate.surfaces.forEach(digest::updateUtf8)
        }
        return digest.digest()
    }

    private fun requireValidCandidate(candidate: NgramCorrectionCandidate) {
        require(candidate.order in 1..NGRAM_SECTION_COUNT) {
            "Invalid N-gram correction candidate order: ${candidate.order}"
        }
        require(candidate.reading.isNotEmpty()) {
            "N-gram correction candidate reading must not be empty"
        }
        require(candidate.surfaces.size == candidate.order) {
            "N-gram correction candidate surface count must match order: order=${candidate.order} surfaces=${candidate.surfaces.size}"
        }
        candidate.surfaces.forEachIndexed { index, surface ->
            require(surface.isNotEmpty()) {
                "N-gram correction candidate surface${index + 1} must not be empty"
            }
        }
    }
}

class NgramCorrectionDataReader {
    fun read(inputPath: Path, verifyChecksum: Boolean = true): LoadedNgramCorrectionDictionary {
        require(Files.isRegularFile(inputPath)) { "N-gram correction data does not exist: $inputPath" }
        return readBytes(Files.readAllBytes(inputPath), verifyChecksum)
    }

    fun readBytes(bytes: ByteArray, verifyChecksum: Boolean = true): LoadedNgramCorrectionDictionary {
        require(bytes.size >= CORRECTION_HEADER_SIZE) { "N-gram correction data is too small: ${bytes.size}" }
        if (verifyChecksum) {
            val expected = bytes.copyOfRange(CORRECTION_CHECKSUM_OFFSET, CORRECTION_CHECKSUM_OFFSET + SHA_256_BYTES)
            val actualInput = bytes.copyOf()
            actualInput.fill(0, CORRECTION_CHECKSUM_OFFSET, CORRECTION_CHECKSUM_OFFSET + SHA_256_BYTES)
            val actual = checksum(actualInput)
            require(expected.contentEquals(actual)) {
                "N-gram correction checksum mismatch: expected=${expected.toHex()} actual=${actual.toHex()}"
            }
        }

        val reader = CorrectionLeReader(bytes)
        require(reader.readAscii(4) == CORRECTION_MAGIC) { "Invalid N-gram correction magic" }
        val version = reader.readInt()
        require(version == NGRAM_CORRECTION_VERSION) { "Unsupported N-gram correction version: $version" }
        val groupCount = reader.readInt()
        val candidateCount = reader.readInt()
        val stringBytesLength = reader.readInt()
        require(groupCount >= 0) { "Invalid N-gram correction group count: $groupCount" }
        require(candidateCount >= 0) { "Invalid N-gram correction candidate count: $candidateCount" }
        require(stringBytesLength >= 0) { "Invalid N-gram correction string bytes length: $stringBytesLength" }
        val buildId = reader.readBytes(SHA_256_BYTES)
        val contentChecksum = reader.readBytes(SHA_256_BYTES)

        val groupReadingOffsets = IntArray(groupCount)
        val groupReadingLengths = IntArray(groupCount)
        val groupCandidateStarts = IntArray(groupCount)
        val groupCandidateCounts = IntArray(groupCount)
        repeat(groupCount) { index ->
            groupReadingOffsets[index] = reader.readInt()
            groupReadingLengths[index] = reader.readInt()
            groupCandidateStarts[index] = reader.readInt()
            groupCandidateCounts[index] = reader.readInt()
        }

        val candidateOrders = IntArray(candidateCount)
        val candidateSurfaceOffsets = Array(candidateCount) { IntArray(NGRAM_SECTION_COUNT) }
        val candidateSurfaceLengths = Array(candidateCount) { IntArray(NGRAM_SECTION_COUNT) }
        repeat(candidateCount) { index ->
            candidateOrders[index] = reader.readInt()
            require(candidateOrders[index] in 1..NGRAM_SECTION_COUNT) {
                "Invalid N-gram correction candidate order at index=$index: ${candidateOrders[index]}"
            }
            repeat(NGRAM_SECTION_COUNT) { surfaceIndex ->
                candidateSurfaceOffsets[index][surfaceIndex] = reader.readInt()
                candidateSurfaceLengths[index][surfaceIndex] = reader.readInt()
            }
        }

        val stringBytes = reader.readBytes(stringBytesLength)
        require(reader.isAtEnd()) { "Unexpected trailing bytes in N-gram correction data" }
        val readings = Array(groupCount) { index ->
            require(groupCandidateStarts[index] >= 0 && groupCandidateCounts[index] >= 0) {
                "Invalid N-gram correction candidate range at group=$index"
            }
            require(groupCandidateStarts[index] + groupCandidateCounts[index] <= candidateCount) {
                "N-gram correction candidate range exceeds table at group=$index"
            }
            stringBytes.decode(groupReadingOffsets[index], groupReadingLengths[index])
        }
        for (index in 1 until readings.size) {
            require(readings[index - 1] < readings[index]) {
                "N-gram correction readings must be strictly sorted at group=$index"
            }
        }
        val candidates = Array(candidateCount) { index ->
            val order = candidateOrders[index]
            val surfaces = (0 until order).map { surfaceIndex ->
                stringBytes.decode(candidateSurfaceOffsets[index][surfaceIndex], candidateSurfaceLengths[index][surfaceIndex])
            }
            NgramCorrectionCandidate(order = order, reading = "", surfaces = surfaces)
        }
        return LoadedNgramCorrectionDictionary(
            readings = readings,
            candidateStarts = groupCandidateStarts,
            candidateCounts = groupCandidateCounts,
            candidates = candidates,
            dictionaryBuildIdHex = buildId.toHex(),
            contentChecksumHex = contentChecksum.toHex(),
            byteSize = bytes.size.toLong(),
        )
    }
}

class LoadedNgramCorrectionDictionary(
    private val readings: Array<String>,
    private val candidateStarts: IntArray,
    private val candidateCounts: IntArray,
    private val candidates: Array<NgramCorrectionCandidate>,
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
) : BinaryNgramCorrectionDictionary {
    override fun lookup(reading: String): List<NgramCorrectionCandidate> {
        val index = readings.binarySearch(reading)
        if (index < 0) {
            return emptyList()
        }
        val start = candidateStarts[index]
        val count = candidateCounts[index]
        return List(count) { offset ->
            val candidate = candidates[start + offset]
            candidate.copy(reading = reading)
        }
    }

    override fun lookupBest(reading: String): NgramCorrectionCandidate? {
        val index = readings.binarySearch(reading)
        if (index < 0 || candidateCounts[index] == 0) {
            return null
        }
        return candidates[candidateStarts[index]].copy(reading = reading)
    }
}

object NgramCorrectionManifestWriter {
    fun write(outputPath: Path, manifest: NgramCorrectionManifest) {
        outputPath.parent?.createDirectories()
        Files.writeString(outputPath, toJson(manifest))
    }

    fun toJson(manifest: NgramCorrectionManifest): String = buildString {
        appendLine("{")
        appendLine("  \"format\": \"${manifest.format}\",")
        appendLine("  \"version\": ${manifest.version},")
        appendLine("  \"lookupMode\": ${jsonString(manifest.lookupMode)},")
        appendLine("  \"candidateOrder\": ${jsonString(manifest.candidateOrder)},")
        appendLine("  \"sourceFiles\": [${manifest.sourceFiles.joinToString(", ") { jsonString(it) }}],")
        appendLine("  \"sourceRowCount\": ${manifest.sourceRowCount},")
        appendLine("  \"candidateCount\": ${manifest.candidateCount},")
        appendLine("  \"readingCount\": ${manifest.readingCount},")
        appendLine("  \"duplicateCount\": ${manifest.duplicateCount},")
        appendLine("  \"skippedCount\": ${manifest.skippedCount},")
        appendLine("  \"entryCountByOrder\": {")
        (1..NGRAM_SECTION_COUNT).forEach { order ->
            val comma = if (order == NGRAM_SECTION_COUNT) "" else ","
            appendLine("    \"$order\": ${manifest.entryCountByOrder[order].orZero()}$comma")
        }
        appendLine("  },")
        appendLine("  \"dictionaryBuildId\": \"${manifest.dictionaryBuildId}\",")
        appendLine("  \"contentChecksum\": \"${manifest.contentChecksum}\",")
        appendLine("  \"byteSize\": ${manifest.byteSize}")
        appendLine("}")
    }

    private fun Int?.orZero(): Int = this ?: 0

    private fun jsonString(value: String): String = buildString {
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
}

object NgramCorrectionGenerator {
    fun generate(sourceDirectory: Path, outputDataPath: Path, outputManifestPath: Path): NgramCorrectionManifest {
        val compiled = NgramCorrectionCompiler.compile(sourceDirectory)
        val writeResult = NgramCorrectionDataWriter().write(outputDataPath, compiled.candidates)
        val manifest = NgramCorrectionManifest(
            format = NGRAM_CORRECTION_FORMAT,
            version = NGRAM_CORRECTION_VERSION,
            lookupMode = NGRAM_CORRECTION_LOOKUP_MODE,
            candidateOrder = NGRAM_CORRECTION_CANDIDATE_ORDER,
            sourceFiles = compiled.sourceReadResult.sourceFiles,
            sourceRowCount = compiled.sourceReadResult.sourceRowCount,
            candidateCount = compiled.candidates.size,
            readingCount = compiled.candidates.map { it.reading }.distinct().size,
            duplicateCount = compiled.duplicateCount,
            skippedCount = compiled.skippedCount,
            entryCountByOrder = compiled.candidates.groupingBy { it.order }.eachCount(),
            dictionaryBuildId = writeResult.dictionaryBuildIdHex,
            contentChecksum = writeResult.contentChecksumHex,
            byteSize = writeResult.byteSize,
        )
        NgramCorrectionManifestWriter.write(outputManifestPath, manifest)
        return manifest
    }
}

object NgramCorrectionVerifier {
    fun verify(sourceDirectory: Path, dataPath: Path): Int {
        val compiled = NgramCorrectionCompiler.compile(sourceDirectory)
        val dictionary = NgramCorrectionDataReader().read(dataPath)
        compiled.candidates.forEach { candidate ->
            val results = dictionary.lookup(candidate.reading)
            require(results.any { it.order == candidate.order && it.surfaces == candidate.surfaces }) {
                "Missing N-gram correction candidate: reading=${candidate.reading} surfaces=${candidate.surfaces}"
            }
        }
        val firstByReading = linkedMapOf<String, NgramCorrectionCandidate>()
        compiled.candidates.forEach { candidate -> firstByReading.putIfAbsent(candidate.reading, candidate) }
        firstByReading.forEach { (reading, expected) ->
            val best = dictionary.lookupBest(reading)
            require(best?.surfaces == expected.surfaces) {
                "Best N-gram correction candidate mismatch: reading=$reading expected=${expected.surfaces} actual=${best?.surfaces}"
            }
        }
        require(dictionary.lookup("\u0000missing-reading").isEmpty()) {
            "Unexpected N-gram correction hit for a missing reading"
        }
        return compiled.candidates.size
    }
}

object NgramCorrectionPerformanceProbe {
    fun run(sourceDirectory: Path, dataPath: Path): String {
        val runtime = Runtime.getRuntime()
        runtime.gc()
        val heapBefore = runtime.totalMemory() - runtime.freeMemory()
        val loadStart = System.nanoTime()
        val dictionary = NgramCorrectionDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart
        runtime.gc()
        val heapAfter = runtime.totalMemory() - runtime.freeMemory()

        val compiled = NgramCorrectionCompiler.compile(sourceDirectory)
        val readings = compiled.candidates.map { it.reading }.distinct().take(10_000)
        val probes = readings.ifEmpty { listOf("\u0000missing-reading") }
        var hitCount = 0
        val lookupStart = System.nanoTime()
        repeat(20) {
            probes.forEach { reading ->
                if (dictionary.lookupBest(reading) != null) {
                    hitCount += 1
                }
            }
        }
        val lookupCount = probes.size * 20L
        val lookupNanos = System.nanoTime() - lookupStart
        val verifyStart = System.nanoTime()
        val verifiedEntryCount = NgramCorrectionVerifier.verify(sourceDirectory, dataPath)
        val verifyNanos = System.nanoTime() - verifyStart

        return buildString {
            appendLine("ngram_correction_probe:")
            appendLine("  binarySizeBytes=${Files.size(dataPath)}")
            appendLine("  loadTimeMs=${loadNanos / 1_000_000.0}")
            appendLine("  heapDeltaBytes=${heapAfter - heapBefore}")
            appendLine("  lookupBestNsOp=${lookupNanos.toDouble() / lookupCount}")
            appendLine("  lookupCount=$lookupCount")
            appendLine("  lookupHitCount=$hitCount")
            appendLine("  readingCount=${compiled.candidates.map { it.reading }.distinct().size}")
            appendLine("  candidateCount=${compiled.candidates.size}")
            appendLine("  verificationTimeMs=${verifyNanos / 1_000_000.0}")
            appendLine("  verifiedEntryCount=$verifiedEntryCount")
        }
    }
}

private data class CorrectionStringRef(val offset: Int, val length: Int)

private class CorrectionStringPool {
    private val bytes = ArrayList<Byte>()
    private val refs = linkedMapOf<String, CorrectionStringRef>()

    val byteSize: Int
        get() = bytes.size

    fun put(value: String) {
        if (value in refs) {
            return
        }
        val encoded = value.toByteArray(Charsets.UTF_8)
        refs[value] = CorrectionStringRef(bytes.size, encoded.size)
        encoded.forEach { bytes += it }
    }

    fun ref(value: String): CorrectionStringRef = refs.getValue(value)

    fun toByteArray(): ByteArray = ByteArray(bytes.size) { bytes[it] }
}

private class CorrectionLeWriter {
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

private class CorrectionLeReader(private val bytes: ByteArray) {
    private var offset = 0

    fun readAscii(length: Int): String = readBytes(length).toString(Charsets.US_ASCII)

    fun readBytes(length: Int): ByteArray {
        require(offset + length <= bytes.size) { "Unexpected end of N-gram correction data" }
        return bytes.copyOfRange(offset, offset + length).also { offset += length }
    }

    fun readInt(): Int {
        require(offset + Int.SIZE_BYTES <= bytes.size) { "Unexpected end of N-gram correction data" }
        var result = 0
        repeat(Int.SIZE_BYTES) { shift ->
            result = result or ((bytes[offset++].toInt() and 0xff) shl (shift * 8))
        }
        return result
    }

    fun isAtEnd(): Boolean = offset == bytes.size
}

private fun ByteArray.decode(offset: Int, length: Int): String {
    require(offset >= 0 && length >= 0 && offset + length <= size) {
        "Invalid N-gram correction string bounds: offset=$offset length=$length size=$size"
    }
    return copyOfRange(offset, offset + length).toString(Charsets.UTF_8)
}

private fun MessageDigest.updateInt(value: Int) {
    update(byteArrayOf(
        (value and 0xff).toByte(),
        ((value ushr 8) and 0xff).toByte(),
        ((value ushr 16) and 0xff).toByte(),
        ((value ushr 24) and 0xff).toByte(),
    ))
}

private fun MessageDigest.updateUtf8(value: String) {
    val bytes = value.toByteArray(Charsets.UTF_8)
    updateInt(bytes.size)
    update(bytes)
}

private fun checksum(bytesWithZeroChecksum: ByteArray): ByteArray =
    MessageDigest.getInstance("SHA-256").digest(bytesWithZeroChecksum)

private const val CORRECTION_MAGIC = "NGC1"
private const val SHA_256_BYTES = 32
private const val CORRECTION_BUILD_ID_OFFSET = 4 + Int.SIZE_BYTES * 4
private const val CORRECTION_CHECKSUM_OFFSET = CORRECTION_BUILD_ID_OFFSET + SHA_256_BYTES
private const val CORRECTION_HEADER_SIZE = 4 + Int.SIZE_BYTES * 4 + SHA_256_BYTES + SHA_256_BYTES
