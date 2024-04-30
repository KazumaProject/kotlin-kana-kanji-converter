package kana_kanji_converter

import com.kazumaproject.engine.KanaKanjiEngine
import kotlin.test.Test

class KanaKanjiConverterTest {

    @Test
    fun `Test KanaKanjiConverter Engine`() {
        val kanaKanjiEngine = KanaKanjiEngine()
        kanaKanjiEngine.buildEngineForTest()

        val word1 = "とべないぶた"
        val word2 = "わたしのなまえはなかのです"
        val word3 = "ここではきものをぬぐ"

        val result1BestPath = kanaKanjiEngine.viterbiAlgorithm(word1)
        val result2BestPath = kanaKanjiEngine.viterbiAlgorithm(word2)
        val result3BestPath = kanaKanjiEngine.viterbiAlgorithm(word3)

        val result1AStarAlgorithm = kanaKanjiEngine.aStarAlgorithm(word1,5)
        val result2AStarAlgorithm = kanaKanjiEngine.aStarAlgorithm(word2,5)
        val result3AStarAlgorithm = kanaKanjiEngine.aStarAlgorithm(word3,5)

        println("Best Path $word1 =>=> $result1BestPath")
        println("Best Path $word2 =>=> $result2BestPath")
        println("Best Path $word3 =>=> $result3BestPath")

        println("A* Algorithm $word1 =>=> $result1AStarAlgorithm")
        println("A* Algorithm $word2 =>=> $result2AStarAlgorithm")
        println("A* Algorithm $word3 =>=> $result3AStarAlgorithm")

    }
}