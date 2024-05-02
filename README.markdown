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
fun main() {
    val kanaKanjiEngine = KanaKanjiEngine()
    kanaKanjiEngine.buildEngine()

    val word1 = "とべないぶた"
    val word2 = "わたしのなまえはなかのです"
    val word3 = "ここではきものをぬぐ"

    val result1BestPath = kanaKanjiEngine.viterbiAlgorithm(word1)
    val result2BestPath = kanaKanjiEngine.viterbiAlgorithm(word2)
    val result3BestPath = kanaKanjiEngine.viterbiAlgorithm(word3)

    val result1NBest = kanaKanjiEngine.nBestPath(word1,5)
    val result2NBest = kanaKanjiEngine.nBestPath(word2,5)
    val result3NBest = kanaKanjiEngine.nBestPath(word3,5)

    println("Viterbi $word1 ==> $result1BestPath")
    println("Viterbi $word2 ==> $result2BestPath")
    println("Viterbi $word3 ==> $result3BestPath")

    println("nBestPath $word1 ==> $result1NBest")
    println("nBestPath $word2 ==> $result2NBest")
    println("nBestPath $word3 ==> $result3NBest")

}
```
<img width="1003" alt="best_paths" src="https://github.com/KazumaProject/kotlin-kana-kanji-converter/assets/59742125/e24d0338-90ef-4a57-a893-755bc00570a2">

Please refer to `/test/kana_kanji_converter/KanaKanjiConverterTest.kt`
