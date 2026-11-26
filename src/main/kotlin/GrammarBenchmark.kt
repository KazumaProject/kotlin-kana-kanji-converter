import com.kazumaproject.grammar.SearchStatistics
import com.sun.management.ThreadMXBean
import kotlinx.serialization.json.*
import java.io.File
import java.lang.management.ManagementFactory
import kotlin.math.ceil
import kotlin.system.measureNanoTime

internal fun benchmarkGrammar(
    input: String, iterations: Int, warmup: Int, initNanos: Long,
    resources: File, additional: List<String>, metadata: File?, run: () -> SearchStatistics?,
): JsonObject {
    require(iterations > 0 && warmup >= 0) { "Use positive iterations and nonnegative warmup" }
    val management = ManagementFactory.getThreadMXBean() as? ThreadMXBean
    if (management?.isThreadAllocatedMemorySupported == true) management.isThreadAllocatedMemoryEnabled = true
    val runtime = Runtime.getRuntime()
    val collectors = ManagementFactory.getGarbageCollectorMXBeans()
    fun heap() = runtime.totalMemory() - runtime.freeMemory()
    fun gcCount() = collectors.map { it.collectionCount }.filter { it >= 0 }.sum()
    fun allocation() = management?.takeIf { it.isThreadAllocatedMemoryEnabled }
        ?.getThreadAllocatedBytes(Thread.currentThread().id)?.takeIf { it >= 0 }
    repeat(warmup) { run() }
    val sample = LongArray(iterations)
    var stats: SearchStatistics? = null
    val gcBefore = gcCount()
    val heapBefore = heap()
    val allocationBefore = allocation()
    for (index in sample.indices) {
        sample[index] = measureNanoTime { stats = run() }
    }
    val allocationAfter = allocation()
    val heapAfter = heap()
    val gcAfter = gcCount()
    sample.sort()
    fun percentile(p: Double) = sample[(ceil(p * sample.size).toInt() - 1).coerceAtLeast(0)]
    val dictionaryNames = listOf("yomi.dat", "tango.dat", "token.dat", "connectionId.dat", "pos_table.dat",
        "ngram/system_ngram.dat", "ngram/system_ngram_unigram.dat", "ngram/system_ngram_standalone_unigram.dat")
    val dictionaryBytes = dictionaryNames.sumOf { resources.resolve(it).length() } +
        additional.sumOf { directory ->
            dictionaryNames.take(3).sumOf { File(directory, it).length() }
        }
    return buildJsonObject {
        put("input", input); put("inputLength", input.length); put("iterations", iterations); put("warmup", warmup)
        put("initializationNs", initNanos); put("dictionaryBytes", dictionaryBytes)
        put("grammarMetadataBytes", metadata?.length() ?: 0)
        put("meanNs", sample.average()); put("p50Ns", percentile(.50)); put("p95Ns", percentile(.95))
        put("p99Ns", percentile(.99)); put("heapBeforeBytes", heapBefore); put("heapAfterBytes", heapAfter)
        put("threadAllocatedBytes", if (allocationAfter != null && allocationBefore != null) {
            JsonPrimitive(allocationAfter - allocationBefore)
        } else JsonNull)
        put("gcCollections", gcAfter - gcBefore)
        put("search", stats?.let(::statisticsJson) ?: JsonNull)
    }
}
