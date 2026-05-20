package mozc

import com.kazumaproject.mozc.ConnectionMatrix
import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class MozcIntegrationGuardTest {
    private val repoRoot: Path = Path.of(System.getProperty("user.dir"))

    @Test
    fun generatedIdDefConstantsAreOnTheBuildPath() {
        val generated = repoRoot.resolve("build/generated/source/mozcIdDef/main/kotlin/com/kazumaproject/IdDefConstants.kt")
        assertTrue(Files.isRegularFile(generated), "Run generateIdDefConstants before tests")
        val text = Files.readString(generated)

        assertTrue(text.contains("Auto-generated from Mozc id.def."))
        assertTrue(text.contains("const val `名詞,接尾,一般,*,*,*,下` = (1951).toShort()"))
        assertTrue(text.contains("const val `連体詞,*,*,*,*,*,我が` = (2671).toShort()"))
    }

    @Test
    fun runtimeCostCalculationDoesNotUseFixedConnectionIdCount() {
        val findPath = Files.readString(repoRoot.resolve("src/main/kotlin/path_algorithm/FindPath.kt"))
        val other = Files.readString(repoRoot.resolve("src/main/kotlin/Other.kt"))

        assertFalse(findPath.contains("NUM_OF_CONNECTION_ID"))
        assertFalse(other.contains("NUM_OF_CONNECTION_ID = 2670"))
        assertTrue(findPath.contains("connectionMatrix.getCost(leftId, rightId)"))
    }

    @Test
    fun connectionMatrixUsesItsOwnSizeForCostIndex() {
        val size = 2672
        val costs = ShortArray(size * size)
        costs[1 * size + 2] = 123
        val matrix = ConnectionMatrix(size, costs)

        assertEquals(123, matrix.getCost(1, 2))
    }
}
