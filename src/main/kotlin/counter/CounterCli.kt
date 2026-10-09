package com.kazumaproject.counter

import java.io.File
import java.lang.management.ManagementFactory
import kotlin.system.exitProcess

/** Desktop CLI for dictionary generation and conversion checks. */
object CounterCli {
    private const val DEFAULT_DICTIONARY = "src/main/resources/counter/counter_rules.dat"
    @JvmStatic fun main(args: Array<String>) {
        try {
            val status = run(args.toList())
            if (status != 0) exitProcess(status)
        } catch (error: Exception) {
            System.err.println(json(mapOf("error" to (error.message ?: error.javaClass.simpleName))))
            exitProcess(2)
        }
    }

    internal fun run(args: List<String>): Int {
        if (args.isEmpty() || args[0] == "--help") {
            println("counterCli build|inspect|convert|check|benchmark [--dictionary PATH] [--source DIR] [--input READING] [--stdin] [--no-aliases] [--limit N] [--list] [--cases TSV] [--warmup N] [--iterations N] [--report JSON]")
            return 0
        }
        val command = args[0]
        require(command in listOf("build", "inspect", "convert", "check", "benchmark")) { "Unknown command: $command" }
        val flags = mutableSetOf<String>(); val options = linkedMapOf<String, String>(); val inputs = mutableListOf<String>()
        val valueFlags = setOf("--dictionary", "--source", "--input", "--limit", "--cases", "--warmup", "--iterations", "--report")
        var position = 1
        while (position < args.size) {
            val flag = args[position++]
            when {
                flag in setOf("--stdin", "--no-aliases", "--list") -> require(flags.add(flag)) { "Duplicate flag: $flag" }
                flag in valueFlags -> {
                    require(position < args.size && !args[position].startsWith("--")) { "Missing value: $flag" }
                    val value = args[position++]
                    if (flag == "--input") inputs += value else require(options.put(flag, value) == null) { "Duplicate option: $flag" }
                }
                else -> error("Unknown argument: $flag")
            }
        }
        val permitted = setOf("--dictionary", "--report") + when (command) {
            "build" -> setOf("--source", "--cases")
            "inspect" -> setOf("--list")
            "convert" -> setOf("--input", "--stdin", "--no-aliases", "--limit")
            "check" -> setOf("--cases")
            else -> setOf("--input", "--cases", "--no-aliases", "--limit", "--warmup", "--iterations")
        }
        require((options.keys + flags).all { it in permitted } && (inputs.isEmpty() || "--input" in permitted)) { "Option is not valid for $command" }
        val dictionaryFile = File(options["--dictionary"] ?: DEFAULT_DICTIONARY)
        val casesFile = File(options["--cases"] ?: "src/main/counter/cases.tsv")
        if (command == "build") {
            val source = CounterSourceParser.parse(File(options["--source"] ?: "src/main/counter"))
            val bytes = CounterDictionary.compile(source)
            val dictionary = CounterDictionary.read(bytes)
            // Verify the source contract before publishing a build output.
            require(casesFile.isFile) { "Missing golden cases: ${casesFile.path}" }
            run {
                val validation = check(dictionary.converter(), casesFile)
                if (validation.getValue("failed") != 0) System.err.println(json(validation))
                require(validation.getValue("failed") == 0) { "Golden cases failed; dictionary was not written" }
            }
            dictionaryFile.parentFile?.mkdirs(); dictionaryFile.writeBytes(bytes)
            emit(info(dictionary), options["--report"])
            return 0
        }
        val started = System.nanoTime()
        val dictionary = dictionaryFile.inputStream().use { CounterDictionary.read(it) }
        val converter = dictionary.converter()
        val loadNs = System.nanoTime() - started
        val aliases = "--no-aliases" !in flags
        val limit = options["--limit"]?.toInt() ?: Int.MAX_VALUE
        require(limit >= 0)
        when (command) {
            "inspect" -> {
                val catalog = if ("--list" in flags) mapOf("counters" to dictionary.units.mapIndexed { i, unit ->
                    mapOf("id" to unit.id, "surface" to unit.surface, "category" to unit.category,
                        "min" to unit.min.toString(), "max" to unit.max.toString(), "priority" to unit.priority,
                        "aliases" to dictionary.surfaces.filter { it.unit == i }.map { it.surface })
                }) else emptyMap()
                emit(info(dictionary) + ("loadNanoseconds" to loadNs) + catalog, options["--report"])
            }
            "convert" -> {
                require(inputs.isNotEmpty() || "--stdin" in flags) { "convert needs --input or --stdin" }
                require("--report" !in options) { "Use stdout redirection for JSONL conversion output" }
                inputs.forEach { println(json(conversion(converter.convert(it, aliases, limit)))) }
                if ("--stdin" in flags) System.`in`.bufferedReader(Charsets.UTF_8).forEachLine { println(json(conversion(converter.convert(it, aliases, limit)))) }
            }
            "check" -> {
                val report = check(converter, casesFile)
                emit(report, options["--report"])
                return if (report.getValue("failed") == 0) 0 else 1
            }
            "benchmark" -> {
                val warmup = options["--warmup"]?.toInt() ?: 10000
                val iterations = options["--iterations"]?.toInt() ?: 100000
                require(warmup in 0..10000000 && iterations in 1..10000000)
                val corpus = if (inputs.isNotEmpty()) inputs else readCases(casesFile).map { it[0] }.distinct()
                require(corpus.isNotEmpty())
                var checksum = 0L
                fun probe(i: Int) {
                    val result = converter.convert(corpus[i % corpus.size], aliases, limit)
                    checksum += result.candidates.sumOf { it.value.length }.toLong() + result.quantities.size
                }
                repeat(warmup, ::probe)
                val bean = ManagementFactory.getThreadMXBean() as? com.sun.management.ThreadMXBean
                val canCount = bean?.isThreadAllocatedMemorySupported == true
                if (canCount) bean!!.isThreadAllocatedMemoryEnabled = true
                val thread = Thread.currentThread().id
                val before = if (canCount) bean!!.getThreadAllocatedBytes(thread) else -1L
                val times = LongArray(iterations)
                val totalStart = System.nanoTime()
                repeat(iterations) { i -> val start = System.nanoTime(); probe(i); times[i] = System.nanoTime() - start }
                val elapsed = System.nanoTime() - totalStart
                val allocated = if (canCount) bean!!.getThreadAllocatedBytes(thread) - before - iterations * 8L else null
                times.sort()
                fun percentile(p: Double) = times[((iterations - 1) * p).toInt()]
                emit(info(dictionary) + mapOf(
                    "environment" to "desktop-jvm", "androidVerified" to false, "targetDevice" to "Pixel 4 (unmeasured)",
                    "javaVersion" to System.getProperty("java.version"), "vm" to System.getProperty("java.vm.name"),
                    "os" to System.getProperty("os.name"), "arch" to System.getProperty("os.arch"),
                    "inputCount" to corpus.size, "warmup" to warmup, "iterations" to iterations,
                    "includeAliases" to aliases, "limit" to limit, "loadNanoseconds" to loadNs,
                    "p50Nanoseconds" to percentile(0.5), "p95Nanoseconds" to percentile(0.95), "p99Nanoseconds" to percentile(0.99),
                    "maxNanoseconds" to times.last(), "meanNanoseconds" to times.average(), "elapsedNanoseconds" to elapsed,
                    "allocatedBytesPerOperation" to allocated?.toDouble()?.div(iterations), "checksum" to checksum.toString(),
                    "measurement" to "quantity/time parsing plus candidate strings; JSON and startup excluded; per-call timer overhead included",
                ), options["--report"])
            }
        }
        return 0
    }

    private fun readCases(file: File): List<List<String>> {
        val lines = file.readLines(Charsets.UTF_8)
        require(lines.firstOrNull() == "input\tcounter_id\tascii\tkanji\tfullwidth\tclock") { "Invalid cases header" }
        return lines.drop(1).filter { it.isNotBlank() && !it.startsWith('#') }.map { it.split('\t').also { c -> require(c.size == 6) { "Invalid case: $it" } } }
            .also { require(it.isNotEmpty()) { "No golden cases" } }
    }
    internal fun check(converter: CounterConverter, file: File): Map<String, Any> {
        val cases = readCases(file)
        val failures = mutableListOf<Map<String, Any>>()
        for (case in cases) {
            val result = converter.convert(case[0])
            val values = result.candidates.map { it.value }
            val expected = case.drop(2).filter { it.isNotEmpty() }
            val valid = if (case[1] == "@reject") values.isEmpty() else {
                val belongs = if (case[1] == "time") result.time != null else result.quantities.any { it.counterId == case[1] }
                belongs && expected.all { it in values } && expected.zipWithNext().all { (a, b) -> values.indexOf(a) < values.indexOf(b) }
            }
            if (!valid) failures += mapOf("input" to case[0], "counterId" to case[1], "expected" to expected, "actual" to values)
        }
        return mapOf("total" to cases.size, "passed" to cases.size - failures.size, "failed" to failures.size, "failures" to failures)
    }
    private fun info(dictionary: CounterDictionary): Map<String, Any> = mapOf(
        "formatVersion" to CounterDictionary.FORMAT_VERSION, "bytes" to dictionary.byteSize,
        "targetBytes" to 65536, "withinSizeTarget" to (dictionary.byteSize <= 65536),
        "counterCount" to dictionary.counterCount, "numberPartCount" to dictionary.numberPartCount,
        "endingCount" to dictionary.endingCount, "exceptionCount" to dictionary.exceptionCount,
        "aliasCount" to dictionary.aliasCount, "stateCount" to dictionary.stateCount,
        "primitiveIndexBytes" to dictionary.primitiveIndexBytes,
    )
    private fun conversion(result: CounterConversion): Map<String, Any?> = mapOf(
        "input" to result.input, "matched" to result.candidates.isNotEmpty(),
        "quantities" to result.quantities.map { mapOf("counterId" to it.counterId, "number" to it.number.toString(), "category" to it.category, "source" to it.source) },
        "time" to result.time?.let { mapOf("hour" to it.hour, "minute" to it.minute, "second" to it.second, "period" to it.period, "originalHour" to it.originalHour, "half" to it.half) },
        "candidates" to result.candidates.map { mapOf("value" to it.value, "notation" to it.notation, "counterId" to it.counterId) },
    )
    private fun emit(value: Any, reportPath: String?) {
        val output = json(value)
        if (reportPath != null) File(reportPath).also { it.parentFile?.mkdirs(); it.writeText(output + "\n", Charsets.UTF_8) }
        println(output)
    }
    internal fun json(value: Any?): String = when (value) {
        null -> "null"
        is String -> buildString { append('"'); value.forEach { c -> when (c) {
            '"' -> append("\\\""); '\\' -> append("\\\\"); '\n' -> append("\\n"); '\r' -> append("\\r"); '\t' -> append("\\t")
            else -> if (c.code < 32) append("\\u" + c.code.toString(16).padStart(4, '0')) else append(c)
        } }; append('"') }
        is Map<*, *> -> value.entries.joinToString(",", "{", "}") { json(it.key.toString()) + ":" + json(it.value) }
        is Iterable<*> -> value.joinToString(",", "[", "]") { json(it) }
        is Number, is Boolean -> value.toString()
        else -> error("Unsupported JSON value: ${value.javaClass}")
    }
}
