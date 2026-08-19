package com.kazumaproject.dictionary

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.single_kanji.SingleKanjiBuilder

class DicUtils {

    fun getListDictionary(fileList: List<String>): List<Dictionary> {
        val tempList = mutableListOf<Dictionary>()

        fileList.forEach fileLoop@{ resourcePath ->
            val lines = object {}::class.java
                .getResourceAsStream(resourcePath)
                ?.bufferedReader()
                ?.readLines()

            lines?.forEach lineLoop@{ str ->
                val fields = str.split('\t', limit = 5)

                if (fields.size < 5) {
                    return@lineLoop
                }

                val yomi = fields[0]
                val leftId = fields[1]
                val rightId = fields[2]
                val cost = fields[3]
                val tango = fields[4]

                when {
                    (yomi to tango) in unnaturalSasuEntries -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "では" && tango == "デは" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "では" && tango == "デハ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "でた" && tango == "デタ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "でる" && tango == "デル" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "ですか" && tango == "デスカ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "でした" && tango == "デシタ" -> {
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

                    yomi == "ふまんてん" && tango == "不満点" -> {
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

                    yomi == "かいたい" && tango == "解体" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "がいじ" && tango == "ガイジ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "ぎじゅつしょ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "おこっ" && tango == "怒っ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "したい" && tango == "死体" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "こうし" && tango == "こうし" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "ですか" &&
                            tango == "ですか" &&
                            leftId == "172" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "にほんご" &&
                            tango == "日本語" &&
                            leftId == "1852" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "でみせ" &&
                            tango == "出店" &&
                            leftId == "1852" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "かいきり" &&
                            tango == "買い切り" &&
                            leftId == "842" -> {
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

                    yomi == "かしか" &&
                            tango == "可視化" &&
                            leftId == "1842" &&
                            rightId == "1942" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "もと" &&
                            tango == "下" &&
                            leftId == "2102" &&
                            rightId == "2102" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "もと" &&
                            tango == "下" &&
                            leftId == "1857" &&
                            rightId == "1857" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "もと" &&
                            tango == "本" &&
                            leftId == "1880" &&
                            rightId == "1880" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "わけ" &&
                            tango == "理由" &&
                            leftId == "1851" &&
                            rightId == "1851" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "した" &&
                            tango == "下" &&
                            leftId == "2002" &&
                            rightId == "2002" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "じぇみに" &&
                            tango == "双子座" &&
                            leftId == "1921" &&
                            rightId == "1921" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "むこうか" &&
                            tango == "無効化" &&
                            leftId == "1932" &&
                            rightId == "1942" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "けんこうほう" && tango == "健康法" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "ございます" && tango == "ゴザイマス" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "じしょびき" && tango == "辞書引き" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "たいかく" && tango == "体格" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "みやこ" && tango == "京都" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "いと" && tango == "系" -> {
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

                    yomi == "ひとおおすぎ" && tango == "人多すぎ" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "になっ" && tango == "になっ" &&
                            rightId == "825" &&
                            leftId == "825" -> {
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

                    yomi == "じしょ" && tango == "辞書" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "か" && tango == "蚊" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "せいびし" && tango == "整備士" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "くいっぱぐれない" &&
                            tango == "食いっぱぐれない" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "におっ" &&
                            leftId == "825" &&
                            rightId == "825" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "におう" &&
                            leftId == "813" &&
                            rightId == "813" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "におい" &&
                            leftId == "829" &&
                            rightId == "829" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "びゃんびゃんめん" &&
                            leftId == "1852" &&
                            rightId == "1852" -> {
                        println("skip $yomi $tango")
                    }

                    yomi == "こわすぎ" &&
                            tango == "怖すぎ" &&
                            leftId == "2392" &&
                            rightId == "1950" -> {
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

        return tempList
    }

    fun getSingleKanjiListDictionary(
        singleKanjiFileName: String
    ): List<Dictionary> {
        val singleKanjiBuilder = SingleKanjiBuilder()
        return singleKanjiBuilder.build(singleKanjiFileName)
    }

    private companion object {

        val unnaturalSasuEntries = setOf(
            "ささ" to "剳さ",
            "ささ" to "扠さ",
            "ささ" to "扨さ",
            "ささ" to "捺さ",
            "ささ" to "箚さ",
            "ささ" to "點さ",

            "さし" to "剳し",
            "さし" to "扠し",
            "さし" to "扨し",
            "さし" to "捺し",
            "さし" to "箚し",
            "さし" to "點し",

            "さしゃ" to "剳しゃ",
            "さしゃ" to "扠しゃ",
            "さしゃ" to "扨しゃ",
            "さしゃ" to "捺しゃ",
            "さしゃ" to "箚しゃ",
            "さしゃ" to "點しゃ",

            "さす" to "剳す",
            "さす" to "扠す",
            "さす" to "扨す",
            "さす" to "捺す",
            "さす" to "箚す",
            "さす" to "點す",

            "させ" to "剳せ",
            "させ" to "扠せ",
            "させ" to "扨せ",
            "させ" to "捺せ",
            "させ" to "箚せ",
            "させ" to "點せ",

            "さそ" to "剳そ",
            "さそ" to "扠そ",
            "さそ" to "扨そ",
            "さそ" to "捺そ",
            "さそ" to "箚そ",
            "さそ" to "點そ"
        )
    }
}
