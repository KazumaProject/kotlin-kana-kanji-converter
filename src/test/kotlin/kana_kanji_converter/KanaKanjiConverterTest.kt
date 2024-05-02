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

        val result1AStarAlgorithm = kanaKanjiEngine.nBestPath(word1,5)
        val result2AStarAlgorithm = kanaKanjiEngine.nBestPath(word2,5)
        val result3AStarAlgorithm = kanaKanjiEngine.nBestPath(word3,5)

        println("Viterbi $word1 =>=> $result1BestPath")
        println("Viterbi $word2 =>=> $result2BestPath")
        println("Viterbi $word3 =>=> $result3BestPath")

        println("nBestPath $word1 =>=> $result1AStarAlgorithm")
        println("nBestPath $word2 =>=> $result2AStarAlgorithm")
        println("nBestPath $word3 =>=> $result3AStarAlgorithm")

    }
}