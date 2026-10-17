package classification

import com.kazumaproject.classification.CategoryCostPolicy
import java.io.File
import kotlin.test.*

class CategoryCostPolicyTest {
    private val policy = CategoryCostPolicy.load()

    @Test
    fun penaltyUsesReadingLengthAndStopsGrowingForLongNames() {
        for (reading in listOf("あ", "あい", "あいう")) assertEquals(8400.toShort(), policy.cost(reading, 8400))
        assertEquals(8900.toShort(), policy.cost("あいうえ", 8400))
        assertEquals(9900.toShort(), policy.cost("そらとぶいえ", 8400))
        assertEquals(11900.toShort(), policy.cost("あ".repeat(10), 8400))
        assertEquals(14400.toShort(), policy.cost("あ".repeat(15), 8400))
        assertEquals(14400.toShort(), policy.cost("あ".repeat(100), 8400))
        assertEquals((-500).toShort(), policy.cost("あいうえ", -1000))
        assertEquals(8900.toShort(), policy.cost("あいう𠮷", 7900))
    }

    @Test
    fun invalidPolicyOrCostOverflowFailsInsteadOfWrapping() {
        assertFailsWith<IllegalArgumentException> { CategoryCostPolicy(-1, 500, 6000) }
        assertFailsWith<IllegalArgumentException> { policy.cost("あ".repeat(15), Short.MAX_VALUE) }
        assertEquals(6000.toShort(), CategoryCostPolicy(0, Int.MAX_VALUE, 6000).cost("あい", 0))
        val file = kotlin.io.path.createTempFile("category-policy", ".json").toFile()
        try {
            file.writeText(File("src/main/classification/runtime-cost-policy.json").readText().replace(
                "\"schemaVersion\": 1", "\"schemaVersion\": 2"))
            assertFailsWith<IllegalArgumentException> { CategoryCostPolicy.load(file) }
        } finally { file.delete() }
    }
}
