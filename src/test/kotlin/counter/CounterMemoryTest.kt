package com.kazumaproject.counter

import org.openjdk.jol.info.GraphLayout
import org.openjdk.jol.vm.VM
import java.io.File
import kotlin.test.Test
import kotlin.test.assertTrue

class CounterMemoryTest {
    @Test fun desktopRetainedDictionaryAndConverterStayWithinMemoryBudget() {
        val bytes = CounterDictionary.compile(CounterSourceParser.parse(File("src/main/counter")))
        val dictionary = CounterDictionary.read(bytes)
        val converter = dictionary.converter()
        converter.convert("ごごさんじはん") // Initialize the conversion path; per-call results are not retained.
        val graph = GraphLayout.parseInstance(dictionary, converter)
        val report = mapOf(
            "environment" to "desktop-hotspot-object-graph", "androidVerified" to false,
            "dictionaryBytes" to bytes.size, "retainedBytes" to graph.totalSize(),
            "objectCount" to graph.totalCount(), "targetBytes" to 512 * 1024,
            "scope" to "dictionary and converter instance graphs; excludes class metadata, static fields, transient loading buffers and candidates",
            "vmDetails" to VM.current().details(), "footprint" to graph.toFootprint(),
        )
        File("build/reports/counter/memory.json").also { it.parentFile.mkdirs(); it.writeText(CounterCli.json(report) + "\n") }
        assertTrue(graph.totalSize() <= 512 * 1024, "Retained graph exceeds budget: ${graph.totalSize()}")
    }
}
