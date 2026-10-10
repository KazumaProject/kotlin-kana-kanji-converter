package com.kazumaproject.counter

import java.io.File
import java.lang.management.ManagementFactory
import org.openjdk.jol.info.GraphLayout

/** Explicit desktop measurement tool, never run as a unit test or shipped to Android. */
object CounterEndingBenchmark {
    @Volatile private var sink: Any? = null
    private val allocation = ManagementFactory.getThreadMXBean() as com.sun.management.ThreadMXBean
    private fun allocated() = allocation.getThreadAllocatedBytes(Thread.currentThread().id)
    private fun index(d: CounterDictionary): LongArray = LongArray(1024).also { bits ->
        fun add(c: Char) { bits[c.code ushr 6] = bits[c.code ushr 6] or (1L shl (c.code and 63)) }
        d.units.forEach { it.surface.lastOrNull()?.let(::add) }
        d.surfaces.forEach { it.surface.lastOrNull()?.let(::add) }
        d.exceptions.forEach { it.suffix.lastOrNull()?.let(::add) }
        "0123456789０１２３４５６７８９〇零一二三四五六七八九十百千万億兆京半".forEach(::add)
    }
    private fun stored(c: CounterConverter, s: String): Boolean = c.mayEndQuantitySurface(s)
    @JvmStatic fun main(args: Array<String>) {
        allocation.isThreadAllocatedMemoryEnabled = true
        val mode = args[0]; val file = File(args[1]); val bytes = file.readBytes()
        fun create(stream: Boolean): Pair<CounterConverter, LongArray?> {
            val d = if (stream) file.inputStream().use(CounterDictionary::read) else CounterDictionary.read(bytes)
            return d.converter() to if (mode == "control") index(d) else null
        }
        if (args.getOrNull(2) == "cold") {
            val before = allocated(); val start = System.nanoTime()
            sink = create(args[3] == "stream")
            val elapsed = System.nanoTime() - start; val allocationBytes = allocated() - before
            println(CounterCli.json(mapOf("mode" to mode, "scope" to args[3], "ns" to elapsed, "allocatedBytes" to allocationBytes)))
            return
        }
        val d = CounterDictionary.read(bytes); val c = d.converter(); val bits = if (mode == "control") index(d) else null
        val inputs = File("src/main/counter/cases.tsv").readLines().filter { it.isNotBlank() && !it.startsWith("#") }.drop(1).map { it.substringBefore('\t') }
        val endings = listOf("123本", "二粒", "午後3時半", "12:30", "買う", "出会う", "", "日本", "１ヶ月")
        val reports = mutableListOf<Map<String, Any>>()
        fun measure(name: String, warmup: Int, samples: Int, batch: Int = 1, action: (Int) -> Unit) {
            repeat(warmup) { action(it) }
            val times = LongArray(samples); val allocBefore = allocated()
            repeat(samples) { i -> val start = System.nanoTime(); action(i); times[i] = System.nanoTime() - start }
            val allocatedBytes = allocated() - allocBefore
            times.sort()
            fun p(f: Double) = times[(kotlin.math.ceil(samples * f).toInt() - 1).coerceIn(times.indices)].toDouble() / batch
            reports += mapOf("scope" to name, "warmup" to warmup, "samples" to samples, "batch" to batch,
                "medianNs" to p(.5), "p95Ns" to p(.95), "p99Ns" to p(.99), "allocatedBytesPerOp" to allocatedBytes.toDouble() / samples / batch)
        }
        repeat(5) { run ->
            for (stream in if (run % 2 == 0) listOf(false,true) else listOf(true,false))
                measure("load-${if (stream) "stream" else "bytes"}-$run",2000,5000) { sink=create(stream) }
            measure("converter-$run",2000,5000) { sink = d.converter() to if(mode=="control") index(d) else null }
            if(mode!="baseline") measure("predicate-$run",2000,5000,1024) { offset ->
                var count=0
                repeat(1024) { i -> val s=endings[(offset+i)%endings.size]
                    val matches = if(mode=="control") {
                        val ch=s.lastOrNull()
                        ch!=null && bits!![ch.code ushr 6] and (1L shl(ch.code and 63))!=0L
                    } else stored(c,s)
                    if(matches) count++ }
                sink=count
            }
            measure("convert-$run",10000,100000) { sink=c.convert(inputs[it%inputs.size]) }
        }
        val graph = if(bits==null) GraphLayout.parseInstance(d,c) else GraphLayout.parseInstance(d,c,bits)
        println(CounterCli.json(mapOf("mode" to mode,"inputs" to inputs.size,"retainedBytes" to graph.totalSize(),"reports" to reports,
            "java" to System.getProperty("java.version"),"os" to System.getProperty("os.name"),"arch" to System.getProperty("os.arch"))))
    }
}
