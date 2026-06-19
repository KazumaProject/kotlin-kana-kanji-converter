package mozc_runtime

import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

object MozcGoldenTestSupport {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    fun officialData(): Path {
        val path = repoRoot.resolve("build/generated/mozc-data/mozc.data")
        assertTrue(Files.isRegularFile(path), "Missing official mozc.data. Run ./gradlew generateOfficialMozcData first: $path")
        return path
    }

    fun fixture(relativePath: String): Path {
        val path = repoRoot.resolve("src/test/resources/mozc_golden").resolve(relativePath)
        assertTrue(Files.isRegularFile(path), "Missing official Mozc golden fixture: $path")
        when (relativePath) {
            "dictionary/system_dictionary_lookup.json" -> assertContainsDictionaryTokenFields(path)
            "connector/connector_cost.json" -> assertContainsConnectorFields(path)
            "segmenter/segmenter_boundary.json" -> assertContainsSegmenterFields(path)
            "converter/nbest_generator.json" -> assertContainsNBestGeneratorFields(path)
            "converter/candidate_filter.json" -> assertContainsCandidateFilterFields(path)
            "prediction/predictor.json" -> assertContainsPredictionFields(path)
            "prediction/zero_query.json" -> assertContainsZeroQueryFields(path)
            else -> assertContainsCandidateFields(path)
        }
        return path
    }

    fun runtimeClass(name: String) {
        val klass = runCatching { Class.forName(name) }.getOrNull()
        assertNotNull(klass, "Missing required Mozc Kotlin runtime class: $name")
    }

    private fun assertContainsCandidateFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "key",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "consumedKeySize",
            "innerSegments",
            "description",
            "category",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "Golden fixture is missing required candidate fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsDictionaryTokenFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "queries",
            "query",
            "lookupPrefix",
            "lookupExact",
            "lookupPredictive",
            "lookupReverse",
            "key",
            "value",
            "lid",
            "rid",
            "cost",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "Dictionary fixture is missing required token fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsConnectorFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "costs",
            "leftId",
            "rightId",
            "cost",
            "order",
            "label",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "Connector fixture is missing required fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsSegmenterFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "cases",
            "input",
            "checks",
            "leftPosId",
            "rightPosId",
            "boundaryType",
            "result",
            "order",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "Segmenter fixture is missing required fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsCandidateFilterFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "cases",
            "input",
            "beforeFilter",
            "afterFilter",
            "key",
            "value",
            "lid",
            "rid",
            "cost",
            "attributes",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "CandidateFilter fixture is missing required fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsNBestGeneratorFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "cases",
            "input",
            "requestType",
            "segments",
            "index",
            "key",
            "candidates",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "innerSegments",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "NBest fixture is missing required fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsPredictionFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "cases",
            "input",
            "requestType",
            "results",
            "index",
            "key",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "types",
            "candidateSource",
            "consumedKeySize",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "Predictor fixture is missing required fields: path=$path missing=${missing.joinToString()}")
    }

    private fun assertContainsZeroQueryFields(path: Path) {
        val text = Files.readString(path)
        val fields = listOf(
            "engineDataVersion",
            "cases",
            "context",
            "results",
            "index",
            "key",
            "value",
            "contentKey",
            "contentValue",
            "cost",
            "wcost",
            "structureCost",
            "lid",
            "rid",
            "attributes",
            "types",
            "candidateSource",
            "consumedKeySize",
        )
        val missing = fields.filterNot { "\"$it\"" in text }
        assertTrue(missing.isEmpty(), "ZeroQuery fixture is missing required fields: path=$path missing=${missing.joinToString()}")
    }
}
