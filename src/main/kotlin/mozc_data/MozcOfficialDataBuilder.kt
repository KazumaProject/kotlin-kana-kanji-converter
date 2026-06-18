package mozc_data

import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.isDirectory

class MozcOfficialDataBuilder(
    private val projectRoot: Path,
) {
    fun resolveSourceDirectory(explicitSourceDirectory: String?): Path {
        if (!explicitSourceDirectory.isNullOrBlank()) {
            val explicit = Path.of(explicitSourceDirectory)
            require(explicit.isDirectory()) { "mozcSrcDir does not exist: $explicit" }
            return explicit
        }
        val candidates = listOf(
            projectRoot.resolve("third_party/mozc/src"),
            projectRoot.resolve("../mozc/src").normalize(),
            projectRoot.resolve("../mozc-master/src").normalize(),
        )
        return candidates.firstOrNull { it.isDirectory() }
            ?: error("Mozc source directory was not found. Set -PmozcSrcDir=/path/to/mozc/src or place Mozc at one of: ${candidates.joinToString()}")
    }

    fun generatedDataPath(sourceDirectory: Path): Path =
        sourceDirectory.resolve("bazel-bin/data_manager/oss/mozc.data")

    fun build(sourceDirectory: Path, outputPath: Path, bazelCommand: String = "bazel") {
        val process = ProcessBuilder(bazelCommand, "build", "//data_manager/oss:mozc_dataset_for_oss")
            .directory(sourceDirectory.toFile())
            .inheritIO()
            .start()
        val exitCode = process.waitFor()
        require(exitCode == 0) { "Bazel failed while generating official mozc.data: exitCode=$exitCode sourceDirectory=$sourceDirectory" }
        val generated = generatedDataPath(sourceDirectory)
        require(Files.isRegularFile(generated)) { "Bazel did not produce mozc.data: $generated" }
        outputPath.parent?.let(Files::createDirectories)
        Files.copy(generated, outputPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
    }
}
