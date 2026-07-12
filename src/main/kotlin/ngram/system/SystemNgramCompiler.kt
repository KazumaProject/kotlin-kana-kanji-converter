package com.kazumaproject.ngram.system

import java.io.File
import java.security.MessageDigest
import java.time.Instant
import kotlin.math.max
import org.openjdk.jol.info.GraphLayout

object SystemNgramCompiler {
    data class BuildResult(
        val dictionary: SystemNgramDictionary,
        val rules: List<SystemNgramRule>,
        val binaryFile: File,
        val sha256: String,
    )

    fun build(sourceDirectory: File, idDefFile: File, binaryFile: File, manifestFile: File): BuildResult {
        val rules = SystemNgramRuleParser.parseDirectory(sourceDirectory)
        val posTable = buildPosTable(idDefFile)
        val dictionary = SystemNgramDictionary.build(rules, posTable)
        dictionary.writeTo(binaryFile)
        val loaded = SystemNgramDictionary.readFrom(binaryFile)
        verifyRules(loaded, rules)
        val checksum = sha256(binaryFile.readBytes())
        writeManifest(manifestFile, loaded, rules, binaryFile.length(), checksum)
        return BuildResult(loaded, rules, binaryFile, checksum)
    }

    fun validate(sourceDirectory: File, idDefFile: File): List<SystemNgramRule> {
        val rules = SystemNgramRuleParser.parseDirectory(sourceDirectory)
        buildPosTable(idDefFile)
        return rules
    }

    fun verifyRules(dictionary: SystemNgramDictionary, rules: List<SystemNgramRule>) {
        rules.forEach { rule ->
            val query = queryFor(rule)
            check(dictionary.matches(query)) {
                "Compiled dictionary does not match ${rule.sourceFile}:${rule.sourceLine}"
            }
        }
    }

    fun queryFor(rule: SystemNgramRule): List<SystemNgramQueryToken> = rule.elements.mapIndexed { index, element ->
        when (element) {
            is SystemNgramElement.Word -> SystemNgramQueryToken(element.surface)
            is SystemNgramElement.Pos -> SystemNgramQueryToken("__pos_${element.posClass.name.lowercase()}_$index", element.posClass)
            SystemNgramElement.Any -> SystemNgramQueryToken("__any_$index", SystemNgramPosClass.UNKNOWN)
        }
    }

    fun buildPosTable(idDefFile: File): ByteArray {
        require(idDefFile.isFile) { "Mozc id.def does not exist: ${idDefFile.path}" }
        val values = mutableListOf<Byte>()
        idDefFile.useLines(Charsets.UTF_8) { lines ->
            lines.forEachIndexed { index, raw ->
                require(raw.isNotBlank()) { "Blank id.def line at ${idDefFile.path}:${index + 1}" }
                val separator = raw.indexOfFirst(Char::isWhitespace)
                require(separator > 0) { "Invalid id.def line at ${idDefFile.path}:${index + 1}" }
                val id = raw.substring(0, separator).toInt()
                require(id == values.size) {
                    "id.def must be continuous at ${idDefFile.path}:${index + 1}; expected=${values.size}, actual=$id"
                }
                val feature = raw.substring(separator + 1)
                values += classifyPos(feature).binaryId.toByte()
            }
        }
        require(values.isNotEmpty()) { "id.def is empty: ${idDefFile.path}" }
        return values.toByteArray()
    }

    private fun classifyPos(feature: String): SystemNgramPosClass {
        val columns = feature.split(',')
        val primary = columns.firstOrNull().orEmpty()
        val secondary = columns.getOrNull(1).orEmpty()
        return when {
            primary == "名詞" && secondary == "固有名詞" -> SystemNgramPosClass.PROPER_NOUN
            primary == "名詞" -> SystemNgramPosClass.NOUN
            primary == "動詞" -> SystemNgramPosClass.VERB
            primary == "形容詞" -> SystemNgramPosClass.ADJECTIVE
            primary == "副詞" -> SystemNgramPosClass.ADVERB
            primary == "助詞" -> SystemNgramPosClass.PARTICLE
            primary == "助動詞" -> SystemNgramPosClass.AUXILIARY
            primary == "記号" || primary == "特殊" -> SystemNgramPosClass.SYMBOL
            primary == "BOS/EOS" -> SystemNgramPosClass.UNKNOWN
            else -> SystemNgramPosClass.OTHER
        }
    }

    private fun writeManifest(
        file: File,
        dictionary: SystemNgramDictionary,
        rules: List<SystemNgramRule>,
        binarySize: Long,
        checksum: String,
    ) {
        val byOrder = (SYSTEM_NGRAM_MIN_ORDER..SYSTEM_NGRAM_MAX_ORDER).associateWith { order ->
            rules.count { it.elements.size == order }
        }
        file.parentFile.mkdirs()
        file.writeText(buildString {
            appendLine("{")
            appendLine("  \"format\": \"SYSTEM_NGRAM_TYPED_LOUDS\",")
            appendLine("  \"formatVersion\": ${SystemNgramDictionary.FORMAT_VERSION},")
            appendLine("  \"ruleCount\": ${dictionary.ruleCount},")
            appendLine("  \"wordCount\": ${dictionary.wordCount},")
            appendLine("  \"wordTrieNodeCount\": ${dictionary.wordTrieNodeCount},")
            appendLine("  \"patternTrieNodeCount\": ${dictionary.patternTrieNodeCount},")
            appendLine("  \"maxOrder\": ${dictionary.maxOrder},")
            appendLine("  \"ruleCountByOrder\": {")
            byOrder.entries.forEachIndexed { index, entry ->
                append("    \"${entry.key}\": ${entry.value}")
                appendLine(if (index == byOrder.size - 1) "" else ",")
            }
            appendLine("  },")
            appendLine("  \"binaryBytes\": $binarySize,")
            appendLine("  \"estimatedHeapBytes\": ${dictionary.estimatedHeapBytes()},")
            appendLine("  \"estimatedMatcherHeapBytesPerThread\": ${SystemNgramDictionary.Matcher.ESTIMATED_HEAP_BYTES},")
            appendLine("  \"sha256\": \"$checksum\"")
            appendLine("}")
        })
    }

    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }
}

object SystemNgramBenchmark {
    data class Distribution(val medianNs: Long, val p95Ns: Long, val maxNs: Long, val operations: Int)

    data class Result(
        val binaryBytes: Long,
        val estimatedHeapBytes: Long,
        val estimatedOperationalHeapBytes: Long,
        val jolJvmHeapBytes: Long,
        val jolJvmOperationalHeapBytes: Long,
        val observedHeapDeltaBytes: Long,
        val wordLookup: Distribution,
        val patternLookup: Distribution,
        val checksum: Long,
    )

    fun run(binaryFile: File, rules: List<SystemNgramRule>, operations: Int): Result {
        require(operations >= 10_000)
        forceGc()
        val before = usedHeap()
        val dictionary = SystemNgramDictionary.readFrom(binaryFile)
        forceGc()
        val after = usedHeap()

        val words = rules.flatMap { it.elements }.mapNotNull { (it as? SystemNgramElement.Word)?.surface }.distinct()
        val queries = rules.map { rule ->
            val tokens = SystemNgramCompiler.queryFor(rule)
            IntArray(tokens.size) { dictionary.findWordId(tokens[it].surface) } to
                IntArray(tokens.size) { tokens[it].posClass.binaryId }
        }
        check(words.isNotEmpty()) { "At least one exact word is required for the benchmark" }
        check(queries.isNotEmpty())
        val matcher = dictionary.newMatcher()

        var checksum = 0L
        repeat(10_000) { index ->
            checksum += dictionary.findWordId(words[index % words.size])
            val query = queries[index % queries.size]
            if (matcher.matchesEncoded(query.first, query.second)) checksum++
        }

        val wordResult = measureBatches(operations) { index ->
            dictionary.findWordId(words[index % words.size]).toLong()
        }
        checksum += wordResult.second
        val patternResult = measureBatches(operations) { index ->
            val query = queries[index % queries.size]
            if (matcher.matchesEncoded(query.first, query.second)) 1L else 0L
        }
        checksum += patternResult.second
        val measuredDictionaryHeap = GraphLayout.parseInstance(dictionary).totalSize()
        val measuredOperationalHeap = GraphLayout.parseInstance(dictionary, matcher).totalSize()

        return Result(
            binaryBytes = binaryFile.length(),
            estimatedHeapBytes = dictionary.estimatedHeapBytes(),
            estimatedOperationalHeapBytes = dictionary.estimatedHeapBytes() + SystemNgramDictionary.Matcher.ESTIMATED_HEAP_BYTES,
            jolJvmHeapBytes = measuredDictionaryHeap,
            jolJvmOperationalHeapBytes = measuredOperationalHeap,
            observedHeapDeltaBytes = max(0L, after - before),
            wordLookup = wordResult.first,
            patternLookup = patternResult.first,
            checksum = checksum,
        )
    }

    private fun measureBatches(operations: Int, operation: (Int) -> Long): Pair<Distribution, Long> {
        val batchCount = 31
        val operationsPerBatch = max(1, operations / batchCount)
        val samples = LongArray(batchCount)
        var checksum = 0L
        var globalIndex = 0
        repeat(batchCount) { batch ->
            val start = System.nanoTime()
            repeat(operationsPerBatch) {
                checksum += operation(globalIndex++)
            }
            samples[batch] = (System.nanoTime() - start) / operationsPerBatch
        }
        samples.sort()
        val p95Index = ((samples.size - 1) * 0.95).toInt()
        return Distribution(
            medianNs = samples[samples.size / 2],
            p95Ns = samples[p95Index],
            maxNs = samples.last(),
            operations = operationsPerBatch * batchCount,
        ) to checksum
    }

    fun writeReports(result: Result, markdownFile: File, propertiesFile: File) {
        markdownFile.parentFile.mkdirs()
        markdownFile.writeText(buildString {
            appendLine("# System N-Gram dictionary benchmark")
            appendLine()
            appendLine("Generated at `${Instant.now()}`. Timing values are observations, not CI pass/fail thresholds.")
            appendLine()
            appendLine("| Metric | Value |")
            appendLine("|---|---:|")
            appendLine("| Serialized dictionary | ${result.binaryBytes} bytes |")
            appendLine("| Estimated retained heap | ${result.estimatedHeapBytes} bytes |")
            appendLine("| Estimated heap with one matcher | ${result.estimatedOperationalHeapBytes} bytes |")
            appendLine("| JOL JVM retained graph size | ${result.jolJvmHeapBytes} bytes |")
            appendLine("| JOL JVM graph with one matcher | ${result.jolJvmOperationalHeapBytes} bytes |")
            appendLine("| Observed JVM heap delta | ${result.observedHeapDeltaBytes} bytes |")
            appendLine("| Word lookup median | ${result.wordLookup.medianNs} ns/op |")
            appendLine("| Word lookup p95 | ${result.wordLookup.p95Ns} ns/op |")
            appendLine("| Pattern lookup median | ${result.patternLookup.medianNs} ns/op |")
            appendLine("| Pattern lookup p95 | ${result.patternLookup.p95Ns} ns/op |")
            appendLine()
            appendLine("`JOL JVM retained graph size` uses the VM layout available to JOL; Android ART can differ. " +
                "`observed JVM heap delta` is GC-sensitive and is reported only as supporting evidence.")
        })
        propertiesFile.parentFile.mkdirs()
        propertiesFile.writeText(buildString {
            appendLine("binary.bytes=${result.binaryBytes}")
            appendLine("heap.estimated.bytes=${result.estimatedHeapBytes}")
            appendLine("heap.estimated.with.matcher.bytes=${result.estimatedOperationalHeapBytes}")
            appendLine("heap.jvm.jol.bytes=${result.jolJvmHeapBytes}")
            appendLine("heap.jvm.jol.with.matcher.bytes=${result.jolJvmOperationalHeapBytes}")
            appendLine("heap.observed.delta.bytes=${result.observedHeapDeltaBytes}")
            appendLine("word.lookup.median.ns=${result.wordLookup.medianNs}")
            appendLine("word.lookup.p95.ns=${result.wordLookup.p95Ns}")
            appendLine("word.lookup.max.ns=${result.wordLookup.maxNs}")
            appendLine("word.lookup.operations=${result.wordLookup.operations}")
            appendLine("pattern.lookup.median.ns=${result.patternLookup.medianNs}")
            appendLine("pattern.lookup.p95.ns=${result.patternLookup.p95Ns}")
            appendLine("pattern.lookup.max.ns=${result.patternLookup.maxNs}")
            appendLine("pattern.lookup.operations=${result.patternLookup.operations}")
            appendLine("checksum=${result.checksum}")
        })
    }

    private fun usedHeap(): Long = Runtime.getRuntime().let { it.totalMemory() - it.freeMemory() }

    private fun forceGc() {
        repeat(3) {
            System.gc()
            Thread.sleep(30)
        }
    }
}
