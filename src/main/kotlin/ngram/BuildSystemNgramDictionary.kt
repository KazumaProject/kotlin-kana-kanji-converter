package com.kazumaproject.ngram

import java.io.File

fun main(args: Array<String>) {
    val values = args.toList().windowed(2, 2).associate { it[0] to it[1] }
    val source = File(values["--source"] ?: "src/main/ngram")
    val idDef = File(values["--id-def"] ?: "src/main/resources/id.def")
    val output = File(values["--output"] ?: "src/main/resources/ngram/system_ngram.dat")
    val reportFile = File(values["--report"] ?: "build/reports/ngram/build.txt")
    val rules = NgramSourceParser.parseDirectory(source)
    val report = SystemNgramBinaryBuilder.build(rules, idDef, output)
    reportFile.parentFile.mkdirs()
    reportFile.writeText(
        buildString {
            appendLine("ruleCount=${report.ruleCount}")
            appendLine("posClassCount=${report.posClassCount}")
            appendLine("signatureCount=${report.signatureCount}")
            appendLine("stateCount=${report.stateCount}")
            appendLine("edgeCount=${report.edgeCount}")
            appendLine("bytes=${report.bytes}")
            appendLine("bytesPerRule=${report.bytes.toDouble() / report.ruleCount}")
        },
    )
    println(reportFile.readText())
}
