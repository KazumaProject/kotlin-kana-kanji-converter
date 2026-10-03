package com.kazumaproject.cli

import java.io.File
import java.io.PrintWriter

/** The installed CLI carries the worker and configuration; normal conversion needs no Python. */
object ResearchRunner {
    fun run(values: Map<String, String>, out: PrintWriter, err: PrintWriter): Int {
        val location = File(ResearchRunner::class.java.protectionDomain.codeSource.location.toURI())
        val bundled = File(location.parentFile.parentFile, "libexec/research/worker.py")
        val worker = if (bundled.isFile) bundled else File("scripts/research/worker.py")
        require(worker.isFile) { "Missing research worker: $worker" }
        val config = if (bundled.isFile) File(bundled.parentFile, "config") else File("src/main/dictionary-quality/research")
        val command = mutableListOf("python3", worker.absolutePath, values.getValue("action"))
        if (!values.containsKey("config")) command.addAll(listOf("--config", config.absolutePath))
        values.filterKeys { it != "action" }.forEach { (key, value) -> if (key == "candidate") command.add("--candidate") else command.addAll(listOf("--$key", value)) }
        val process = ProcessBuilder(command).redirectErrorStream(true).start()
        val shutdown = Thread { process.destroy() }
        Runtime.getRuntime().addShutdownHook(shutdown)
        return try {
            process.inputStream.bufferedReader().useLines { lines -> lines.forEach { out.println(it); out.flush() } }
            val code = process.waitFor()
            if (code != 0) { err.println("Research stopped; use research status/explain for unfinished work"); err.flush() }
            code
        } finally { Runtime.getRuntime().removeShutdownHook(shutdown) }
    }
}
