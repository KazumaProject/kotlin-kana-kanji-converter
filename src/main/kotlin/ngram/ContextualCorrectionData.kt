package com.kazumaproject.ngram

import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.text.Normalizer
import kotlin.io.path.createDirectories
import kotlin.io.path.invariantSeparatorsPathString
import kotlin.io.path.isRegularFile
import kotlin.io.path.name

const val CONTEXTUAL_CORRECTION_FORMAT = "CONTEXTUAL_CORRECTION_EXACT"
const val CONTEXTUAL_CORRECTION_VERSION = 1
const val CONTEXTUAL_CORRECTION_LOOKUP_MODE = "TOKEN_SEQUENCE_PATTERN_EXACT_WITH_COARSE_CLASS_SLOT"
const val CONTEXTUAL_CORRECTION_CANDIDATE_ORDER = "source_manifest_order_then_source_row_order"

data class ContextualCorrectionToken(
    val reading: String,
    val surface: String,
    val coarseClass: ContextualCorrectionCoarseClass,
)

enum class ContextualCorrectionCoarseClass(val id: Int) {
    ANY(0),
    NOUN(1),
    PARTICLE(2),
    VERB(3),
    AUX(4),
    SYMBOL(5),
    UNKNOWN(6);

    companion object {
        fun fromId(id: Int): ContextualCorrectionCoarseClass =
            entries.firstOrNull { it.id == id } ?: error("Unknown contextual correction class id: $id")

        fun parse(value: String): ContextualCorrectionCoarseClass =
            entries.firstOrNull { it.name == value.trim().uppercase() }
                ?: error("Unknown contextual correction coarse class: $value")
    }
}

data class ContextualCorrectionCandidate(
    val ruleId: String,
    val surfaces: List<String>,
    val targetIndex: Int,
    val replacementSurface: String,
) {
    val surfaceText: String
        get() = surfaces.joinToString("")
}

interface BinaryContextualCorrectionDictionary {
    fun lookup(tokens: List<ContextualCorrectionToken>): List<ContextualCorrectionCandidate>
    fun lookupBest(tokens: List<ContextualCorrectionToken>): ContextualCorrectionCandidate? =
        lookup(tokens).firstOrNull()
}

object EmptyBinaryContextualCorrectionDictionary : BinaryContextualCorrectionDictionary {
    override fun lookup(tokens: List<ContextualCorrectionToken>): List<ContextualCorrectionCandidate> = emptyList()
}

data class ContextualCorrectionSourceRule(
    val id: String,
    val pattern: String,
    val source: String,
    val comment: String,
    val sourceFile: String,
    val lineNumber: Int,
)

data class ContextualCorrectionPatternItem(
    val kind: ContextualCorrectionPatternKind,
    val reading: String,
    val surface: String,
    val replacementSurface: String,
    val coarseClass: ContextualCorrectionCoarseClass,
)

enum class ContextualCorrectionPatternKind(val id: Int) {
    LITERAL(1),
    SLOT(2),
    TARGET(3);

    companion object {
        fun fromId(id: Int): ContextualCorrectionPatternKind =
            entries.firstOrNull { it.id == id } ?: error("Unknown contextual correction pattern kind id: $id")
    }
}

data class ContextualCorrectionRule(
    val id: String,
    val items: List<ContextualCorrectionPatternItem>,
    val sourceFile: String,
    val lineNumber: Int,
) {
    val targetIndex: Int
        get() = items.indexOfFirst { it.kind == ContextualCorrectionPatternKind.TARGET }
}

data class ContextualCorrectionSourceReadResult(
    val rules: List<ContextualCorrectionSourceRule>,
    val sourceFiles: List<String>,
    val sourceRowCount: Int,
)

data class ContextualCorrectionCompiledData(
    val sourceReadResult: ContextualCorrectionSourceReadResult,
    val rules: List<ContextualCorrectionRule>,
    val duplicateCount: Int,
    val skippedCount: Int,
)

data class ContextualCorrectionManifest(
    val format: String,
    val version: Int,
    val lookupMode: String,
    val candidateOrder: String,
    val sourceFiles: List<String>,
    val sourceRowCount: Int,
    val ruleCount: Int,
    val duplicateCount: Int,
    val skippedCount: Int,
    val ruleCountByLength: Map<Int, Int>,
    val dictionaryBuildId: String,
    val contentChecksum: String,
    val byteSize: Long,
)

data class ContextualCorrectionWriteResult(
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
)

object ContextualCorrectionSourceTsvReader {
    fun readDirectory(sourceDirectory: Path): ContextualCorrectionSourceReadResult {
        require(Files.isDirectory(sourceDirectory)) {
            "Contextual correction source directory does not exist: $sourceDirectory"
        }
        val sourceSet = ContextualCorrectionSourceSetManifestReader.read(sourceDirectory)
        val files = sourceSet.enabledFiles.map { sourceDirectory.resolve(it).normalize() }
        return readFiles(files, sourceDirectory)
    }

    fun readFiles(files: List<Path>, sourceRoot: Path? = null): ContextualCorrectionSourceReadResult {
        val rules = mutableListOf<ContextualCorrectionSourceRule>()
        val sourceFiles = mutableListOf<String>()
        var sourceRowCount = 0
        files.forEach { file ->
            require(file.isRegularFile()) { "Contextual correction source TSV does not exist: $file" }
            val sourceName = sourceRoot?.relativize(file)?.toString()?.replace('\\', '/') ?: file.name
            sourceFiles += sourceName
            val rows = Files.readAllLines(file)
            if (rows.isEmpty()) return@forEach
            val header = splitPreservingEmpty(rows.first(), '\t')
                .map { it.trim().lowercase() }
                .withIndex()
                .associate { it.value to it.index }
            listOf("id", "pattern").forEach { column ->
                require(column in header) {
                    "Contextual correction source header is missing '$column': file=$file"
                }
            }
            rows.drop(1).forEachIndexed { index, rawLine ->
                val lineNumber = index + 2
                if (rawLine.isBlank() || rawLine.trimStart().startsWith("#")) return@forEachIndexed
                sourceRowCount += 1
                val columns = splitPreservingEmpty(rawLine, '\t')
                fun value(name: String): String = columns.getOrElse(header[name] ?: -1) { "" }
                rules += ContextualCorrectionSourceRule(
                    id = value("id"),
                    pattern = value("pattern"),
                    source = value("source"),
                    comment = value("comment"),
                    sourceFile = sourceName,
                    lineNumber = lineNumber,
                )
            }
        }
        return ContextualCorrectionSourceReadResult(
            rules = rules,
            sourceFiles = sourceFiles,
            sourceRowCount = sourceRowCount,
        )
    }
}

data class ContextualCorrectionSourceSetEntry(
    val enabled: Boolean,
    val file: String,
    val kind: String,
    val description: String,
    val lineNumber: Int,
)

data class ContextualCorrectionSourceSet(
    val entries: List<ContextualCorrectionSourceSetEntry>,
) {
    val enabledFiles: List<String>
        get() = entries.filter { it.enabled }.map { it.file }
}

object ContextualCorrectionSourceSetManifestReader {
    private const val MANIFEST = "sources_manifest.tsv"

    fun read(sourceDirectory: Path): ContextualCorrectionSourceSet {
        val manifest = sourceDirectory.resolve(MANIFEST)
        require(manifest.isRegularFile()) { "Missing contextual correction source manifest: $manifest" }
        val rows = Files.readAllLines(manifest)
        require(rows.isNotEmpty()) { "Contextual correction source manifest is empty: $manifest" }
        val header = splitPreservingEmpty(rows.first(), '\t')
            .map { it.trim().lowercase() }
            .withIndex()
            .associate { it.value to it.index }
        listOf("enabled", "file", "kind", "description").forEach { column ->
            require(column in header) {
                "Contextual correction source manifest is missing column '$column': $manifest"
            }
        }
        val entries = rows.drop(1).mapIndexedNotNull { index, rawLine ->
            val lineNumber = index + 2
            if (rawLine.isBlank() || rawLine.trimStart().startsWith("#")) return@mapIndexedNotNull null
            val columns = splitPreservingEmpty(rawLine, '\t')
            fun value(name: String): String = columns.getOrElse(header.getValue(name)) { "" }.trim()
            ContextualCorrectionSourceSetEntry(
                enabled = parseEnabled(value("enabled"), manifest, lineNumber),
                file = normalizeManifestPath(value("file"), manifest, lineNumber),
                kind = value("kind"),
                description = value("description"),
                lineNumber = lineNumber,
            )
        }
        val seen = mutableSetOf<String>()
        entries.forEach { entry ->
            require(seen.add(entry.file)) {
                "Duplicate contextual correction source manifest file entry: file=${entry.file}"
            }
            require(entry.kind == "contextual_correction") {
                "Unsupported contextual correction source kind at $manifest:${entry.lineNumber}: ${entry.kind}"
            }
            val sourceFile = sourceDirectory.resolve(entry.file).normalize()
            require(sourceFile.startsWith(sourceDirectory.normalize())) {
                "Contextual correction source path escapes source directory at $manifest:${entry.lineNumber}: ${entry.file}"
            }
            require(sourceFile.isRegularFile()) {
                "Contextual correction source manifest references missing file at $manifest:${entry.lineNumber}: ${entry.file}"
            }
        }
        require(entries.any { it.enabled }) { "Contextual correction source manifest has no enabled files: $manifest" }
        return ContextualCorrectionSourceSet(entries)
    }

    private fun parseEnabled(value: String, manifest: Path, lineNumber: Int): Boolean =
        when (value.lowercase()) {
            "true", "1", "yes", "y", "enabled" -> true
            "false", "0", "no", "n", "disabled" -> false
            else -> error("Invalid enabled value at $manifest:$lineNumber: $value")
        }

    private fun normalizeManifestPath(value: String, manifest: Path, lineNumber: Int): String {
        require(value.isNotBlank()) { "file must not be blank at $manifest:$lineNumber" }
        require(value.endsWith(".tsv")) { "Contextual correction source file must end with .tsv at $manifest:$lineNumber: $value" }
        require(value != MANIFEST) { "Contextual correction source manifest cannot include itself at $manifest:$lineNumber" }
        val path = Path.of(value)
        require(!path.isAbsolute) { "Contextual correction source file must be relative at $manifest:$lineNumber: $value" }
        require(path.none { it.toString() == ".." }) {
            "Contextual correction source file must not contain '..' at $manifest:$lineNumber: $value"
        }
        return path.invariantSeparatorsPathString
    }
}

object ContextualCorrectionRuleParser {
    fun parse(rule: ContextualCorrectionSourceRule): ContextualCorrectionRule {
        val id = normalizeText(rule.id)
        require(id.matches(Regex("[A-Za-z0-9_.-]+"))) {
            "Invalid contextual correction rule id at ${rule.sourceFile}:${rule.lineNumber}: ${rule.id}"
        }
        val items = rule.pattern.trim()
            .split(Regex("\\s+"))
            .filter { it.isNotBlank() }
            .map { parseItem(it, rule) }
        require(items.isNotEmpty()) {
            "Contextual correction pattern is empty at ${rule.sourceFile}:${rule.lineNumber}"
        }
        require(items.size <= CONTEXTUAL_CORRECTION_MAX_PATTERN_LENGTH) {
            "Contextual correction pattern is too long at ${rule.sourceFile}:${rule.lineNumber}: ${items.size}"
        }
        require(items.first().kind != ContextualCorrectionPatternKind.SLOT) {
            "Contextual correction first pattern item must be lit(...) or target(...) for indexed lookup: ${rule.sourceFile}:${rule.lineNumber}"
        }
        require(items.count { it.kind == ContextualCorrectionPatternKind.TARGET } == 1) {
            "Contextual correction pattern must contain exactly one target(...) at ${rule.sourceFile}:${rule.lineNumber}"
        }
        return ContextualCorrectionRule(
            id = id,
            items = items,
            sourceFile = rule.sourceFile,
            lineNumber = rule.lineNumber,
        )
    }

    private fun parseItem(value: String, rule: ContextualCorrectionSourceRule): ContextualCorrectionPatternItem {
        val open = value.indexOf('(')
        require(open > 0 && value.endsWith(")")) {
            "Invalid contextual correction pattern item at ${rule.sourceFile}:${rule.lineNumber}: $value"
        }
        val name = value.substring(0, open)
        val args = value.substring(open + 1, value.length - 1)
            .split(',')
            .map { normalizeText(it) }
        return when (name) {
            "lit" -> {
                require(args.size == 2 && args.all { it.isNotEmpty() }) {
                    "lit(...) expects reading,surface at ${rule.sourceFile}:${rule.lineNumber}: $value"
                }
                ContextualCorrectionPatternItem(
                    kind = ContextualCorrectionPatternKind.LITERAL,
                    reading = args[0],
                    surface = args[1],
                    replacementSurface = "",
                    coarseClass = ContextualCorrectionCoarseClass.ANY,
                )
            }
            "slot" -> {
                require(args.size in 1..2) {
                    "slot(...) expects class or name,class at ${rule.sourceFile}:${rule.lineNumber}: $value"
                }
                val classText = args.last()
                ContextualCorrectionPatternItem(
                    kind = ContextualCorrectionPatternKind.SLOT,
                    reading = "",
                    surface = "",
                    replacementSurface = "",
                    coarseClass = ContextualCorrectionCoarseClass.parse(classText),
                )
            }
            "target" -> {
                require(args.size == 3 && args.all { it.isNotEmpty() }) {
                    "target(...) expects reading,fromSurface,toSurface at ${rule.sourceFile}:${rule.lineNumber}: $value"
                }
                ContextualCorrectionPatternItem(
                    kind = ContextualCorrectionPatternKind.TARGET,
                    reading = args[0],
                    surface = args[1],
                    replacementSurface = args[2],
                    coarseClass = ContextualCorrectionCoarseClass.ANY,
                )
            }
            else -> error("Unknown contextual correction pattern item '$name' at ${rule.sourceFile}:${rule.lineNumber}")
        }
    }

    private fun normalizeText(value: String): String = Normalizer.normalize(value.trim(), Normalizer.Form.NFC)
}

object ContextualCorrectionCompiler {
    fun compile(sourceDirectory: Path): ContextualCorrectionCompiledData {
        val sourceReadResult = ContextualCorrectionSourceTsvReader.readDirectory(sourceDirectory)
        val rules = mutableListOf<ContextualCorrectionRule>()
        val seenKeys = linkedSetOf<String>()
        val seenIds = linkedMapOf<String, String>()
        var duplicateCount = 0
        sourceReadResult.rules.forEach { sourceRule ->
            val rule = ContextualCorrectionRuleParser.parse(sourceRule)
            val key = rule.key()
            val previousKeyForId = seenIds.putIfAbsent(rule.id, key)
            require(previousKeyForId == null || previousKeyForId == key) {
                "Conflicting contextual correction rule id: id=${rule.id}, firstKey=$previousKeyForId, secondKey=$key"
            }
            if (!seenKeys.add(key)) {
                duplicateCount += 1
            } else {
                rules += rule
            }
        }
        return ContextualCorrectionCompiledData(
            sourceReadResult = sourceReadResult,
            rules = rules,
            duplicateCount = duplicateCount,
            skippedCount = 0,
        )
    }

    private fun ContextualCorrectionRule.key(): String =
        buildString {
            append(id)
            items.forEach { item ->
                append('|')
                append(item.kind.name)
                append(':')
                append(item.reading)
                append(':')
                append(item.surface)
                append(':')
                append(item.replacementSurface)
                append(':')
                append(item.coarseClass.name)
            }
        }
}

class ContextualCorrectionDataWriter {
    fun write(outputPath: Path, rules: List<ContextualCorrectionRule>): ContextualCorrectionWriteResult {
        outputPath.parent?.createDirectories()
        val bytes = toByteArray(rules)
        Files.write(outputPath, bytes)
        return ContextualCorrectionWriteResult(
            dictionaryBuildIdHex = bytes.copyOfRange(CTX_BUILD_ID_OFFSET, CTX_BUILD_ID_OFFSET + CTX_SHA_256_BYTES).toHex(),
            contentChecksumHex = bytes.copyOfRange(CTX_CHECKSUM_OFFSET, CTX_CHECKSUM_OFFSET + CTX_SHA_256_BYTES).toHex(),
            byteSize = bytes.size.toLong(),
        )
    }

    fun toByteArray(rules: List<ContextualCorrectionRule>): ByteArray {
        rules.forEach(::requireValidRule)
        val orderedRules = rules.withIndex()
            .sortedWith(
                compareBy<IndexedValue<ContextualCorrectionRule>> { it.value.items.first().reading }
                    .thenBy { it.index }
            )
            .map { it.value }
        val groups = orderedRules
            .withIndex()
            .groupBy({ it.value.items.first().reading }, { it.index })
            .toSortedMap()
        val patternItems = orderedRules.flatMap { it.items }
        val stringPool = ContextualCorrectionStringPool()
        groups.keys.forEach(stringPool::put)
        orderedRules.forEach { rule -> stringPool.put(rule.id) }
        patternItems.forEach { item ->
            stringPool.put(item.reading)
            stringPool.put(item.surface)
            stringPool.put(item.replacementSurface)
        }
        val buildId = buildId(orderedRules)

        val writer = ContextualCorrectionLeWriter()
        writer.writeAscii(CTX_MAGIC)
        writer.writeInt(CONTEXTUAL_CORRECTION_VERSION)
        writer.writeInt(groups.size)
        writer.writeInt(orderedRules.size)
        writer.writeInt(patternItems.size)
        writer.writeInt(stringPool.byteSize)
        writer.writeBytes(buildId)
        writer.writeBytes(ByteArray(CTX_SHA_256_BYTES))

        groups.forEach { (anchor, indexes) ->
            val ref = stringPool.ref(anchor)
            writer.writeInt(ref.offset)
            writer.writeInt(ref.length)
            writer.writeInt(indexes.first())
            writer.writeInt(indexes.size)
        }

        var patternStart = 0
        orderedRules.forEach { rule ->
            val idRef = stringPool.ref(rule.id)
            writer.writeInt(idRef.offset)
            writer.writeInt(idRef.length)
            writer.writeInt(patternStart)
            writer.writeInt(rule.items.size)
            writer.writeInt(rule.targetIndex)
            patternStart += rule.items.size
        }

        patternItems.forEach { item ->
            writer.writeInt(item.kind.id)
            writer.writeInt(item.coarseClass.id)
            listOf(item.reading, item.surface, item.replacementSurface).forEach { value ->
                val ref = stringPool.ref(value)
                writer.writeInt(ref.offset)
                writer.writeInt(ref.length)
            }
        }
        writer.writeBytes(stringPool.toByteArray())

        val bytes = writer.toByteArray()
        buildId.copyInto(bytes, CTX_BUILD_ID_OFFSET)
        val checksum = contextualCorrectionChecksum(bytes)
        checksum.copyInto(bytes, CTX_CHECKSUM_OFFSET)
        return bytes
    }

    private fun buildId(rules: List<ContextualCorrectionRule>): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update("CTX1-build-v1".toByteArray(Charsets.US_ASCII))
        rules.forEach { rule ->
            digest.updateUtf8(rule.id)
            rule.items.forEach { item ->
                digest.updateInt(item.kind.id)
                digest.updateInt(item.coarseClass.id)
                digest.updateUtf8(item.reading)
                digest.updateUtf8(item.surface)
                digest.updateUtf8(item.replacementSurface)
            }
        }
        return digest.digest()
    }

    private fun requireValidRule(rule: ContextualCorrectionRule) {
        require(rule.id.isNotEmpty()) { "Contextual correction rule id must not be empty" }
        require(rule.items.size in 1..CONTEXTUAL_CORRECTION_MAX_PATTERN_LENGTH) {
            "Contextual correction pattern length must be 1..$CONTEXTUAL_CORRECTION_MAX_PATTERN_LENGTH: ${rule.items.size}"
        }
        require(rule.items.first().kind != ContextualCorrectionPatternKind.SLOT) {
            "Contextual correction first pattern item must be indexed by reading"
        }
        require(rule.targetIndex in rule.items.indices) { "Contextual correction target index is invalid: ${rule.targetIndex}" }
        require(rule.items.count { it.kind == ContextualCorrectionPatternKind.TARGET } == 1) {
            "Contextual correction rule must contain exactly one target item: ${rule.id}"
        }
    }
}

class ContextualCorrectionDataReader {
    fun read(inputPath: Path, verifyChecksum: Boolean = true): LoadedContextualCorrectionDictionary {
        require(Files.isRegularFile(inputPath)) { "Contextual correction data does not exist: $inputPath" }
        return readBytes(Files.readAllBytes(inputPath), verifyChecksum)
    }

    fun readBytes(bytes: ByteArray, verifyChecksum: Boolean = true): LoadedContextualCorrectionDictionary {
        require(bytes.size >= CTX_HEADER_SIZE) { "Contextual correction data is too small: ${bytes.size}" }
        if (verifyChecksum) {
            val expected = bytes.copyOfRange(CTX_CHECKSUM_OFFSET, CTX_CHECKSUM_OFFSET + CTX_SHA_256_BYTES)
            val actualInput = bytes.copyOf()
            actualInput.fill(0, CTX_CHECKSUM_OFFSET, CTX_CHECKSUM_OFFSET + CTX_SHA_256_BYTES)
            val actual = contextualCorrectionChecksum(actualInput)
            require(expected.contentEquals(actual)) {
                "Contextual correction checksum mismatch: expected=${expected.toHex()} actual=${actual.toHex()}"
            }
        }

        val reader = ContextualCorrectionLeReader(bytes)
        require(reader.readAscii(4) == CTX_MAGIC) { "Invalid contextual correction magic" }
        val version = reader.readInt()
        require(version == CONTEXTUAL_CORRECTION_VERSION) { "Unsupported contextual correction version: $version" }
        val groupCount = reader.readInt()
        val ruleCount = reader.readInt()
        val itemCount = reader.readInt()
        val stringBytesLength = reader.readInt()
        require(groupCount >= 0 && ruleCount >= 0 && itemCount >= 0 && stringBytesLength >= 0) {
            "Invalid contextual correction table counts"
        }
        val buildId = reader.readBytes(CTX_SHA_256_BYTES)
        val checksum = reader.readBytes(CTX_SHA_256_BYTES)

        val groupReadingOffsets = IntArray(groupCount)
        val groupReadingLengths = IntArray(groupCount)
        val groupRuleStarts = IntArray(groupCount)
        val groupRuleCounts = IntArray(groupCount)
        repeat(groupCount) { index ->
            groupReadingOffsets[index] = reader.readInt()
            groupReadingLengths[index] = reader.readInt()
            groupRuleStarts[index] = reader.readInt()
            groupRuleCounts[index] = reader.readInt()
        }

        val ruleIdOffsets = IntArray(ruleCount)
        val ruleIdLengths = IntArray(ruleCount)
        val ruleItemStarts = IntArray(ruleCount)
        val ruleItemCounts = IntArray(ruleCount)
        val ruleTargetIndexes = IntArray(ruleCount)
        repeat(ruleCount) { index ->
            ruleIdOffsets[index] = reader.readInt()
            ruleIdLengths[index] = reader.readInt()
            ruleItemStarts[index] = reader.readInt()
            ruleItemCounts[index] = reader.readInt()
            ruleTargetIndexes[index] = reader.readInt()
        }

        val itemKinds = IntArray(itemCount)
        val itemClasses = IntArray(itemCount)
        val itemReadingOffsets = IntArray(itemCount)
        val itemReadingLengths = IntArray(itemCount)
        val itemSurfaceOffsets = IntArray(itemCount)
        val itemSurfaceLengths = IntArray(itemCount)
        val itemReplacementOffsets = IntArray(itemCount)
        val itemReplacementLengths = IntArray(itemCount)
        repeat(itemCount) { index ->
            itemKinds[index] = reader.readInt()
            itemClasses[index] = reader.readInt()
            itemReadingOffsets[index] = reader.readInt()
            itemReadingLengths[index] = reader.readInt()
            itemSurfaceOffsets[index] = reader.readInt()
            itemSurfaceLengths[index] = reader.readInt()
            itemReplacementOffsets[index] = reader.readInt()
            itemReplacementLengths[index] = reader.readInt()
        }
        val stringBytes = reader.readBytes(stringBytesLength)
        require(reader.isAtEnd()) { "Unexpected trailing bytes in contextual correction data" }

        val groupReadings = Array(groupCount) { index ->
            require(groupRuleStarts[index] >= 0 && groupRuleCounts[index] >= 0) {
                "Invalid contextual correction rule range at group=$index"
            }
            require(groupRuleStarts[index] + groupRuleCounts[index] <= ruleCount) {
                "Contextual correction rule range exceeds table at group=$index"
            }
            stringBytes.decodeContextString(groupReadingOffsets[index], groupReadingLengths[index])
        }
        for (index in 1 until groupReadings.size) {
            require(groupReadings[index - 1] < groupReadings[index]) {
                "Contextual correction group readings must be strictly sorted at group=$index"
            }
        }
        val ruleIds = Array(ruleCount) { index ->
            require(ruleItemStarts[index] >= 0 && ruleItemCounts[index] >= 0) {
                "Invalid contextual correction item range at rule=$index"
            }
            require(ruleItemStarts[index] + ruleItemCounts[index] <= itemCount) {
                "Contextual correction item range exceeds table at rule=$index"
            }
            require(ruleTargetIndexes[index] in 0 until ruleItemCounts[index]) {
                "Invalid contextual correction target index at rule=$index"
            }
            stringBytes.decodeContextString(ruleIdOffsets[index], ruleIdLengths[index])
        }
        val itemReadings = Array(itemCount) { index ->
            stringBytes.decodeContextString(itemReadingOffsets[index], itemReadingLengths[index])
        }
        val itemSurfaces = Array(itemCount) { index ->
            stringBytes.decodeContextString(itemSurfaceOffsets[index], itemSurfaceLengths[index])
        }
        val itemReplacements = Array(itemCount) { index ->
            stringBytes.decodeContextString(itemReplacementOffsets[index], itemReplacementLengths[index])
        }

        return LoadedContextualCorrectionDictionary(
            groupReadings = groupReadings,
            groupRuleStarts = groupRuleStarts,
            groupRuleCounts = groupRuleCounts,
            ruleIds = ruleIds,
            ruleItemStarts = ruleItemStarts,
            ruleItemCounts = ruleItemCounts,
            ruleTargetIndexes = ruleTargetIndexes,
            itemKinds = itemKinds,
            itemClasses = itemClasses,
            itemReadings = itemReadings,
            itemSurfaces = itemSurfaces,
            itemReplacements = itemReplacements,
            dictionaryBuildIdHex = buildId.toHex(),
            contentChecksumHex = checksum.toHex(),
            byteSize = bytes.size.toLong(),
        )
    }
}

class LoadedContextualCorrectionDictionary(
    private val groupReadings: Array<String>,
    private val groupRuleStarts: IntArray,
    private val groupRuleCounts: IntArray,
    private val ruleIds: Array<String>,
    private val ruleItemStarts: IntArray,
    private val ruleItemCounts: IntArray,
    private val ruleTargetIndexes: IntArray,
    private val itemKinds: IntArray,
    private val itemClasses: IntArray,
    private val itemReadings: Array<String>,
    private val itemSurfaces: Array<String>,
    private val itemReplacements: Array<String>,
    val dictionaryBuildIdHex: String,
    val contentChecksumHex: String,
    val byteSize: Long,
) : BinaryContextualCorrectionDictionary {
    override fun lookup(tokens: List<ContextualCorrectionToken>): List<ContextualCorrectionCandidate> {
        if (tokens.isEmpty()) return emptyList()
        val groupIndex = groupReadings.binarySearch(tokens.first().reading)
        if (groupIndex < 0) return emptyList()
        val start = groupRuleStarts[groupIndex]
        val end = start + groupRuleCounts[groupIndex]
        val results = mutableListOf<ContextualCorrectionCandidate>()
        for (ruleIndex in start until end) {
            matchRule(ruleIndex, tokens)?.let { results += it }
        }
        return results
    }

    override fun lookupBest(tokens: List<ContextualCorrectionToken>): ContextualCorrectionCandidate? {
        if (tokens.isEmpty()) return null
        val groupIndex = groupReadings.binarySearch(tokens.first().reading)
        if (groupIndex < 0) return null
        val start = groupRuleStarts[groupIndex]
        val end = start + groupRuleCounts[groupIndex]
        for (ruleIndex in start until end) {
            matchRule(ruleIndex, tokens)?.let { return it }
        }
        return null
    }

    private fun matchRule(ruleIndex: Int, tokens: List<ContextualCorrectionToken>): ContextualCorrectionCandidate? {
        val itemStart = ruleItemStarts[ruleIndex]
        val itemCount = ruleItemCounts[ruleIndex]
        if (tokens.size != itemCount) return null
        var absoluteTargetIndex = -1
        var replacement = ""
        for (offset in 0 until itemCount) {
            val itemIndex = itemStart + offset
            when (itemKinds[itemIndex]) {
                ContextualCorrectionPatternKind.LITERAL.id -> {
                    if (tokens[offset].reading != itemReadings[itemIndex]) return null
                    if (tokens[offset].surface != itemSurfaces[itemIndex]) return null
                }
                ContextualCorrectionPatternKind.SLOT.id -> {
                    val expectedClassId = itemClasses[itemIndex]
                    if (expectedClassId != ContextualCorrectionCoarseClass.ANY.id &&
                        tokens[offset].coarseClass.id != expectedClassId
                    ) {
                        return null
                    }
                }
                ContextualCorrectionPatternKind.TARGET.id -> {
                    if (tokens[offset].reading != itemReadings[itemIndex]) return null
                    if (tokens[offset].surface != itemSurfaces[itemIndex]) return null
                    absoluteTargetIndex = offset
                    replacement = itemReplacements[itemIndex]
                }
                else -> return null
            }
        }
        if (absoluteTargetIndex != ruleTargetIndexes[ruleIndex]) return null
        val surfaces = tokens.mapIndexed { index, token ->
            if (index == absoluteTargetIndex) replacement else token.surface
        }
        return ContextualCorrectionCandidate(
            ruleId = ruleIds[ruleIndex],
            surfaces = surfaces,
            targetIndex = absoluteTargetIndex,
            replacementSurface = replacement,
        )
    }
}

object ContextualCorrectionManifestWriter {
    fun write(outputPath: Path, manifest: ContextualCorrectionManifest) {
        outputPath.parent?.createDirectories()
        Files.writeString(outputPath, toJson(manifest))
    }

    fun toJson(manifest: ContextualCorrectionManifest): String = buildString {
        appendLine("{")
        appendLine("  \"format\": ${contextJsonString(manifest.format)},")
        appendLine("  \"version\": ${manifest.version},")
        appendLine("  \"lookupMode\": ${contextJsonString(manifest.lookupMode)},")
        appendLine("  \"candidateOrder\": ${contextJsonString(manifest.candidateOrder)},")
        appendLine("  \"sourceFiles\": [${manifest.sourceFiles.joinToString(", ") { contextJsonString(it) }}],")
        appendLine("  \"sourceRowCount\": ${manifest.sourceRowCount},")
        appendLine("  \"ruleCount\": ${manifest.ruleCount},")
        appendLine("  \"duplicateCount\": ${manifest.duplicateCount},")
        appendLine("  \"skippedCount\": ${manifest.skippedCount},")
        appendLine("  \"ruleCountByLength\": {")
        (1..CONTEXTUAL_CORRECTION_MAX_PATTERN_LENGTH).forEach { length ->
            val comma = if (length == CONTEXTUAL_CORRECTION_MAX_PATTERN_LENGTH) "" else ","
            appendLine("    \"$length\": ${manifest.ruleCountByLength[length] ?: 0}$comma")
        }
        appendLine("  },")
        appendLine("  \"dictionaryBuildId\": ${contextJsonString(manifest.dictionaryBuildId)},")
        appendLine("  \"contentChecksum\": ${contextJsonString(manifest.contentChecksum)},")
        appendLine("  \"byteSize\": ${manifest.byteSize}")
        appendLine("}")
    }
}

object ContextualCorrectionGenerator {
    fun generate(sourceDirectory: Path, outputDataPath: Path, outputManifestPath: Path): ContextualCorrectionManifest {
        val compiled = ContextualCorrectionCompiler.compile(sourceDirectory)
        val writeResult = ContextualCorrectionDataWriter().write(outputDataPath, compiled.rules)
        val manifest = ContextualCorrectionManifest(
            format = CONTEXTUAL_CORRECTION_FORMAT,
            version = CONTEXTUAL_CORRECTION_VERSION,
            lookupMode = CONTEXTUAL_CORRECTION_LOOKUP_MODE,
            candidateOrder = CONTEXTUAL_CORRECTION_CANDIDATE_ORDER,
            sourceFiles = compiled.sourceReadResult.sourceFiles,
            sourceRowCount = compiled.sourceReadResult.sourceRowCount,
            ruleCount = compiled.rules.size,
            duplicateCount = compiled.duplicateCount,
            skippedCount = compiled.skippedCount,
            ruleCountByLength = compiled.rules.groupingBy { it.items.size }.eachCount(),
            dictionaryBuildId = writeResult.dictionaryBuildIdHex,
            contentChecksum = writeResult.contentChecksumHex,
            byteSize = writeResult.byteSize,
        )
        ContextualCorrectionManifestWriter.write(outputManifestPath, manifest)
        return manifest
    }
}

object ContextualCorrectionVerifier {
    fun verify(sourceDirectory: Path, dataPath: Path): Int {
        val compiled = ContextualCorrectionCompiler.compile(sourceDirectory)
        val dictionary = ContextualCorrectionDataReader().read(dataPath)
        compiled.rules.forEach { rule ->
            val tokens = positiveTokens(rule)
            val best = dictionary.lookupBest(tokens)
            require(best?.ruleId == rule.id) {
                "Contextual correction lookup failed: rule=${rule.id} actual=${best?.ruleId}"
            }
            val matched = best ?: error("Contextual correction lookup failed after rule id check: ${rule.id}")
            val expectedSurfaces = tokens.mapIndexed { index, token ->
                if (index == rule.targetIndex) rule.items[rule.targetIndex].replacementSurface else token.surface
            }
            require(matched.surfaces == expectedSurfaces) {
                "Contextual correction surfaces mismatch: rule=${rule.id} expected=$expectedSurfaces actual=${matched.surfaces}"
            }
            val negativeTokens = tokens.toMutableList()
            val target = rule.targetIndex
            negativeTokens[target] = negativeTokens[target].copy(surface = negativeTokens[target].surface + "\u0000")
            require(dictionary.lookupBest(negativeTokens) == null) {
                "Contextual correction negative target probe unexpectedly matched: rule=${rule.id}"
            }
        }
        return compiled.rules.size
    }

    private fun positiveTokens(rule: ContextualCorrectionRule): List<ContextualCorrectionToken> =
        rule.items.mapIndexed { index, item ->
            when (item.kind) {
                ContextualCorrectionPatternKind.LITERAL -> ContextualCorrectionToken(
                    reading = item.reading,
                    surface = item.surface,
                    coarseClass = ContextualCorrectionCoarseClass.UNKNOWN,
                )
                ContextualCorrectionPatternKind.SLOT -> ContextualCorrectionToken(
                    reading = "slot$index",
                    surface = "名詞$index",
                    coarseClass = if (item.coarseClass == ContextualCorrectionCoarseClass.ANY) {
                        ContextualCorrectionCoarseClass.NOUN
                    } else {
                        item.coarseClass
                    },
                )
                ContextualCorrectionPatternKind.TARGET -> ContextualCorrectionToken(
                    reading = item.reading,
                    surface = item.surface,
                    coarseClass = ContextualCorrectionCoarseClass.VERB,
                )
            }
        }
}

object ContextualCorrectionPerformanceProbe {
    fun run(sourceDirectory: Path, dataPath: Path): String {
        val runtime = Runtime.getRuntime()
        runtime.gc()
        val heapBefore = runtime.totalMemory() - runtime.freeMemory()
        val loadStart = System.nanoTime()
        val dictionary = ContextualCorrectionDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart
        runtime.gc()
        val heapAfter = runtime.totalMemory() - runtime.freeMemory()

        val compiled = ContextualCorrectionCompiler.compile(sourceDirectory)
        val probes = compiled.rules.map(::contextualCorrectionPositiveTokens)
            .ifEmpty { listOf(emptyList()) }
        var hitCount = 0
        val lookupStart = System.nanoTime()
        repeat(1000) {
            probes.forEach { tokens ->
                if (dictionary.lookupBest(tokens) != null) hitCount += 1
            }
        }
        val lookupCount = probes.size * 1000L
        val lookupNanos = System.nanoTime() - lookupStart
        val verifyStart = System.nanoTime()
        val verified = ContextualCorrectionVerifier.verify(sourceDirectory, dataPath)
        val verifyNanos = System.nanoTime() - verifyStart

        return buildString {
            appendLine("contextual_correction_probe:")
            appendLine("  binarySizeBytes=${Files.size(dataPath)}")
            appendLine("  loadTimeMs=${loadNanos / 1_000_000.0}")
            appendLine("  heapDeltaBytes=${heapAfter - heapBefore}")
            appendLine("  lookupBestNsOp=${lookupNanos.toDouble() / lookupCount}")
            appendLine("  lookupCount=$lookupCount")
            appendLine("  lookupHitCount=$hitCount")
            appendLine("  ruleCount=${compiled.rules.size}")
            appendLine("  verificationTimeMs=${verifyNanos / 1_000_000.0}")
            appendLine("  verifiedRuleCount=$verified")
        }
    }
}

private fun contextualCorrectionPositiveTokens(rule: ContextualCorrectionRule): List<ContextualCorrectionToken> =
    rule.items.mapIndexed { index, item ->
        when (item.kind) {
            ContextualCorrectionPatternKind.LITERAL -> ContextualCorrectionToken(item.reading, item.surface, ContextualCorrectionCoarseClass.UNKNOWN)
            ContextualCorrectionPatternKind.SLOT -> ContextualCorrectionToken(
                reading = "slot$index",
                surface = "名詞$index",
                coarseClass = if (item.coarseClass == ContextualCorrectionCoarseClass.ANY) {
                    ContextualCorrectionCoarseClass.NOUN
                } else {
                    item.coarseClass
                },
            )
            ContextualCorrectionPatternKind.TARGET -> ContextualCorrectionToken(item.reading, item.surface, ContextualCorrectionCoarseClass.VERB)
        }
    }

private data class ContextualCorrectionStringRef(val offset: Int, val length: Int)

private class ContextualCorrectionStringPool {
    private val bytes = ArrayList<Byte>()
    private val refs = linkedMapOf<String, ContextualCorrectionStringRef>()

    val byteSize: Int
        get() = bytes.size

    fun put(value: String) {
        if (value in refs) return
        val encoded = value.toByteArray(Charsets.UTF_8)
        refs[value] = ContextualCorrectionStringRef(bytes.size, encoded.size)
        encoded.forEach { bytes += it }
    }

    fun ref(value: String): ContextualCorrectionStringRef = refs.getValue(value)

    fun toByteArray(): ByteArray = ByteArray(bytes.size) { bytes[it] }
}

private class ContextualCorrectionLeWriter {
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

private class ContextualCorrectionLeReader(private val bytes: ByteArray) {
    private var offset = 0

    fun readAscii(length: Int): String = readBytes(length).toString(Charsets.US_ASCII)

    fun readBytes(length: Int): ByteArray {
        require(offset + length <= bytes.size) { "Unexpected end of contextual correction data" }
        return bytes.copyOfRange(offset, offset + length).also { offset += length }
    }

    fun readInt(): Int {
        require(offset + Int.SIZE_BYTES <= bytes.size) { "Unexpected end of contextual correction data" }
        var result = 0
        repeat(Int.SIZE_BYTES) { shift ->
            result = result or ((bytes[offset++].toInt() and 0xff) shl (shift * 8))
        }
        return result
    }

    fun isAtEnd(): Boolean = offset == bytes.size
}

private fun ByteArray.decodeContextString(offset: Int, length: Int): String {
    require(offset >= 0 && length >= 0 && offset + length <= size) {
        "Invalid contextual correction string bounds: offset=$offset length=$length size=$size"
    }
    return copyOfRange(offset, offset + length).toString(Charsets.UTF_8)
}

private fun MessageDigest.updateInt(value: Int) {
    update(
        byteArrayOf(
            (value and 0xff).toByte(),
            ((value ushr 8) and 0xff).toByte(),
            ((value ushr 16) and 0xff).toByte(),
            ((value ushr 24) and 0xff).toByte(),
        )
    )
}

private fun MessageDigest.updateUtf8(value: String) {
    val bytes = value.toByteArray(Charsets.UTF_8)
    updateInt(bytes.size)
    update(bytes)
}

private fun contextualCorrectionChecksum(bytesWithZeroChecksum: ByteArray): ByteArray =
    MessageDigest.getInstance("SHA-256").digest(bytesWithZeroChecksum)

private fun contextJsonString(value: String): String = buildString {
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

private const val CTX_MAGIC = "CTX1"
private const val CTX_SHA_256_BYTES = 32
private const val CONTEXTUAL_CORRECTION_MAX_PATTERN_LENGTH = 8
private const val CTX_BUILD_ID_OFFSET = 4 + Int.SIZE_BYTES * 5
private const val CTX_CHECKSUM_OFFSET = CTX_BUILD_ID_OFFSET + CTX_SHA_256_BYTES
private const val CTX_HEADER_SIZE = 4 + Int.SIZE_BYTES * 5 + CTX_SHA_256_BYTES + CTX_SHA_256_BYTES
