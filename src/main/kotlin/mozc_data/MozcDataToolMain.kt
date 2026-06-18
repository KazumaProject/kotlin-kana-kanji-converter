package mozc_data

import java.nio.file.Files
import java.nio.file.Path

fun main(args: Array<String>) {
    require(args.isNotEmpty()) { "Expected command: verify or manifest" }
    val options = args.drop(1).associateOptionValues()
    when (args[0]) {
        "verify" -> {
            val input = options.requiredPath("input")
            val report = MozcDataVerifier().verify(input, options["expectedVersion"])
            println("Verified mozc.data: fileSize=${report.fileSize}, metadataSize=${report.metadataSize}, sections=${report.sectionCount}, version=${report.version}")
        }
        "manifest" -> {
            val input = options.requiredPath("input")
            val output = options.requiredPath("output")
            val bytes = Files.readAllBytes(input)
            val dataSet = MozcDataSetReader().read(bytes)
            val manifest = MozcDataManifestWriter().create(dataSet, bytes)
            MozcDataManifestWriter().write(output, manifest)
            println("Wrote mozc.data manifest: $output")
        }
        else -> error("Unknown command: ${args[0]}")
    }
}

private fun List<String>.associateOptionValues(): Map<String, String> =
    associate { argument ->
        require(argument.startsWith("--") && argument.contains("=")) { "Invalid option: $argument" }
        val key = argument.substringAfter("--").substringBefore("=")
        val value = argument.substringAfter("=")
        key to value
    }

private fun Map<String, String>.requiredPath(name: String): Path =
    get(name)?.let(Path::of) ?: error("Missing required option: --$name=<path>")
