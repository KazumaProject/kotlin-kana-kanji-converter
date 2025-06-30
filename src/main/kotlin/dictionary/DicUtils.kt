package com.kazumaproject.dictionary

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.single_kanji.SingleKanjiBuilder
import java.io.File
import java.io.FileInputStream
import java.io.InputStreamReader
import java.util.zip.ZipInputStream

class DicUtils {

    fun getListDictionary(fileList: List<String>): List<Dictionary> {
        val tempList: MutableList<Dictionary> = mutableListOf()
        fileList.forEach {
            val line = object {}::class.java.getResourceAsStream(it)?.bufferedReader()?.readLines()

            line?.forEach { str ->
                str.apply {
                    val yomi = split("\\t".toRegex())[0]
                    val leftId = split("\\t".toRegex())[1]
                    val rightId = split("\\t".toRegex())[2]
                    val cost = split("\\t".toRegex())[3]
                    val tango = split("\\t".toRegex())[4]
                    when {
                        yomi == "では" && tango == "デは" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "での" && tango == "デの" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "でも" && tango == "デも" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "でこそ" && tango == "デこそ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "でしか" && tango == "デしか" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "っとは" && tango == "ットは" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "っとも" && tango == "ットも" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "をは" && tango == "ヲは" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "をも" && tango == "ヲも" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "をら" && tango == "ヲら" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "をしか" && tango == "ヲしか" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "のも" && tango == "のも" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "のも" && tango == "ノも" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "のは" && tango == "ノは" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぽけれ" && tango == "ぽけれ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぽかっ" && tango == "ぽかっ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぽきゃ" && tango == "ぽきゃ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぽから" && tango == "ぽから" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぽかれ" && tango == "ぽかれ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぽかろ" && tango == "ぽかろ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "おこる" && tango == "怒る" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "りゆうしょ" && tango == "理由書" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "しんせいにん" && tango == "申請人" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "にしん" && tango == "ニシン" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "にしん" && tango == "にしん" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ふいんき" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ぎじゅつしょ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "おこっ" && tango == "怒っ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "にほんご" && tango == "日本語" && leftId == "1851" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "よる" && tango == "夜" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "しょうが" && tango == "生姜" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "しんかんせん" && tango == "新幹線" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ちゅうしょうか" && tango == "抽象化" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "なかた" && tango == "中田" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "かしか" && tango == "可視化" && leftId == "1841" && rightId == "1941" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "じぇみに" && tango == "双子座" && leftId == "1920" && rightId == "1920" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "けんこうほう" && tango == "健康法" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "みやこ" && tango == "京都" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "きちゃんねる" && tango == "貴ちゃんねる" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "たかちゃん" && tango == "タカチャン" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "ころん" && tango == "コロン" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "にほんとう" && tango == "日本刀" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "よいか" && tango == "よい花" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "あすぱらがず" && tango == "野天門" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "りょうしか" && tango == "量子化" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "でかい" && tango == "でかい" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "でかい" && tango == "デカイ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "はいっ" && tango == "入っ" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "くいっぱぐれない" && tango == "食いっぱぐれない" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "におっ" && leftId == "825" && rightId == "825" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "におう" && leftId == "813" && rightId == "813" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "におい" && leftId == "829" && rightId == "829" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "びゃんびゃんめん" && leftId == "1851" && rightId == "1851" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "か" && tango == "化" && leftId == "1941" && rightId == "1941" -> {
                            println("skip $yomi $tango")
                        }

                        yomi == "こわすぎ" && tango == "怖すぎ" && leftId == "2391" && rightId == "1949" -> {
                            println("skip $yomi $tango")
                        }

                        else -> {
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

                    }
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
