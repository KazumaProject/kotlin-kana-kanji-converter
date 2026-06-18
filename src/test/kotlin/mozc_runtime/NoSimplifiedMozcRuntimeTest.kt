package mozc_runtime

import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertTrue

class NoSimplifiedMozcRuntimeTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun mozcRuntimeAndDataSourcesDoNotContainEscapeHatches() {
        val roots = listOf(
            repoRoot.resolve("src/main/kotlin/mozc_runtime"),
            repoRoot.resolve("src/main/kotlin/mozc_data"),
        )
        val prohibited = listOf(
            "TODO",
            "FIXME",
            "NotImplementedError",
            "UnsupportedOperationException",
            "simplified",
            "approximate",
            "fake",
            "temporary",
            "later",
            "return emptyList()",
            "return emptySequence()",
        )
        val violations = mutableListOf<String>()
        roots.filter { Files.exists(it) }.forEach { root ->
            Files.walk(root).use { paths ->
                paths.filter { Files.isRegularFile(it) && it.fileName.toString().endsWith(".kt") }.forEach { path ->
                    val text = Files.readString(path)
                    prohibited.forEach { needle ->
                        if (text.contains(needle)) {
                            violations += "${repoRoot.relativize(path)} contains $needle"
                        }
                    }
                }
            }
        }
        assertTrue(violations.isEmpty(), violations.joinToString(separator = "\n"))
    }
}
