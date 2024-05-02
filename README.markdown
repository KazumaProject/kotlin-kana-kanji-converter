# Kana Kanji Converter in Kotlin

This is kana kanji converter using Mozc dictionaries in Kotlin.

## Usage

1. copy `dictionary00.txt` ~ `dictionary09.txt`,`connection_single_column.txt` and `single_kanji.tsv` from [mozc](https://github.com/google/mozc/tree/master/src/data/dictionary_oss) to `src/main/resources` directory
2. build binary files for first time

```kotlin
fun main() {
    buildTriesAndTokenArray()
    buildConnectionIdSparseArray()
    buildPOSTable()
}
```

Please refer to `/src/main/Main.kt`

## Sample code:

```kotlin
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
```

Please refer to `/test/kana_kanji_converter/KanaKanjiConverterTest.kt`


