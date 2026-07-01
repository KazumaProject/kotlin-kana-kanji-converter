package mozc.zeroquery

import com.kazumaproject.mozc.zeroquery.GenerateMozcZeroQueryData
import com.kazumaproject.mozc.zeroquery.GenerateOptions
import com.kazumaproject.mozc.zeroquery.VerifyMozcZeroQueryData
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertTrue

class MozcZeroQueryDataGenerationTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))
    private val resources: Path = repoRoot.resolve("src/main/resources")

    @Test
    fun generatesZeroQueryBinaryDataFromRealResources() {
        val tempDir = Files.createTempDirectory("mozc-zero-query-generation-")
        try {
            GenerateMozcZeroQueryData.generate(
                GenerateOptions(
                    zeroQueryDef = resources.resolve("zero_query.def"),
                    zeroQueryNumberDef = resources.resolve("zero_query_number.def"),
                    emojiData = resources.resolve("mozc_emoji_data.tsv"),
                    emoticonCategorized = resources.resolve("mozc_emoticon_categorized.tsv"),
                    symbol = resources.resolve("mozc_symbol.tsv"),
                    customZeroQueryDef = repoRoot.resolve("src/main/custom_zero_query.def"),
                    outputDir = tempDir,
                )
            )

            listOf(
                "zero_query_token.data",
                "zero_query_string.data",
                "zero_query_number_token.data",
                "zero_query_number_string.data",
            ).forEach { fileName ->
                val path = tempDir.resolve(fileName)
                assertTrue(Files.isRegularFile(path), "Expected generated file: $path")
                assertTrue(Files.size(path) > 0, "Expected non-empty generated file: $path")
            }

            val summary = VerifyMozcZeroQueryData.verify(tempDir)
            assertTrue(summary.customLookupValues.contains("着る"))
        } finally {
            tempDir.toFile().deleteRecursively()
        }
    }
}
