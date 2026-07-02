package com.kazumaproject.ngram

import java.nio.file.Path
import kotlin.io.path.fileSize

data class NgramGenerationOptions(
    val sourceDirectory: Path,
    val outputDataPath: Path,
    val outputManifestPath: Path,
    val strictUnresolved: Boolean = false,
)

data class NgramCompiledRules(
    val sourceReadResult: NgramSourceReadResult,
    val normalizeResult: NgramRuleNormalizeResult,
    val resolvedRules: List<ResolvedNgramRule>,
    val unresolvedRules: List<UnresolvedNgramRule>,
    val keySequences: List<NgramKeySequence>,
)

object NgramPresenceCompiler {
    fun compile(sourceDirectory: Path, strictUnresolved: Boolean = false): NgramCompiledRules {
        val sourceReadResult = NgramSourceTsvReader().readDirectory(sourceDirectory)
        val normalizeResult = NgramRuleNormalizer.normalizeAndDedupe(sourceReadResult.rules)
        val termMap = StableTermIdMap.build(NgramDictionarySource.buildMainDictionaryList())
        val resolver = FullReadingSegmentResolver(NgramTermResolver(termMap.terms))
        val resolved = mutableListOf<ResolvedNgramRule>()
        val unresolved = mutableListOf<UnresolvedNgramRule>()

        normalizeResult.rules.forEach { rule ->
            val resolvedRule = resolver.resolve(rule)
            if (resolvedRule == null) {
                unresolved += UnresolvedNgramRule(
                    order = rule.order,
                    reading = rule.reading,
                    surfaces = rule.surfaces.take(rule.order),
                    sourceFile = rule.sourceFile,
                    lineNumber = rule.lineNumber,
                    reason = "No token sequence in stable termId map matches the full reading segmentation",
                )
            } else {
                resolved += resolvedRule
            }
        }

        if (strictUnresolved && unresolved.isNotEmpty()) {
            error("Unresolved N-gram rules: count=${unresolved.size}, first=${unresolved.first()}")
        }

        return NgramCompiledRules(
            sourceReadResult = sourceReadResult,
            normalizeResult = normalizeResult,
            resolvedRules = resolved,
            unresolvedRules = unresolved,
            keySequences = resolved.map { it.keySequence }.sorted().dedupeSorted(),
        )
    }

    private fun List<NgramKeySequence>.dedupeSorted(): List<NgramKeySequence> {
        val result = mutableListOf<NgramKeySequence>()
        forEach { sequence ->
            if (result.lastOrNull() != sequence) {
                result += sequence
            }
        }
        return result
    }
}

object NgramPresenceGenerator {
    fun generate(options: NgramGenerationOptions): NgramPresenceManifest {
        val compiled = NgramPresenceCompiler.compile(
            sourceDirectory = options.sourceDirectory,
            strictUnresolved = options.strictUnresolved,
        )
        val duplicateKeyCount = compiled.resolvedRules.size - compiled.keySequences.size
        val sections = (1..NGRAM_SECTION_COUNT).map { order ->
            BdzMphfBuilder().build(order, compiled.keySequences.filter { it.order == order })
        }
        val writeResult = NgramPresenceDataWriter().write(options.outputDataPath, sections)
        val orders = sections.map { section ->
            NgramOrderManifest(
                order = section.order,
                entryCount = section.entryCount,
                bdzVertexCount = section.vertexCount,
                bdzRetryCount = section.retryCount,
                binaryByteSize = writeResult.sectionPayloadByteSizes.getValue(section.order),
            )
        }
        val manifest = NgramPresenceManifest(
            format = NGRAM_PRESENCE_FORMAT,
            version = NGRAM_PRESENCE_VERSION,
            keyMode = NGRAM_PRESENCE_KEY_MODE,
            sourceFiles = compiled.sourceReadResult.sourceFiles,
            sourceRowCount = compiled.sourceReadResult.sourceRowCount,
            resolvedRuleCount = compiled.keySequences.size,
            unresolvedRuleCount = compiled.unresolvedRules.size,
            duplicateCount = compiled.normalizeResult.duplicateCount + duplicateKeyCount,
            skippedCount = compiled.normalizeResult.skippedCount + compiled.unresolvedRules.size,
            orders = orders,
            dictionaryBuildId = writeResult.dictionaryBuildIdHex,
            contentChecksum = writeResult.contentChecksumHex,
            unresolvedRuleSamples = compiled.unresolvedRules.take(20),
        )
        NgramPresenceManifestWriter.write(options.outputManifestPath, manifest)
        return manifest
    }
}

data class NgramVerificationResult(
    val verifiedEntryCount: Int,
    val negativeProbeCount: Int,
    val elapsedNanos: Long,
)

object NgramPresenceVerifier {
    fun verify(sourceDirectory: Path, dataPath: Path, strictUnresolved: Boolean = false): NgramVerificationResult {
        val startedAt = System.nanoTime()
        val compiled = NgramPresenceCompiler.compile(sourceDirectory, strictUnresolved)
        val dictionary = NgramPresenceDataReader().read(dataPath)
        val byOrder = compiled.keySequences.groupBy { it.order }
        var verified = 0
        for (order in 1..NGRAM_SECTION_COUNT) {
            val expected = byOrder[order].orEmpty()
            val section = dictionary.section(order)
            require((section?.entryCount ?: 0) == expected.size) {
                "N-gram section entry count mismatch: order=$order expected=${expected.size} actual=${section?.entryCount ?: 0}"
            }
            expected.forEach { sequence ->
                require(contains(dictionary, sequence)) {
                    "N-gram presence lookup failed for generated rule: order=${sequence.order} keys=${sequence.keys.contentToString()}"
                }
                verified += 1
            }
        }

        var negativeProbes = 0
        for (order in 1..NGRAM_SECTION_COUNT) {
            val expected = byOrder[order].orEmpty()
            if (expected.isEmpty()) {
                continue
            }
            val candidate = mutateUntilAbsent(expected.first(), expected)
            require(!contains(dictionary, candidate)) {
                "N-gram presence negative probe unexpectedly returned true: order=${candidate.order} keys=${candidate.keys.contentToString()}"
            }
            negativeProbes += 1
        }
        return NgramVerificationResult(
            verifiedEntryCount = verified,
            negativeProbeCount = negativeProbes,
            elapsedNanos = System.nanoTime() - startedAt,
        )
    }

    private fun contains(dictionary: BinaryNgramPresenceDictionary, sequence: NgramKeySequence): Boolean {
        return when (sequence.order) {
            1 -> dictionary.contains1(sequence.keys[0])
            2 -> dictionary.contains2(sequence.keys[0], sequence.keys[1])
            3 -> dictionary.contains3(sequence.keys[0], sequence.keys[1], sequence.keys[2])
            4 -> dictionary.contains4(sequence.keys[0], sequence.keys[1], sequence.keys[2], sequence.keys[3])
            5 -> dictionary.contains5(sequence.keys[0], sequence.keys[1], sequence.keys[2], sequence.keys[3], sequence.keys[4])
            else -> false
        }
    }

    private fun mutateUntilAbsent(sequence: NgramKeySequence, existing: List<NgramKeySequence>): NgramKeySequence {
        var salt = 1L
        while (true) {
            val keys = sequence.keys.copyOf()
            keys[keys.lastIndex] = keys[keys.lastIndex] xor (0x5f3759dfL + salt)
            val candidate = NgramKeySequence(sequence.order, keys)
            if (existing.binarySearch(candidate) < 0) {
                return candidate
            }
            salt += 1
        }
    }
}

object JapaneseKeyboardDictionaryManifestWriter {
    fun write(
        outputPath: Path,
        ngramManifest: NgramPresenceManifest,
        tokenTermIdDataPath: String,
        tokenTermIdManifestPath: String,
    ) {
        val json = buildString {
            appendLine("{")
            appendLine("  \"version\": 1,")
            appendLine("  \"ngramPresence\": {")
            appendLine("    \"data\": \"ngram/ngram_presence.data\",")
            appendLine("    \"manifest\": \"ngram/ngram_presence_manifest.json\",")
            appendLine("    \"tokenTermIdData\": ${jsonString(tokenTermIdDataPath)},")
            appendLine("    \"tokenTermIdManifest\": ${jsonString(tokenTermIdManifestPath)},")
            appendLine("    \"format\": ${jsonString(ngramManifest.format)},")
            appendLine("    \"keyMode\": ${jsonString(ngramManifest.keyMode)},")
            appendLine("    \"dictionaryBuildId\": ${jsonString(ngramManifest.dictionaryBuildId)},")
            appendLine("    \"contentChecksum\": ${jsonString(ngramManifest.contentChecksum)}")
            appendLine("  }")
            appendLine("}")
        }
        outputPath.parent?.toFile()?.mkdirs()
        java.nio.file.Files.writeString(outputPath, json)
    }

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

object NgramPerformanceProbe {
    fun run(sourceDirectory: Path, dataPath: Path): String {
        val runtime = Runtime.getRuntime()
        runtime.gc()
        val heapBefore = runtime.totalMemory() - runtime.freeMemory()
        val loadStart = System.nanoTime()
        val dictionary = NgramPresenceDataReader().read(dataPath)
        val loadNanos = System.nanoTime() - loadStart
        runtime.gc()
        val heapAfter = runtime.totalMemory() - runtime.freeMemory()

        val compiled = NgramPresenceCompiler.compile(sourceDirectory)
        val probes = compiled.keySequences.take(10_000).ifEmpty {
            listOf(NgramKeySequence(1, longArrayOf(1L)))
        }
        val lookupStart = System.nanoTime()
        var hitCount = 0
        repeat(20) {
            probes.forEach { if (contains(dictionary, it)) hitCount += 1 }
        }
        val lookupCount = probes.size * 20L
        val lookupNanos = System.nanoTime() - lookupStart
        val verifyStart = System.nanoTime()
        val verifyResult = NgramPresenceVerifier.verify(sourceDirectory, dataPath)
        val verifyNanos = System.nanoTime() - verifyStart

        return buildString {
            appendLine("ngram_presence_probe:")
            appendLine("  binarySizeBytes=${dataPath.fileSize()}")
            appendLine("  loadTimeMs=${loadNanos / 1_000_000.0}")
            appendLine("  heapDeltaBytes=${heapAfter - heapBefore}")
            appendLine("  containsNsOp=${lookupNanos.toDouble() / lookupCount}")
            appendLine("  lookupCount=$lookupCount")
            appendLine("  lookupHitCount=$hitCount")
            for (order in 1..NGRAM_SECTION_COUNT) {
                val section = dictionary.section(order)
                appendLine("  section$order.entryCount=${section?.entryCount ?: 0}")
                appendLine("  section$order.vertexCount=${section?.vertexCount ?: 0}")
            }
            appendLine("  verificationTimeMs=${verifyNanos / 1_000_000.0}")
            appendLine("  verifiedEntryCount=${verifyResult.verifiedEntryCount}")
        }
    }

    private fun contains(dictionary: BinaryNgramPresenceDictionary, sequence: NgramKeySequence): Boolean {
        return when (sequence.order) {
            1 -> dictionary.contains1(sequence.keys[0])
            2 -> dictionary.contains2(sequence.keys[0], sequence.keys[1])
            3 -> dictionary.contains3(sequence.keys[0], sequence.keys[1], sequence.keys[2])
            4 -> dictionary.contains4(sequence.keys[0], sequence.keys[1], sequence.keys[2], sequence.keys[3])
            5 -> dictionary.contains5(sequence.keys[0], sequence.keys[1], sequence.keys[2], sequence.keys[3], sequence.keys[4])
            else -> false
        }
    }
}
