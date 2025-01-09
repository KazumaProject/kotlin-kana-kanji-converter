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

                        yomi == "びゃんびゃんめん" && leftId == "1851" && rightId == "1851" -> {
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

        val zipFilePath = "src/main/bin/mozcdic-ut.txt.zip"
        val fileNameInZip = "mozcdic-ut.txt"

        // Set of pairs for skip conditions
        val skipConditions = setOf(
            "では" to "デは", "での" to "デの", "でも" to "デも", "でこそ" to "デこそ",
            "でしか" to "デしか", "っとは" to "ットは", "っとも" to "ットも", "をは" to "ヲは",
            "をも" to "ヲも", "をら" to "ヲら", "をしか" to "ヲしか", "のも" to "のも",
            "のも" to "ノも", "のは" to "ノは", "ぽけれ" to "ぽけれ", "ぽかっ" to "ぽかっ",
            "ぽきゃ" to "ぽきゃ", "ぽから" to "ぽから", "ぽかれ" to "ぽかれ", "ぽかろ" to "ぽかろ",
            "おこる" to "怒る", "りゆうしょ" to "理由書", "しんせいにん" to "申請人",
            "にしん" to "ニシン", "にしん" to "にしん", "おこっ" to "怒っ",
            "にほんご" to "日本語", "よる" to "夜", "しょうが" to "生姜",
            "しんかんせん" to "新幹線", "ちゅうしょうか" to "抽象化", "なかた" to "中田",
            "けんこうほう" to "健康法", "みやこ" to "京都", "きちゃんねる" to "貴ちゃんねる",
            "たかちゃん" to "タカチャン", "ころん" to "コロン", "びゃんびゃんめん" to "1851"
        )

        ZipInputStream(FileInputStream(zipFilePath)).use { zipStream ->
            var entry = zipStream.nextEntry
            while (entry != null) {
                if (entry.name == fileNameInZip) {
                    // Process the file inside the zip
                    InputStreamReader(zipStream).buffered().useLines { lines ->
                        lines.forEach { line ->
                            val parts = line.split("\t")
                            if (parts.size < 5) return@forEach // Skip malformed lines
                            val yomi = parts[0]
                            val leftId = parts[1]
                            val rightId = parts[2]
                            val cost = parts[3]
                            val tango = parts[4]

                            // Skip based on conditions
                            if (skipConditions.contains(yomi to tango)) {
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
                        }
                    }
                }
                entry = zipStream.nextEntry
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
