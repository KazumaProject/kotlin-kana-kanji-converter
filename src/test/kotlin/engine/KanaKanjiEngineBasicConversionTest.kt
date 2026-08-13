package engine

import com.kazumaproject.engine.ConversionPathNode
import com.kazumaproject.engine.KanaKanjiEngine
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class KanaKanjiEngineBasicConversionTest {
    @Test
    fun bestPathMatchesJapaneseKeyboardBasicConversionGoldenCases() {
        assertBestPath(
            input = "へんかん",
            value = "変換",
            nodes = listOf(
                expectedNode("へんかん", "変換", 1845, 1845, 0, 5140, 0, 4),
            ),
        )
        assertBestPath(
            input = "きょう",
            value = "今日",
            nodes = listOf(
                expectedNode("きょう", "今日", 1913, 1913, 121, 4326, 0, 3),
            ),
        )
        assertBestPath(
            input = "わたしは",
            value = "私は",
            nodes = listOf(
                expectedNode("わたし", "私", 1902, 1902, 263, 3753, 0, 3),
                expectedNode("は", "は", 283, 283, 0, 4423, 3, 4),
            ),
        )
        assertBestPath(
            input = "やまだたろう",
            value = "山田太郎",
            nodes = listOf(
                expectedNode("やまだ", "山田", 1923, 1923, 2899, 5562, 0, 3),
                expectedNode("たろう", "太郎", 1922, 1922, 2988, 8983, 3, 6),
            ),
        )
    }

    @Test
    fun conversionPreferenceRegressionCases() {
        assertEquals("目の前", engine.viterbiAlgorithm("めのまえ"))

        // The generator's engine does not load system_ngram.dat. These
        // candidates are promoted by JapaneseKeyboard after this project
        // packages the generated scoreless n-gram asset.
        mapOf(
            "でいうと" to "でいうと",
            "いります" to "いります",
            "いんくじぇっとし" to "インクジェット紙",
        ).forEach { (input, expected) ->
            assertTrue(
                expected in engine.nBestPath(input, 64),
                "Candidate must remain available for system n-gram reranking: $input -> $expected",
            )
        }
    }

    @Test
    fun nBestReturnsBasicCandidatesInCostOrder() {
        assertEquals(
            listOf("変換", "返還", "偏官"),
            engine.nBestPath("へんかん", 3),
        )
        assertEquals(emptyList(), engine.nBestPath("へんかん", 0))
    }

    @Test
    fun houseDemolitionExistsInTheSystemCandidatePool() {
        val candidates = engine.nBestPath("いえをかいたい", 64)

        assertTrue("家を解体" in candidates, "System n-gram can only rerank candidates that already exist")
    }

    private fun assertBestPath(
        input: String,
        value: String,
        nodes: List<ConversionPathNode>,
    ) {
        val result = engine.convert(input)

        assertEquals(value, result.value)
        assertEquals(nodes, result.bestPath)
        assertEquals(value, engine.viterbiAlgorithm(input))
    }

    private fun expectedNode(
        key: String,
        value: String,
        lid: Int,
        rid: Int,
        wcost: Int,
        cost: Int,
        start: Int,
        end: Int,
    ): ConversionPathNode =
        ConversionPathNode(
            key = key,
            value = value,
            lid = lid,
            rid = rid,
            wcost = wcost,
            cost = cost,
            start = start,
            end = end,
        )

    private companion object {
        val engine: KanaKanjiEngine by lazy {
            KanaKanjiEngine().apply { buildEngine() }
        }
    }
}
