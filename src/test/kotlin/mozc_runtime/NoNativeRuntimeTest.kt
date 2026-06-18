package mozc_runtime

import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.isRegularFile
import kotlin.test.Test
import kotlin.test.assertTrue

class NoNativeRuntimeTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun projectDoesNotWireNativeRuntime() {
        val violations = mutableListOf<String>()
        val pathRoots = listOf(repoRoot.resolve("src/main"), repoRoot.resolve("build.gradle.kts"), repoRoot.resolve(".github/workflows"))
        pathRoots.filter { Files.exists(it) }.forEach { root ->
            Files.walk(root).use { paths ->
                paths.filter { Files.isRegularFile(it) }.forEach { path ->
                    val normalized = repoRoot.relativize(path).toString()
                    if (path.fileName.toString().endsWith(".so")) {
                        violations += "$normalized: shared object file"
                    }
                    if (normalized.contains("jniLibs")) {
                        violations += "$normalized: jniLibs path"
                    }
                    if (path.fileName.toString() == "CMakeLists.txt") {
                        violations += "$normalized: CMake file"
                    }
                }
            }
        }

        val textFiles = listOf(repoRoot.resolve("src/main"), repoRoot.resolve("build.gradle.kts"), repoRoot.resolve(".github/workflows"))
        textFiles.filter { Files.exists(it) }.forEach { root ->
            val files = if (root.isRegularFile()) sequenceOf(root) else Files.walk(root).use { it.filter(Files::isRegularFile).toList().asSequence() }
            files.forEach { path ->
                val text = runCatching { Files.readString(path) }.getOrNull()
                if (text != null) {
                    val normalized = repoRoot.relativize(path).toString()
                    listOf(
                        Regex("""System\.loadLibrary""") to "System.loadLibrary",
                        Regex("""externalNativeBuild""") to "externalNativeBuild",
                        Regex("""\bndk\b""", RegexOption.IGNORE_CASE) to "ndk",
                        Regex("""\bJNI\b""") to "JNI",
                    ).forEach { (regex, label) ->
                        if (regex.containsMatchIn(text)) {
                            violations += "$normalized: $label"
                        }
                    }
                }
            }
        }

        assertTrue(violations.isEmpty(), violations.joinToString(separator = "\n"))
    }
}
