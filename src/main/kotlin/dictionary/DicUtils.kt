package com.kazumaproject.dictionary

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.single_kanji.SingleKanjiBuilder

class DicUtils {

    fun getListDictionary(
        fileList: List<String>, singleKanjiFileName: String
    ): List<Dictionary> {
        val tempList: MutableList<Dictionary> = mutableListOf()
        val singleKanjiBuilder = SingleKanjiBuilder()
        fileList.forEach {
            val line = object {}::class.java.getResourceAsStream(it)?.bufferedReader()?.readLines()

            line?.forEach { str ->
                str.apply {
                    val yomi = split("\\t".toRegex())[0]
                    val leftId = split("\\t".toRegex())[1]
                    val rightId = split("\\t".toRegex())[2]
                    val cost = split("\\t".toRegex())[3]
                    val tango = split("\\t".toRegex())[4]
                    val dictionary = Dictionary(
                        yomi = yomi,
                        leftId = leftId.toShort(),
                        rightId = rightId.toShort(),
                        cost = cost.toShort(),
                        tango = tango,
                    )
                    tempList.add(dictionary)
                }
            }
        }
        return tempList + singleKanjiBuilder.build(singleKanjiFileName)
    }

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

                        yomi == "ふいんき" -> {
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