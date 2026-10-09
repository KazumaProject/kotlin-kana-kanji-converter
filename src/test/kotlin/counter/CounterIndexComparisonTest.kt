package com.kazumaproject.counter

import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import org.openjdk.jol.info.GraphLayout
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals

/** Compare the existing LOUDS API with CSR on the same keys; timings are diagnostic, never CI gates. */
class CounterIndexComparisonTest {
    @Test fun compareEquivalentExactLookupIndexes() {
        val source = CounterSourceParser.parse(File("src/main/counter"))
        val keys = source.endings.map { it.reading.reversed() }.distinct().sorted()
        val truth = keys.toSet()
        val queries = (keys + keys.map { it.dropLast(1) } + listOf("", "存在しない")).distinct()
        val csr = CounterTrie.build(keys.mapIndexed { i, key -> key to i })
        val tree = PrefixTreeWithTermId()
        keys.forEach(tree::insert)
        val built = ConverterWithTermId().convert(tree.root).apply { convertListToBitSet() }
        val output = ByteArrayOutputStream()
        ObjectOutputStream(output).use { built.writeExternalNotCompress(it) }
        val serialized = output.toByteArray()
        val louds = ObjectInputStream(ByteArrayInputStream(serialized)).use { LOUDSWithTermId().readExternalNotCompress(it) }
        fun csrLookup(key: String): Boolean { val node = csr.exact(key); return node >= 0 && csr.postings[node] < csr.postings[node + 1] }
        fun loudsLookup(key: String): Boolean { val node = louds.getNodeIndex(key); return node >= 0 && louds.getTermId(node) >= 0 }
        queries.forEach { key ->
            assertEquals(key in truth, csrLookup(key), key)
            assertEquals(key in truth, loudsLookup(key), key)
        }
        repeat(10000) { i -> val key = queries[i % queries.size]; csrLookup(key); loudsLookup(key) }
        fun measure(lookup: (String) -> Boolean): Map<String, Any> {
            val samples = LongArray(30000); var checksum = 0
            for (i in samples.indices) {
                val key = queries[i % queries.size]; val start = System.nanoTime()
                if (lookup(key)) checksum++
                samples[i] = System.nanoTime() - start
            }
            samples.sort()
            return mapOf("p50Nanoseconds" to samples[samples.size / 2], "p95Nanoseconds" to samples[(samples.size * .95).toInt()],
                "p99Nanoseconds" to samples[(samples.size * .99).toInt()], "checksum" to checksum)
        }
        val csrBytes = 20 + (csr.edges.size + csr.targets.size + csr.postings.size + csr.outputs.size) * 4 + csr.labels.size * 2
        val report = mapOf(
            "environment" to "desktop-jvm", "androidVerified" to false,
            "scope" to "same unique reversed endings; trie-only exact lookup; excludes restoration/quantity parsing and postings per counter; reversed inputs prepared outside timing",
            "keyCount" to keys.size, "queryCount" to queries.size, "iterations" to 30000,
            "csr" to (measure(::csrLookup) + mapOf("wireBytes" to csrBytes, "retainedBytes" to GraphLayout.parseInstance(csr).totalSize())),
            "existingLouds" to (measure(::loudsLookup) + mapOf("wireBytes" to serialized.size, "retainedBytes" to GraphLayout.parseInstance(louds).totalSize())),
        )
        File("build/reports/counter/index-comparison.json").also { it.parentFile.mkdirs(); it.writeText(CounterCli.json(report) + "\n") }
    }
}
