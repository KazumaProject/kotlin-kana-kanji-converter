package com.kazumaproject.dictionary

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.single_kanji.SingleKanjiBuilder

class DicUtils {

    fun getListDictionary(fileList: List<String>): List<Dictionary> {
        val tempList: MutableList<Dictionary> = mutableListOf()
        val regex = """^([^\t]+)\t(\d+)\t(\d+)\t(\d+)\t([^\t]+)(\t.*)?$""".toRegex()

        // List of skip conditions
        val skipConditions = listOf(
            "では" to "デは",
            "での" to "デの",
            "ぽけれ" to "ぽけれ",
            "ぽかっ" to "ぽかっ",
            "ぽきゃ" to "ぽきゃ",
            "ぽから" to "ぽから",
            "ぽかれ" to "ぽかれ",
            "ぽかろ" to "ぽかろ",
            "おこる" to "怒る",
            "りゆうしょ" to "理由書",
            "しんせいにん" to "申請人",
            "にしん" to "ニシン",
            "にしん" to "にしん",
            "ふいんき" to null,
            "ぎじゅつしょ" to null,
            "をは" to "ヲは",
            "をも" to "ヲも",
            "をら" to "ヲら",
            "をしか" to "ヲしか",
            "おこっ" to "怒っ",
            "にほんご" to "日本語",
            "よる" to "夜",
            "しょうが" to "生姜",
            "しんかんせん" to "新幹線",
            "ちゅうしょうか" to "抽象化"
        )

        fileList.forEach { fileName ->
            val lines = object {}::class.java.getResourceAsStream(fileName)?.bufferedReader()?.readLines()

            lines?.forEach { line ->
                val matchResult = regex.matchEntire(line)
                if (matchResult != null) {
                    val (yomi, leftId, rightId, cost, tango) = matchResult.destructured

                    // Check against skip conditions
                    if (skipConditions.any { it.first == yomi && (it.second == null || it.second == tango) }) {
                        println("skip $yomi $tango")
                    } else if (yomi == "にほんご" && tango == "日本語" && leftId == "1851") {
                        println("skip $yomi $tango")
                    } else {
                        tempList.add(
                            Dictionary(
                                yomi = yomi,
                                leftId = leftId.toShort(),
                                rightId = rightId.toShort(),
                                cost = cost.toShort(),
                                tango = tango
                            )
                        )
                    }
                } else {
                    println("Invalid line format: $line")
                }
            }
        }
        return tempList
    }

    fun getSingleKanjiListDictionary(
        singleKanjiFileName: String
    ): List<Dictionary> {
        val singleKanjiBuilder = SingleKanjiBuilder()
        return singleKanjiBuilder.build(singleKanjiFileName)
    }

}
