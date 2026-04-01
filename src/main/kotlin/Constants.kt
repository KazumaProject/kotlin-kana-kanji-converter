package com.kazumaproject

import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,一段,連用形,*`
import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,五段・カ行イ音便,連用形,*`
import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,五段・ラ行,連用タ接続,ある`
import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,五段・ワ行ウ音便,連用形,*`
import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,基本形,*`
import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,五段動詞,基本形,*`
import com.kazumaproject.IdDefConstants.`動詞,自立,*,*,五段動詞,連用形,*`
import com.kazumaproject.IdDefConstants.`名詞,サ変接続,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,一般,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,副詞可能,*,*,*,*,時間`
import com.kazumaproject.IdDefConstants.`名詞,固有名詞,一般,*,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,固有名詞,人名,名,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,固有名詞,人名,姓,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,固有名詞,組織,*,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,形容動詞語幹,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,接尾,サ変接続,*,*,*,化`
import com.kazumaproject.IdDefConstants.`名詞,接尾,一般,*,*,*,*`
import com.kazumaproject.IdDefConstants.`名詞,接尾,一般,*,*,*,人`
import com.kazumaproject.IdDefConstants.`名詞,接尾,一般,*,*,*,制`
import com.kazumaproject.IdDefConstants.`名詞,接尾,一般,*,*,*,書`
import com.kazumaproject.IdDefConstants.`名詞,接尾,一般,*,*,*,点`
import com.kazumaproject.IdDefConstants.`名詞,接尾,助動詞語幹,*,*,*,そう`
import com.kazumaproject.IdDefConstants.`名詞,接尾,特殊,*,*,*,さ`
import com.kazumaproject.IdDefConstants.`形容詞,自立,*,*,形容詞・イ段,ガル接続,*`
import com.kazumaproject.IdDefConstants.`形容詞,非自立,*,*,形容詞・アウオ段,基本形,がたい`
import com.kazumaproject.IdDefConstants.`記号,アルファベット,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`記号,一般,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`記号,句点,*,*,*,*,!`
import com.kazumaproject.IdDefConstants.`記号,句点,*,*,*,*,?`
import com.kazumaproject.IdDefConstants.`記号,句点,*,*,*,*,～`
import com.kazumaproject.IdDefConstants.`記号,括弧閉,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`記号,括弧開,*,*,*,*,*`
import com.kazumaproject.IdDefConstants.`連体詞,*,*,*,*,*,*`
import com.kazumaproject.dictionary.models.Dictionary

object Constants {
    val DIC_LIST = listOf(
        Dictionary(
            yomi = "a",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "a"
        ),
        Dictionary(
            yomi = "b",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "b"
        ),
        Dictionary(
            yomi = "c",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "c"
        ),
        Dictionary(
            yomi = "d",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "d"
        ),
        Dictionary(
            yomi = "e",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "e"
        ),
        Dictionary(
            yomi = "f",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "f"
        ),
        Dictionary(
            yomi = "g",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "g"
        ),
        Dictionary(
            yomi = "h",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "h"
        ),
        Dictionary(
            yomi = "i",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "i"
        ),
        Dictionary(
            yomi = "j",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "j"
        ),
        Dictionary(
            yomi = "k",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "k"
        ),
        Dictionary(
            yomi = "l",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "l"
        ),
        Dictionary(
            yomi = "m",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "m"
        ),
        Dictionary(
            yomi = "n",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "n"
        ),
        Dictionary(
            yomi = "o",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "o"
        ),
        Dictionary(
            yomi = "p",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "p"
        ),
        Dictionary(
            yomi = "q",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "q"
        ),
        Dictionary(
            yomi = "r",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "r"
        ),
        Dictionary(
            yomi = "s",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "s"
        ),
        Dictionary(
            yomi = "t",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "t"
        ),
        Dictionary(
            yomi = "u",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "u"
        ),
        Dictionary(
            yomi = "v",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "v"
        ),
        Dictionary(
            yomi = "x",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "x"
        ),
        Dictionary(
            yomi = "y",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "y"
        ),
        Dictionary(
            yomi = "z",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "z"
        ),
        Dictionary(
            yomi = "A",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "A"
        ),
        Dictionary(
            yomi = "B",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "B"
        ),
        Dictionary(
            yomi = "C",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "C"
        ),
        Dictionary(
            yomi = "D",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "D"
        ),
        Dictionary(
            yomi = "E",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "E"
        ),
        Dictionary(
            yomi = "F",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "F"
        ),
        Dictionary(
            yomi = "G",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "G"
        ),
        Dictionary(
            yomi = "H",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "H"
        ),
        Dictionary(
            yomi = "I",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "I"
        ),
        Dictionary(
            yomi = "J",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "J"
        ),
        Dictionary(
            yomi = "K",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "K"
        ),
        Dictionary(
            yomi = "L",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "L"
        ),
        Dictionary(
            yomi = "M",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "M"
        ),
        Dictionary(
            yomi = "N",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "N"
        ),
        Dictionary(
            yomi = "O",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "O"
        ),
        Dictionary(
            yomi = "P",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "P"
        ),
        Dictionary(
            yomi = "Q",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "Q"
        ),
        Dictionary(
            yomi = "R",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "R"
        ),
        Dictionary(
            yomi = "S",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "S"
        ),
        Dictionary(
            yomi = "T",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "T"
        ),
        Dictionary(
            yomi = "U",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "U"
        ),
        Dictionary(
            yomi = "V",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "V"
        ),
        Dictionary(
            yomi = "W",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "W"
        ),
        Dictionary(
            yomi = "X",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "X"
        ),
        Dictionary(
            yomi = "Y",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "Y"
        ),
        Dictionary(
            yomi = "Z",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "Z"
        ),
        Dictionary(
            yomi = "'", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,一般,*,*,*,*,*`, cost = 8000, tango = "'"
        ),
        Dictionary(
            yomi = "~", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,句点,*,*,*,*,～`, cost = 8000, tango = "~"
        ),
        Dictionary(
            yomi = "\"", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,一般,*,*,*,*,*`, cost = 8000, tango = "\""
        ),
        Dictionary(
            yomi = "ゃ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 1998, tango = "ゃ"
        ),
        Dictionary(
            yomi = "ゅ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8000, tango = "ゅ"
        ),
        Dictionary(
            yomi = "ゃ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8000, tango = "ャ"
        ),
        Dictionary(
            yomi = "ゅ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8001, tango = "ュ"
        ),
        Dictionary(
            yomi = "ゎ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8000, tango = "ゎ"
        ),
        Dictionary(
            yomi = "ゔ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8000, tango = "ゔ"
        ),
        Dictionary(
            yomi = "ゔ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8001, tango = "\u30F4"
        ),
        Dictionary(
            yomi = "ゔ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8002, tango = "ｳﾞ"
        ),
        Dictionary(
            yomi = "づ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8000, tango = "づ"
        ),
        Dictionary(
            yomi = "づ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8001, tango = "ヅ"
        ),
        Dictionary(
            yomi = "づ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 8002, tango = "ﾂﾞ"
        ),
        Dictionary(
            yomi = "%",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "%"
        ),
        Dictionary(
            yomi = "°",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "°"
        ),
        Dictionary(
            yomi = "￥",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "￥"
        ),
        Dictionary(
            yomi = "€",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "€"
        ),
        Dictionary(
            yomi = "♪",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "♪"
        ),
        Dictionary(
            yomi = "々",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "々"
        ),
        Dictionary(
            yomi = "#",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "#"
        ),
        Dictionary(
            yomi = "&",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "&"
        ),
        Dictionary(
            yomi = "！",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 8000,
            tango = "！"
        ),
        Dictionary(
            yomi = "〜", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,句点,*,*,*,*,～`, cost = 8000, tango = "〜"
        ),
        Dictionary(
            yomi = "？", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,句点,*,*,*,*,?`, cost = 8000, tango = "？"
        ),
        Dictionary(
            yomi = "（", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,括弧閉,*,*,*,*,*`, cost = 8000, tango = "（"
        ),
        Dictionary(
            yomi = "）", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,括弧開,*,*,*,*,*`, cost = 8000, tango = "）"
        ),
    )

    val VERB_LIST = listOf(
        Dictionary(
            yomi = "かいたい",
            leftId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            rightId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            cost = 2100,
            tango = "飼いたい"
        ),
        Dictionary(
            yomi = "かいたい",
            leftId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            rightId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            cost = 2150,
            tango = "買いたい"
        ),
        Dictionary(
            yomi = "おうた",
            leftId = `動詞,自立,*,*,五段・ワ行ウ音便,連用形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行ウ音便,連用形,*`,
            cost = 3000,
            tango = "負うた"
        ),
        Dictionary(
            yomi = "たいま",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "大麻"
        ),
        Dictionary(
            yomi = "すう",
            leftId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            cost = 2500,
            tango = "吸う"
        ),
    )

    val CUSTOM_LIST = listOf(
        Dictionary(
            yomi = "きめつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 2000,
            tango = "鬼滅"
        ),
        Dictionary(
            yomi = "あいふぉん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "iPhone"
        ),
        Dictionary(
            yomi = "あんどろいど",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 3900,
            tango = "Android"
        ),
        Dictionary(
            yomi = "とりまよ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "鶏マヨ"
        ),
        Dictionary(
            yomi = "にほんゆび",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "二本指"
        ),
        Dictionary(
            yomi = "たけい",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "たけ井"
        ),
        Dictionary(
            yomi = "とみた",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "とみ田"
        ),
        Dictionary(
            yomi = "めんやたけい",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "麺屋たけ井"
        ),
        Dictionary(
            yomi = "ちゅうかそばとみた",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "中華蕎麦とみ田"
        ),
        Dictionary(
            yomi = "じゃば",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Java"
        ),
        Dictionary(
            yomi = "じゃばすくりぷと",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "JavaScript"
        ),
        Dictionary(
            yomi = "たいぷすくりぷと",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "TypeScript"
        ),
        Dictionary(
            yomi = "ぱいそん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Python"
        ),
        Dictionary(
            yomi = "るびー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Ruby"
        ),
        Dictionary(
            yomi = "ぴーえいちぴー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "PHP"
        ),
        Dictionary(
            yomi = "しーげんご",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "C言語"
        ),
        Dictionary(
            yomi = "しーぷらすぷらす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "C++"
        ),
        Dictionary(
            yomi = "すうぃふと",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Swift"
        ),
        Dictionary(
            yomi = "ことりん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Kotlin"
        ),
        Dictionary(
            yomi = "きんどる",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Kindle"
        ),
        Dictionary(
            yomi = "にしむく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "西向く"
        ),
        Dictionary(
            yomi = "あうんのこきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "阿吽の呼吸"
        ),
        Dictionary(
            yomi = "ひとはこ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "一箱"
        ),
        Dictionary(
            yomi = "こころ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4650,
            tango = "こゝろ"
        ),
        Dictionary(
            yomi = "なーばす",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ナーバス"
        ),
        Dictionary(
            yomi = "そうししゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "創始者"
        ),
        Dictionary(
            yomi = "かけぐるい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "賭ケグルイ"
        ),
        Dictionary(
            yomi = "あづちおおしま",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "的山大島"
        ),
        Dictionary(
            yomi = "あづちこう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "的山港"
        ),
        Dictionary(
            yomi = "あずち", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 4000, tango = "垜"
        ),
        Dictionary(
            yomi = "あづち",
            leftId = `名詞,固有名詞,地域,一般,*,*,*`,
            rightId = `名詞,固有名詞,地域,一般,*,*,*`,
            cost = 5100,
            tango = "的山"
        ),
        Dictionary(
            yomi = "ふまんてん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,点`,
            cost = 4000,
            tango = "不満点"
        ),
        Dictionary(
            yomi = "そうりゅうりょく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "掃流力"
        ),
        Dictionary(
            yomi = "ふどうさん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4200,
            tango = "負動産"
        ),
        Dictionary(
            yomi = "でみせ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "出店"
        ),
        Dictionary(
            yomi = "かいきり",
            leftId = `動詞,自立,*,*,五段動詞,連用形,*`,
            rightId = `動詞,自立,*,*,五段動詞,連用形,*`,
            cost = 4000,
            tango = "買い切り"
        ),
        Dictionary(
            yomi = "おみおつけ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7550,
            tango = "御御御付"
        ),
        Dictionary(
            yomi = "おみおつけ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7500,
            tango = "御味御汁"
        ),
        Dictionary(
            yomi = "じい", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 5800, tango = "自維"
        ),
        Dictionary(
            yomi = "じいせいけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "自維政権"
        ),
        Dictionary(
            yomi = "じいれんりつせいけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "自維連立政権"
        ),
        Dictionary(
            yomi = "ちきゅうしゅうかい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "地球周回"
        ),
        Dictionary(
            yomi = "ちきゅうしゅうかいきどう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "地球周回軌道"
        ),
        Dictionary(
            yomi = "にだいはばつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "二大派閥"
        ),
        Dictionary(
            yomi = "えんすいぷーる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "塩水プール"
        ),
        Dictionary(
            yomi = "おんらいんごうせつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "オンライン合説"
        ),
        Dictionary(
            yomi = "うぇぶごうせつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "ウェブ合説"
        ),
        Dictionary(
            yomi = "うぇぶごうせつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4501,
            tango = "Web合説"
        ),
        Dictionary(
            yomi = "かしひん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "下賜品"
        ),
        Dictionary(
            yomi = "ごじょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "誤乗"
        ),
        Dictionary(
            yomi = "そくへん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "即返"
        ),
        Dictionary(
            yomi = "たんかんえいがかん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "単館映画館"
        ),
        Dictionary(
            yomi = "たんごじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "丹後路"
        ),
        Dictionary(
            yomi = "ぶあつめに",
            leftId = IdDefConstants.`副詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "分厚めに"
        ),
        Dictionary(
            yomi = "ぶいろぐ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ブイログ"
        ),
        Dictionary(
            yomi = "ぶいろぐ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "Vlog"
        ),
        Dictionary(
            yomi = "かせんひっしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "下線筆者"
        ),
        Dictionary(
            yomi = "ぼうせんひっしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "傍線筆者"
        ),
        Dictionary(
            yomi = "かいきょくせん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "開曲線"
        ),
        Dictionary(
            yomi = "かんちょうひん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "完調品"
        ),
        Dictionary(
            yomi = "きこうしゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "寄稿集"
        ),
        Dictionary(
            yomi = "こめがし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "米菓子"
        ),
        Dictionary(
            yomi = "そうていぶ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "漕艇部"
        ),
        Dictionary(
            yomi = "たんりゅうしゅ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "短粒種"
        ),
        Dictionary(
            yomi = "とうばくよう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "塔婆供養"
        ),
        Dictionary(
            yomi = "ひゃくようず",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "百様図"
        ),
        Dictionary(
            yomi = "へいかとしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "閉架図書"
        ),
        Dictionary(
            yomi = "けんさし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "検査士"
        ),
        Dictionary(
            yomi = "あにごえ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "アニ声"
        ),
        Dictionary(
            yomi = "あんこくし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "暗黒史"
        ),
        Dictionary(
            yomi = "せいびし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "整備士"
        ),
        Dictionary(
            yomi = "こくしょき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "酷暑期"
        ),
        Dictionary(
            yomi = "さっちゅうとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "殺虫灯"
        ),
        Dictionary(
            yomi = "そしきち",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "組織知"
        ),
        Dictionary(
            yomi = "ながしした",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "流し下"
        ),
        Dictionary(
            yomi = "なくはめに",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "泣く羽目に"
        ),
        Dictionary(
            yomi = "はんにんげつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "半人月"
        ),
        Dictionary(
            yomi = "りまにゅふぁくちゃりんぐ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "リマニュファクチャリング"
        ),
        Dictionary(
            yomi = "くろずあん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "黒酢あん"
        ),
        Dictionary(
            yomi = "こうりょふじん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "考慮不尽"
        ),
        Dictionary(
            yomi = "ごぶんけい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "五文型"
        ),
        Dictionary(
            yomi = "じこんて",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "字コンテ"
        ),
        Dictionary(
            yomi = "ぜんぱく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "前泊"
        ),
        Dictionary(
            yomi = "つつがゆさい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "筒粥祭"
        ),
        Dictionary(
            yomi = "てんせいろ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "天せいろ"
        ),
        Dictionary(
            yomi = "こみゃく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "こみゃく"
        ),
        Dictionary(
            yomi = "ださてぃー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ダサT"
        ),
        Dictionary(
            yomi = "ちえんしょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "遅延証"
        ),
        Dictionary(
            yomi = "おいくらべ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "追い比べ"
        ),
        Dictionary(
            yomi = "ごかきん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "誤課金"
        ),
        Dictionary(
            yomi = "さんぜんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "産前休"
        ),
        Dictionary(
            yomi = "しとだる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "四斗樽"
        ),
        Dictionary(
            yomi = "じこうしき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 9130,
            tango = "字光式"
        ),
        Dictionary(
            yomi = "せりょういん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "施療院"
        ),
        Dictionary(
            yomi = "はいぜんしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "配膳車"
        ),
        Dictionary(
            yomi = "ひーてっど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ヒーテッド"
        ),
        Dictionary(
            yomi = "あれでら",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "荒れ寺"
        ),
        Dictionary(
            yomi = "かいさんひん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "海産品"
        ),
        Dictionary(
            yomi = "かんもどり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "寒戻り"
        ),
        Dictionary(
            yomi = "きかんしょく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "基幹職"
        ),
        Dictionary(
            yomi = "くちゆく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "朽ちゆく"
        ),
        Dictionary(
            yomi = "こくほうでん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "国宝殿"
        ),
        Dictionary(
            yomi = "さいさいどの",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "再々度の"
        ),
        Dictionary(
            yomi = "じょしぼう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "除脂肪"
        ),
        Dictionary(
            yomi = "りは", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 4000, tango = "リハ"
        ),
        Dictionary(
            yomi = "ちゅうやきん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "昼夜勤"
        ),
        Dictionary(
            yomi = "ばくやけ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "爆焼け"
        ),
        Dictionary(
            yomi = "ひふんち",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "避粉地"
        ),
        Dictionary(
            yomi = "ほわはら",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ホワハラ"
        ),
        Dictionary(
            yomi = "みたつじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "未達時"
        ),
        Dictionary(
            yomi = "かつぜん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "カツ膳"
        ),
        Dictionary(
            yomi = "そつだんせい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "卒団生"
        ),
        Dictionary(
            yomi = "でじえ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "デジ絵"
        ),
        Dictionary(
            yomi = "たんしゅうまい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "炭秀米"
        ),
        Dictionary(
            yomi = "ふんとそく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "フント則"
        ),
        Dictionary(
            yomi = "じし", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 4000, tango = "磁子"
        ),
        Dictionary(
            yomi = "せんいきんぞく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "遷移金属"
        ),
        Dictionary(
            yomi = "にゅーろひかり",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "NURO光"
        ),
        Dictionary(
            yomi = "なに",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "Nani!?"
        ),
        Dictionary(
            yomi = "なにほんやく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4001,
            tango = "Nani翻訳"
        ),
        Dictionary(
            yomi = "なにほんやく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4002,
            tango = "Nani!?翻訳"
        ),
    )

    val ERA = listOf(
        Dictionary(
            yomi = "れいわ",
            leftId = `名詞,副詞可能,*,*,*,*,時間`,
            rightId = `名詞,副詞可能,*,*,*,*,時間`,
            cost = 1685,
            tango = "令和"
        ),
    )

    val DOMAIN = listOf(
        Dictionary(
            yomi = "@gmail.com",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 1500,
            tango = "@gmail.com"
        ),
        Dictionary(
            yomi = "@docomo.ne.jp",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 1500,
            tango = "@docomo.ne.jp"
        ),
        Dictionary(
            yomi = "@i.softbank.jp",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 1500,
            tango = "@i.softbank.jp"
        ),
        Dictionary(
            yomi = "@softbank.ne.jp",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2002,
            tango = "@softbank.ne.jp"
        ),
        Dictionary(
            yomi = "@ezweb.ne.jp",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2003,
            tango = "@ezweb.ne.jp"
        ),
        Dictionary(
            yomi = "@au.com",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2004,
            tango = "@au.com"
        ),
    )

    val NAME_LIST = listOf(
        Dictionary(
            yomi = "みくる",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 3000,
            tango = "未来"
        ),
        Dictionary(
            yomi = "かい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 2000,
            tango = "海"
        ),
        Dictionary(
            yomi = "るきや",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "瑠輝也"
        ),
        Dictionary(
            yomi = "まどか",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 3000,
            tango = "円佳"
        ),
        Dictionary(
            yomi = "ひさし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "寿至"
        ),
        Dictionary(
            yomi = "かずま",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 3500,
            tango = "一真"
        ),
        Dictionary(
            yomi = "なおみ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 3200,
            tango = "尚美"
        ),
        Dictionary(
            yomi = "なか",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 3000,
            tango = "中"
        ),
        Dictionary(
            yomi = "こうじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "皇治"
        ),
        Dictionary(
            yomi = "にしい",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 3500,
            tango = "西居"
        ),
        Dictionary(
            yomi = "なかた",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 2000,
            tango = "中田"
        ),
    )

    val FIGHT_NAME = listOf(
        Dictionary(
            yomi = "らいじん",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 5000,
            tango = "RIZIN"
        ),
        Dictionary(
            yomi = "けーわん",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 5000,
            tango = "K-1"
        ),
        Dictionary(
            yomi = "k-1",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 5000,
            tango = "K-1"
        ),
        Dictionary(
            yomi = "K-1",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 5000,
            tango = "K-1"
        ),
        Dictionary(
            yomi = "らいず",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 5000,
            tango = "RIZE"
        ),
        Dictionary(
            yomi = "しゅーと",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 4000,
            tango = "修斗"
        ),
        Dictionary(
            yomi = "やーまん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ヤーマン"
        ),
        Dictionary(
            yomi = "やーまん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4001,
            tango = "YA-MAN"
        ),
    )

    val NAME_MUSIC_LIST = listOf(
        Dictionary(
            yomi = "ぱんぴー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "PUNPEE"
        ),
        Dictionary(
            yomi = "ぱんぴー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4001,
            tango = "Punpee"
        ),
        Dictionary(
            yomi = "ぱんぴー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4002,
            tango = "punpee"
        ),
        Dictionary(
            yomi = "すらっく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "Slack"
        ),
        Dictionary(
            yomi = "すらっく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4001,
            tango = "5lack"
        ),
        Dictionary(
            yomi = "すらっく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 8002,
            tango = "slack"
        ),
        Dictionary(
            yomi = "ぶっだぶらんど",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "BUDDHA_BRAND"
        ),
        Dictionary(
            yomi = "ぶっだぶらんど",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5001,
            tango = "ブッダ・ブランド"
        ),
    )

    val NAME_IT_LIST = listOf(
        Dictionary(
            yomi = "きーた",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "Qiita"
        ),
        Dictionary(
            yomi = "すたっくおーばーふろー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "Stack Overflow"
        ),
        Dictionary(
            yomi = "ふぇいすぶっく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "Facebook"
        ),
        Dictionary(
            yomi = "ちゃっとじーぴーてぃー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ChatGPT"
        ),
        Dictionary(
            yomi = "うーばー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 3000,
            tango = "Uber"
        ),
        Dictionary(
            yomi = "らいん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 2300,
            tango = "LINE"
        ),
        Dictionary(
            yomi = "いんすたぐらむ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "Instagram"
        ),
        Dictionary(
            yomi = "てぃっくとっく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "TikTok"
        ),
        Dictionary(
            yomi = "ゆーちゅーぶ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "YouTube"
        ),
        Dictionary(
            yomi = "ぐーぐる",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 4000,
            tango = "Google"
        ),
        Dictionary(
            yomi = "ぐーぐるまっぷ",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 4000,
            tango = "Google Map"
        ),
        Dictionary(
            yomi = "あまぞん",
            leftId = `名詞,固有名詞,組織,*,*,*,*`,
            rightId = `名詞,固有名詞,組織,*,*,*,*`,
            cost = 4000,
            tango = "Amazon"
        ),
        Dictionary(
            yomi = "ぎっと",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 3000,
            tango = "Git"
        ),
        Dictionary(
            yomi = "ぎっとはぶ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 3000,
            tango = "GitHub"
        ),
    )

    val SYMBOL_LIST = listOf(
        Dictionary(
            yomi = "はてな", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,句点,*,*,*,*,?`, cost = 4001, tango = "?"
        ),
        Dictionary(
            yomi = "びっくりまーく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,句点,*,*,*,*,!`,
            cost = 4601,
            tango = "!"
        ),
        Dictionary(
            yomi = "かっこ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 4001,
            tango = "（）"
        ),
        Dictionary(
            yomi = "ぷらす",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 4001,
            tango = "+"
        ),
        Dictionary(
            yomi = "まいなす",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 4001,
            tango = "-"
        ),
        Dictionary(
            yomi = "ー", leftId = `名詞,一般,*,*,*,*,*`, rightId = `記号,句点,*,*,*,*,～`, cost = 4001, tango = "~"
        ),
    )

    val ZENKANKU_LIST = listOf(
        Dictionary(
            yomi = "はてな", leftId = `記号,句点,*,*,*,*,?`, rightId = `記号,句点,*,*,*,*,?`, cost = 4000, tango = "？"
        ),
        Dictionary(
            yomi = "びっくりまーく",
            leftId = `記号,アルファベット,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 4600,
            tango = "！"
        ),
        Dictionary(
            yomi = "かっこ",
            leftId = `記号,アルファベット,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 4000,
            tango = "()"
        ),
        Dictionary(
            yomi = "ぷらす",
            leftId = `記号,アルファベット,*,*,*,*,*`,
            rightId = `記号,アルファベット,*,*,*,*,*`,
            cost = 4000,
            tango = "＋"
        ),
        Dictionary(
            yomi = "ー", leftId = `記号,句点,*,*,*,*,～`, rightId = `記号,句点,*,*,*,*,～`, cost = 4000, tango = "〜"
        ),
    )

    val FIXED_LIST = listOf(
        Dictionary(
            yomi = "かのように",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "かのように"
        ),
        Dictionary(
            yomi = "をしたにも",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "をしたにも"
        ),
        Dictionary(
            yomi = "てをふっ",
            leftId = `動詞,自立,*,*,五段・ラ行,連用タ接続,ある`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "手を振っ"
        ),
        Dictionary(
            yomi = "みにくいじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "見にくい字"
        ),
        Dictionary(
            yomi = "みにくいもじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "見にくい文字"
        ),
        Dictionary(
            yomi = "みやすいじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "見やすい字"
        ),
        Dictionary(
            yomi = "よみにくいじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "読みにくい字"
        ),
        Dictionary(
            yomi = "よみにくいもじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "読みにくい文字"
        ),
        Dictionary(
            yomi = "おれかかった",
            leftId = `動詞,自立,*,*,一段,連用形,*`,
            rightId = `動詞,自立,*,*,一段,連用形,*`,
            cost = 3000,
            tango = "折れかかった"
        ),
        Dictionary(
            yomi = "きりがない",
            leftId = `形容詞,非自立,*,*,形容詞・アウオ段,基本形,がたい`,
            rightId = `形容詞,非自立,*,*,形容詞・アウオ段,基本形,がたい`,
            cost = 3000,
            tango = "きりがない"
        ),
        Dictionary(
            yomi = "よくえいぎょうび",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "翌営業日"
        ),
        Dictionary(
            yomi = "そけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "訴権"
        ),
        Dictionary(
            yomi = "こうそけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "公訴権"
        ),
        Dictionary(
            yomi = "きのこ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3500,
            tango = "きのこ"
        ),
        Dictionary(
            yomi = "きのこ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3600,
            tango = "キノコ"
        ),
        Dictionary(
            yomi = "きのこ", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 3700, tango = "茸"
        ),
        Dictionary(
            yomi = "おこる",
            leftId = `動詞,自立,*,*,五段動詞,基本形,*`,
            rightId = `動詞,自立,*,*,五段動詞,基本形,*`,
            cost = 2600,
            tango = "怒る"
        ),
        Dictionary(
            yomi = "りゆうしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,書`,
            cost = 3000,
            tango = "理由書"
        ),
        Dictionary(
            yomi = "しんせいにん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,人`,
            cost = 3000,
            tango = "申請人"
        ),
        Dictionary(
            yomi = "らゔぃっと",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "ラ\u30F4ィット"
        ),
        Dictionary(
            yomi = "にしん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "ニシン"
        ),
        Dictionary(
            yomi = "にしん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3001,
            tango = "にしん"
        ),
        Dictionary(
            yomi = "えんもたけなわ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3001,
            tango = "宴もたけなわ"
        ),
        Dictionary(
            yomi = "あるひと",
            leftId = `連体詞,*,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2500,
            tango = "ある人"
        ),
        Dictionary(
            yomi = "ぎじゅつしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,書`,
            cost = 2500,
            tango = "技術書"
        ),
        Dictionary(
            yomi = "ずかんしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,書`,
            cost = 3500,
            tango = "図鑑書"
        ),
        Dictionary(
            yomi = "じれいしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,書`,
            cost = 3500,
            tango = "辞令書"
        ),
        Dictionary(
            yomi = "でんぴょうしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,書`,
            cost = 3500,
            tango = "伝票書"
        ),
        Dictionary(
            yomi = "ぎょとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "魚頭"
        ),
        Dictionary(
            yomi = "ちゅうしょうか",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,接尾,サ変接続,*,*,*,化`,
            cost = 2300,
            tango = "抽象化"
        ),
        Dictionary(
            yomi = "りょうしか",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,接尾,サ変接続,*,*,*,化`,
            cost = 2300,
            tango = "量子化"
        ),
        Dictionary(
            yomi = "てっそん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "姪孫"
        ),
        Dictionary(
            yomi = "またおい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "又甥"
        ),
        Dictionary(
            yomi = "まためい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "又姪"
        ),
        Dictionary(
            yomi = "そうてっそん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "曾姪孫"
        ),
        Dictionary(
            yomi = "げんてっそん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "玄姪孫"
        ),
        Dictionary(
            yomi = "おいご",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "甥御"
        ),
        Dictionary(
            yomi = "おいめい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "甥姪"
        ),
        Dictionary(
            yomi = "またどなり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "又隣"
        ),
        Dictionary(
            yomi = "けんこうほう",
            leftId = `名詞,形容動詞語幹,*,*,*,*,*`,
            rightId = `名詞,接尾,一般,*,*,*,*`,
            cost = 2500,
            tango = "健康法"
        ),
        Dictionary(
            yomi = "まずしそう",
            leftId = `形容詞,自立,*,*,形容詞・イ段,ガル接続,*`,
            rightId = `名詞,接尾,助動詞語幹,*,*,*,そう`,
            cost = 4000,
            tango = "貧しそう"
        ),
        Dictionary(
            yomi = "みたさ",
            leftId = `形容詞,自立,*,*,形容詞・イ段,ガル接続,*`,
            rightId = `名詞,接尾,特殊,*,*,*,さ`,
            cost = 5000,
            tango = "見たさ"
        ),
        Dictionary(
            yomi = "あいたさ",
            leftId = `形容詞,自立,*,*,形容詞・イ段,ガル接続,*`,
            rightId = `名詞,接尾,特殊,*,*,*,さ`,
            cost = 4301,
            tango = "逢いたさ"
        ),
        Dictionary(
            yomi = "あいたさ",
            leftId = `形容詞,自立,*,*,形容詞・イ段,ガル接続,*`,
            rightId = `名詞,接尾,特殊,*,*,*,さ`,
            cost = 4300,
            tango = "会いたさ"
        ),
        Dictionary(
            yomi = "なんしんとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "何親等"
        ),
        Dictionary(
            yomi = "とうしん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4200,
            tango = "頭身"
        ),
        Dictionary(
            yomi = "あすぱらがす",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6500,
            tango = "竜髭菜"
        ),
        Dictionary(
            yomi = "におっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用タ接続,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用タ接続,*`,
            cost = 3300,
            tango = "匂っ"
        ),
        Dictionary(
            yomi = "におっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用タ接続,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用タ接続,*`,
            cost = 3400,
            tango = "臭っ"
        ),
        Dictionary(
            yomi = "におっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用タ接続,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用タ接続,*`,
            cost = 3500,
            tango = "におっ"
        ),
        Dictionary(
            yomi = "におう",
            leftId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            cost = 3300,
            tango = "匂う"
        ),
        Dictionary(
            yomi = "におう",
            leftId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            cost = 3400,
            tango = "臭う"
        ),
        Dictionary(
            yomi = "におう",
            leftId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            cost = 3500,
            tango = "におう"
        ),
        Dictionary(
            yomi = "におい",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用形,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用形,*`,
            cost = 1900,
            tango = "匂い"
        ),
        Dictionary(
            yomi = "におい",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用形,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用形,*`,
            cost = 3100,
            tango = "臭い"
        ),
        Dictionary(
            yomi = "におい",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用形,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・ワ行促音便,連用形,*`,
            cost = 3400,
            tango = "におい"
        ),
        Dictionary(
            yomi = "でかい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,*`,
            rightId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,*`,
            cost = 2000,
            tango = "でかい"
        ),
        Dictionary(
            yomi = "でかい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,*`,
            rightId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,*`,
            cost = 2100,
            tango = "デカい"
        ),
        Dictionary(
            yomi = "みせぷ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "魅せプ"
        ),
        Dictionary(
            yomi = "くいっぱぐれない",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,ない`,
            cost = 3000,
            tango = "食いっぱぐれない"
        ),
        Dictionary(
            yomi = "りょうしか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,接尾,サ変接続,*,*,*,化`,
            cost = 4000,
            tango = "量子化"
        ),
        Dictionary(
            yomi = "はいっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段動詞,連用タ接続,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段動詞,連用タ接続,*`,
            cost = 1000,
            tango = "入っ"
        ),
        Dictionary(
            yomi = "かしか",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = IdDefConstants.`名詞,接尾,サ変接続,*,*,*,干し`,
            cost = 2500,
            tango = "可視化"
        ),
        Dictionary(
            yomi = "ふかしか",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = IdDefConstants.`名詞,接尾,サ変接続,*,*,*,干し`,
            cost = 3500,
            tango = "不可視化"
        ),
        Dictionary(
            yomi = "なんどか",
            leftId = IdDefConstants.`副詞,一般,*,*,*,*,*`,
            rightId = IdDefConstants.`副詞,一般,*,*,*,*,*`,
            cost = 3500,
            tango = "何度か"
        ),
        Dictionary(
            yomi = "じぇみに",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 6000,
            tango = "双子座"
        ),
        Dictionary(
            yomi = "じぇみに",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Gemini"
        ),
        Dictionary(
            yomi = "じぇみない",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 5000,
            tango = "Gemini"
        ),
        Dictionary(
            yomi = "ぎもうこうい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "欺罔行為"
        ),
        Dictionary(
            yomi = "ききました",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・マス,連用形,ます`,
            rightId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            cost = 1000,
            tango = "聞きました"
        ),
        Dictionary(
            yomi = "ききました",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・マス,連用形,ます`,
            rightId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            cost = 1005,
            tango = "効きました"
        ),
        Dictionary(
            yomi = "ききました",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・マス,連用形,ます`,
            rightId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            cost = 1010,
            tango = "聴きました"
        ),
        Dictionary(
            yomi = "こわすぎ",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,ガル接続,*`,
            rightId = `名詞,接尾,一般,*,*,*,*`,
            cost = 2300,
            tango = "怖すぎ"
        ),
        Dictionary(
            yomi = "こわすぎる",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,ガル接続,*`,
            rightId = `名詞,接尾,一般,*,*,*,*`,
            cost = 2500,
            tango = "怖すぎる"
        ),
        Dictionary(
            yomi = "こわすぎて",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,ガル接続,*`,
            rightId = `名詞,接尾,一般,*,*,*,*`,
            cost = 2600,
            tango = "怖すぎて"
        ),
        Dictionary(
            yomi = "かちかく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 3500,
            tango = "勝ち確"
        ),
        Dictionary(
            yomi = "じしょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3200,
            tango = "辞書"
        ),
        Dictionary(
            yomi = "からもじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3500,
            tango = "空文字"
        ),
        Dictionary(
            yomi = "まじりぶん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 3500,
            tango = "交じり文"
        ),
        Dictionary(
            yomi = "りけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "離鍵"
        ),
        Dictionary(
            yomi = "じーぼーど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "Gboard"
        ),
        Dictionary(
            yomi = "あっぷん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "圧粉"
        ),
        Dictionary(
            yomi = "きゅうはいき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "吸排気"
        ),
        Dictionary(
            yomi = "きゅうはいき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "給排気"
        ),
        Dictionary(
            yomi = "かんじへんかん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "漢字変換"
        ),
        Dictionary(
            yomi = "か", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 4000, tango = "蚊"
        ),
        Dictionary(
            yomi = "げつがくせい",
            leftId = `名詞,接尾,一般,*,*,*,制`,
            rightId = `名詞,接尾,一般,*,*,*,制`,
            cost = 3000,
            tango = "月額制"
        ),
        Dictionary(
            yomi = "ほけんせい",
            leftId = `名詞,接尾,一般,*,*,*,制`,
            rightId = `名詞,接尾,一般,*,*,*,制`,
            cost = 4000,
            tango = "保険制"
        ),
        Dictionary(
            yomi = "ぜいせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "税制度"
        ),
        Dictionary(
            yomi = "さいばんせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "裁判制度"
        ),
        Dictionary(
            yomi = "ほうしゅうせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "報酬制度"
        ),
        Dictionary(
            yomi = "ほうしゅうせい",
            leftId = `名詞,接尾,一般,*,*,*,制`,
            rightId = `名詞,接尾,一般,*,*,*,制`,
            cost = 6000,
            tango = "報酬制"
        ),
        Dictionary(
            yomi = "ふくりこうせいせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "福利厚生制度"
        ),
        Dictionary(
            yomi = "たいしょくきんせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "退職金制度"
        ),
        Dictionary(
            yomi = "たんいせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "単位制度"
        ),
        Dictionary(
            yomi = "たんいせい",
            leftId = `名詞,接尾,一般,*,*,*,制`,
            rightId = `名詞,接尾,一般,*,*,*,制`,
            cost = 6000,
            tango = "単位制"
        ),
        Dictionary(
            yomi = "じゅうたくせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "住宅制度"
        ),
        Dictionary(
            yomi = "いくじきゅうぎょうせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "育児休業制度"
        ),
        Dictionary(
            yomi = "かいごせいど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "介護制度"
        ),
        Dictionary(
            yomi = "むこうか",
            leftId = `名詞,接尾,サ変接続,*,*,*,化`,
            rightId = `名詞,接尾,サ変接続,*,*,*,化`,
            cost = 3000,
            tango = "無効化"
        ),
        Dictionary(
            yomi = "ていれいや",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "低レイヤ"
        ),
        Dictionary(
            yomi = "こうれいや",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "高レイヤ"
        ),
        Dictionary(
            yomi = "たこぴーのげんざい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "タコピーの原罪"
        ),
        Dictionary(
            yomi = "れっきと",
            leftId = IdDefConstants.`副詞,一般,*,*,*,*,*`,
            rightId = IdDefConstants.`副詞,一般,*,*,*,*,*`,
            cost = 7200,
            tango = "歴と"
        ),
        Dictionary(
            yomi = "れっきとした",
            leftId = `連体詞,*,*,*,*,*,*`,
            rightId = `連体詞,*,*,*,*,*,*`,
            cost = 3700,
            tango = "歴とした"
        ),
        Dictionary(
            yomi = "とはなに",
            leftId = IdDefConstants.`名詞,代名詞,対象,*,*,*,*`,
            rightId = IdDefConstants.`名詞,代名詞,対象,*,*,*,*`,
            cost = 2600,
            tango = "とは何"
        ),
        Dictionary(
            yomi = "とはなに",
            leftId = IdDefConstants.`名詞,代名詞,対象,*,*,*,*`,
            rightId = IdDefConstants.`名詞,代名詞,対象,*,*,*,*`,
            cost = 2800,
            tango = "とはなに"
        ),
        Dictionary(
            yomi = "ございますか",
            leftId = IdDefConstants.`助詞,終助詞,*,*,*,*,かぁ`,
            rightId = IdDefConstants.`動詞,自立,*,*,五段・カ行促音便ユク,連用形,*`,
            cost = 600,
            tango = "ございますか"
        ),
        Dictionary(
            yomi = "いちねん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "一年"
        ),
        Dictionary(
            yomi = "いちねん",
            leftId = IdDefConstants.`名詞,数,漢数字,*,*,*,*`,
            rightId = IdDefConstants.`名詞,接尾,助数詞,*,*,*,*`,
            cost = 2000,
            tango = "一年"
        ),
        Dictionary(
            yomi = "いちにち",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "一日"
        ),
        Dictionary(
            yomi = "たいかく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "体格"
        ),
        Dictionary(
            yomi = "じしょびき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `動詞,自立,*,*,五段・カ行イ音便,連用形,*`,
            cost = 3500,
            tango = "辞書引き"
        ),
        Dictionary(
            yomi = "じしょびき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = IdDefConstants.`名詞,接尾,一般,*,*,*,引き`,
            cost = 3200,
            tango = "辞書引き"
        ),
        Dictionary(
            yomi = "にれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "二連休"
        ),
        Dictionary(
            yomi = "にれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "2連休"
        ),
        Dictionary(
            yomi = "さんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "三連休"
        ),
        Dictionary(
            yomi = "さんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "3連休"
        ),
        Dictionary(
            yomi = "よんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "四連休"
        ),
        Dictionary(
            yomi = "よんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "4連休"
        ),
        Dictionary(
            yomi = "ごれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "五連休"
        ),
        Dictionary(
            yomi = "ごれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "5連休"
        ),
        Dictionary(
            yomi = "ろくれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "六連休"
        ),
        Dictionary(
            yomi = "ろくれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "6連休"
        ),
        Dictionary(
            yomi = "ななれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "七連休"
        ),
        Dictionary(
            yomi = "ななれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "7連休"
        ),
        Dictionary(
            yomi = "はちれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "八連休"
        ),
        Dictionary(
            yomi = "はちれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "8連休"
        ),
        Dictionary(
            yomi = "きゅうれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "九連休"
        ),
        Dictionary(
            yomi = "きゅうれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "9連休"
        ),
        Dictionary(
            yomi = "じゅうれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "十連休"
        ),
        Dictionary(
            yomi = "じゅうれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "10連休"
        ),
        Dictionary(
            yomi = "じゅういちれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "十一連休"
        ),
        Dictionary(
            yomi = "じゅういちれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "11連休"
        ),
        Dictionary(
            yomi = "じゅうにれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "十二連休"
        ),
        Dictionary(
            yomi = "じゅうにれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "12連休"
        ),
        Dictionary(
            yomi = "じゅうさんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "十三連休"
        ),
        Dictionary(
            yomi = "じゅうさんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "13連休"
        ),
        Dictionary(
            yomi = "じゅうよんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "十四連休"
        ),
        Dictionary(
            yomi = "じゅうよんれんきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "14連休"
        ),
        Dictionary(
            yomi = "ごしちご",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "五七五"
        ),
        Dictionary(
            yomi = "ごしちごしちしち",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5001,
            tango = "五七五七七"
        ),
        Dictionary(
            yomi = "ですか",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・デス,基本形,です`,
            rightId = IdDefConstants.`助詞,副助詞／並立助詞／終助詞,*,*,*,*,か`,
            cost = 500,
            tango = "ですか"
        ),
        Dictionary(
            yomi = "おてつたび",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "おてつたび"
        ),
    )

    val PHISIC_NOUN_LIST = listOf(
        Dictionary(
            yomi = "てっそん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2301,
            tango = "鉄損"
        ),
        Dictionary(
            yomi = "てっそんしつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2000,
            tango = "鉄損失"
        ),
        Dictionary(
            yomi = "あっぷんじしん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "圧粉磁心"
        ),
    )

    val DIFFICULT_LIST = listOf(
        Dictionary(
            yomi = "にわにはにわ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "庭には二羽"
        ),
        Dictionary(
            yomi = "にわにはにわ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "庭には２羽"
        ),
        Dictionary(
            yomi = "かきくう",
            leftId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            cost = 4001,
            tango = "柿食う"
        ),
        Dictionary(
            yomi = "よくかき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "よく柿"
        ),
        Dictionary(
            yomi = "よくかきくう",
            leftId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            rightId = `動詞,自立,*,*,五段・ワ行促音便,基本形,*`,
            cost = 4000,
            tango = "よく柿食う"
        ),
        Dictionary(
            yomi = "はがいたい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,命令ｅ,良い`,
            rightId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,命令ｅ,良い`,
            cost = 3000,
            tango = "歯が痛い"
        ),
        Dictionary(
            yomi = "かえるのこはかえる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "蛙の子は蛙"
        ),
        Dictionary(
            yomi = "てきにしお",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "敵に塩"
        ),
        Dictionary(
            yomi = "ひとしな",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "一品"
        ),
        Dictionary(
            yomi = "しゅはり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "守破離"
        ),
        Dictionary(
            yomi = "つめもの",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "詰め物"
        ),
        Dictionary(
            yomi = "すいらいけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "酔来軒"
        ),
        Dictionary(
            yomi = "びーきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "B級"
        ),
        Dictionary(
            yomi = "だんしゃり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "断捨離"
        ),
        Dictionary(
            yomi = "しゃぎょう",
            leftId = IdDefConstants.`動詞,自立,*,*,四段・タ行,未然形,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,四段・タ行,未然形,*`,
            cost = 4000,
            tango = "捨行"
        ),
        Dictionary(
            yomi = "りぎょう",
            leftId = IdDefConstants.`動詞,自立,*,*,ラ変,未然形,*`,
            rightId = IdDefConstants.`動詞,自立,*,*,ラ変,未然形,*`,
            cost = 4000,
            tango = "離行"
        ),
        Dictionary(
            yomi = "しかのこ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "鹿の子"
        ),
        Dictionary(
            yomi = "いちふじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "一富士"
        ),
        Dictionary(
            yomi = "にたか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "二鷹"
        ),
        Dictionary(
            yomi = "さんなすび",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "三茄子"
        ),
        Dictionary(
            yomi = "しせん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5200,
            tango = "四扇"
        ),
        Dictionary(
            yomi = "ごたばこ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "五煙草"
        ),
        Dictionary(
            yomi = "ろくざとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "六座頭"
        ),
        Dictionary(
            yomi = "しせんごたばころくざとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "四扇五煙草六座頭"
        ),
        Dictionary(
            yomi = "えびでたいをつる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 1000,
            tango = "海老で鯛を釣る"
        ),
        Dictionary(
            yomi = "はもの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "鱧の"
        ),
        Dictionary(
            yomi = "めんばん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "麺絆"
        ),
        Dictionary(
            yomi = "さんねんざか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "産寧坂"
        ),
        Dictionary(
            yomi = "やさかのとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "八坂の塔"
        ),
        Dictionary(
            yomi = "せんた",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "仙太"
        ),
        Dictionary(
            yomi = "わびさび",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "侘び寂び"
        ),
        Dictionary(
            yomi = "かもん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "家紋"
        ),
        Dictionary(
            yomi = "せっか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "雪花"
        ),
        Dictionary(
            yomi = "つきました",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `動詞,自立,*,*,一段,連用形,*`,
            cost = 3000,
            tango = "着きました"
        ),
        Dictionary(
            yomi = "いきました",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `動詞,自立,*,*,一段,連用形,*`,
            cost = 1500,
            tango = "行きました"
        ),
        Dictionary(
            yomi = "にほんご",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2500,
            tango = "日本語"
        ),
        Dictionary(
            yomi = "にほんとう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3500,
            tango = "日本刀"
        ),
        Dictionary(
            yomi = "がくるまで",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,で`,
            rightId = IdDefConstants.`助詞,格助詞,一般,*,*,*,が`,
            cost = 4000,
            tango = "が来るまで"
        ),
        Dictionary(
            yomi = "がくるまで",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,で`,
            rightId = IdDefConstants.`助詞,格助詞,一般,*,*,*,が`,
            cost = 4001,
            tango = "が車で"
        ),
        Dictionary(
            yomi = "よる",
            leftId = IdDefConstants.`名詞,副詞可能,*,*,*,*,*`,
            rightId = IdDefConstants.`名詞,副詞可能,*,*,*,*,*`,
            cost = 1700,
            tango = "夜"
        ),
        Dictionary(
            yomi = "しょうが",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2000,
            tango = "生姜"
        ),
        Dictionary(
            yomi = "しんかんせん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2500,
            tango = "新幹線"
        ),
        Dictionary(
            yomi = "こくさいひ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2300,
            tango = "国債費"
        ),
        Dictionary(
            yomi = "あすぺ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 2500,
            tango = "アスペ"
        ),
    )

    val ENTERTAIMENT_NAME = listOf(
        Dictionary(
            yomi = "たかちゃんねるず",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "貴ちゃんねるず"
        ),
        Dictionary(
            yomi = "たかちゃん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "貴ちゃん"
        ),
    )

    val FOOD_NAME = listOf(
        Dictionary(
            yomi = "にしんそば",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ニシンそば"
        ),
        Dictionary(
            yomi = "にしんそば",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4001,
            tango = "ニシン蕎麦"
        ),
        Dictionary(
            yomi = "にしんそば",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4002,
            tango = "鰊蕎麦"
        ),
    )

    val RESCORE_WORDS = listOf(
        Dictionary(
            yomi = "のも",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,ノ`,
            rightId = IdDefConstants.`助詞,並立助詞,*,*,*,*,や`,
            cost = 2300,
            tango = "のも"
        ),
        Dictionary(
            yomi = "のは",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,ノ`,
            rightId = IdDefConstants.`助詞,係助詞,*,*,*,*,は`,
            cost = 1500,
            tango = "のは"
        ),
        Dictionary(
            yomi = "ころん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 3000,
            tango = "コロン"
        ),
        Dictionary(
            yomi = "せつぜんぶ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 8500,
            tango = "楔前部"
        ),
    )

    val ADDS_NEW_WORDS = listOf(
        Dictionary(
            yomi = "たこわさ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "たこわさ"
        ),
        Dictionary(
            yomi = "すもももももももものうち",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "季も桃も桃のうち"
        ),
        Dictionary(
            yomi = "あかずの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "開かずの"
        ),
        Dictionary(
            yomi = "のいち",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            cost = 2500,
            tango = "の位置"
        ),
        Dictionary(
            yomi = "をふる",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ラ行,基本形,ある`,
            rightId = IdDefConstants.`助詞,格助詞,一般,*,*,*,を`,
            cost = 3800,
            tango = "を振る"
        ),
        Dictionary(
            yomi = "をふっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ラ行,連用タ接続,ある`,
            rightId = IdDefConstants.`助詞,格助詞,一般,*,*,*,を`,
            cost = 3800,
            tango = "を振っ"
        ),
        Dictionary(
            yomi = "がふる",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ラ行,基本形,ある`,
            rightId = IdDefConstants.`助詞,格助詞,一般,*,*,*,が`,
            cost = 3800,
            tango = "が降る"
        ),
        Dictionary(
            yomi = "がふっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ラ行,連用タ接続,ある`,
            rightId = IdDefConstants.`助詞,格助詞,一般,*,*,*,が`,
            cost = 3800,
            tango = "が降っ"
        ),
        Dictionary(
            yomi = "なた", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 3500, tango = "鉈"
        ),
        Dictionary(
            yomi = "なた", leftId = `名詞,一般,*,*,*,*,*`, rightId = `名詞,一般,*,*,*,*,*`, cost = 3600, tango = "なた"
        ),
        Dictionary(
            yomi = "てんじゅくねずみ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "天竺鼠"
        ),
        Dictionary(
            yomi = "あおうめのどく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "青梅の毒"
        ),
        Dictionary(
            yomi = "あらわれたしんせい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "現れた新星"
        ),
        Dictionary(
            yomi = "いぬはか",
            leftId = IdDefConstants.`助詞,副助詞／並立助詞／終助詞,*,*,*,*,か`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "犬派か"
        ),
        Dictionary(
            yomi = "ねこはか",
            leftId = IdDefConstants.`助詞,副助詞／並立助詞／終助詞,*,*,*,*,か`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "猫派か"
        ),
        Dictionary(
            yomi = "かりかりのきじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "カリカリの生地"
        ),
        Dictionary(
            yomi = "かわじゃけ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "革ジャケ"
        ),
        Dictionary(
            yomi = "かんぜんにつんだ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "完全に詰んだ"
        ),
        Dictionary(
            yomi = "ちゅうれい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "昼礼"
        ),
        Dictionary(
            yomi = "ちゅうれいのあと",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 8000,
            tango = "昼礼の後"
        ),
        Dictionary(
            yomi = "ぎゅうにゅうかん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "牛乳かん"
        ),
        Dictionary(
            yomi = "くうちょくび",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "空直日"
        ),
        Dictionary(
            yomi = "けいこくはいた",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・タ,基本形,た`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "警告吐いた"
        ),
        Dictionary(
            yomi = "ぜんちしゅうしょく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "前置修飾"
        ),
        Dictionary(
            yomi = "こえだしてくれる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "声出してくれる"
        ),
        Dictionary(
            yomi = "さなえのみくす",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "サナエノミクス"
        ),
        Dictionary(
            yomi = "さゆうりょうもも",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "左右両もも"
        ),
        Dictionary(
            yomi = "さんまさしていしょく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "サンマ刺し定食"
        ),
        Dictionary(
            yomi = "さんまさし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "サンマ刺し"
        ),
        Dictionary(
            yomi = "ざんかほしょうがく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "残価保証額"
        ),
        Dictionary(
            yomi = "しにけん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "死に券"
        ),
        Dictionary(
            yomi = "しゃこうこーてぃんぐ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "遮光コーティング"
        ),
        Dictionary(
            yomi = "しゅうききゅうぎょうび",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "秋期休業日"
        ),
        Dictionary(
            yomi = "しゅったつのぜん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "出立の膳"
        ),
        Dictionary(
            yomi = "ぜんいんてき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "全員敵"
        ),
        Dictionary(
            yomi = "ちょうようせつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "重陽節"
        ),
        Dictionary(
            yomi = "とんとろどん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "豚トロ丼"
        ),
        Dictionary(
            yomi = "ばんせんかね",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ラ行,体言接続特殊,なる`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "番宣兼ね"
        ),
        Dictionary(
            yomi = "ばんせんをかね",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・ラ行,体言接続特殊,なる`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "番宣を兼ね"
        ),
        Dictionary(
            yomi = "ぶかつせい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "部活生"
        ),
        Dictionary(
            yomi = "ぶつりしむ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "物理SIM"
        ),
        Dictionary(
            yomi = "ほけんこうかいじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "保険更改時"
        ),
        Dictionary(
            yomi = "まきべりー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "マキベリー"
        ),
        Dictionary(
            yomi = "まるちがい",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・カ行イ音便,未然ウ接続,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "マルチ買い"
        ),
        Dictionary(
            yomi = "よわのつき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "夜半の月"
        ),
        Dictionary(
            yomi = "りょうきょくたんにふれる",
            leftId = IdDefConstants.`動詞,非自立,*,*,一段,仮定形,振れる`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "両極端に振れる"
        ),
        Dictionary(
            yomi = "きょくたんにふれる",
            leftId = IdDefConstants.`動詞,非自立,*,*,一段,仮定形,振れる`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "極端に振れる"
        ),
        Dictionary(
            yomi = "かたとんとん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "肩トントン"
        ),
        Dictionary(
            yomi = "かみがたとえど",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "上方と江戸"
        ),
        Dictionary(
            yomi = "ぎりごぜんちゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "ギリ午前中"
        ),
        Dictionary(
            yomi = "くうこうよりどうじょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "空港より同乗"
        ),
        Dictionary(
            yomi = "くうこうからどうじょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "空港から同乗"
        ),
        Dictionary(
            yomi = "くうこうでどうじょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "空港で同乗"
        ),
        Dictionary(
            yomi = "こりあんがい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "コリアン街"
        ),
        Dictionary(
            yomi = "ごじょうぼうし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "誤乗防止"
        ),
        Dictionary(
            yomi = "しゅうえきはげん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "収益は減"
        ),
        Dictionary(
            yomi = "じゅうでんのへり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "充電の減り"
        ),
        Dictionary(
            yomi = "ぜんけんおーそり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "全件オーソリ"
        ),
        Dictionary(
            yomi = "ちるちるとみちる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "チルチルとミチル"
        ),
        Dictionary(
            yomi = "なんぶんのいちか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "何分の一か"
        ),
        Dictionary(
            yomi = "びょうきでたかい",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "病気で他界"
        ),
        Dictionary(
            yomi = "ぶいぽいんと",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "Vポイント"
        ),
        Dictionary(
            yomi = "るぱんさんじょう",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "ルパン参上"
        ),
        Dictionary(
            yomi = "ろぐをかけ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "ログを書け"
        ),
        Dictionary(
            yomi = "われをしゅうり",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "割れを修理"
        ),
        Dictionary(
            yomi = "おやへのこうこう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "親への孝行"
        ),
        Dictionary(
            yomi = "おやにこうこう",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "親に孝行"
        ),
        Dictionary(
            yomi = "かくはんに",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,に`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "各班に"
        ),
        Dictionary(
            yomi = "かざせばあく",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・カ行イ音便,基本形,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "かざせば開く"
        ),
        Dictionary(
            yomi = "かならずこい",
            leftId = IdDefConstants.`動詞,自立,*,*,カ変・クル,命令ｉ,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "必ず来い"
        ),
        Dictionary(
            yomi = "かんかんぼうし",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "カンカン帽子"
        ),
        Dictionary(
            yomi = "がっきはじめ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "学期初め"
        ),
        Dictionary(
            yomi = "きょうようぶしょうめい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "共用部照明"
        ),
        Dictionary(
            yomi = "ぐたいてきにつめ",
            leftId = `動詞,自立,*,*,一段,連用形,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "具体的に詰め"
        ),
        Dictionary(
            yomi = "こうかをはしる",
            leftId = `動詞,自立,*,*,五段動詞,基本形,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "高架を走る"
        ),
        Dictionary(
            yomi = "こうかをはしっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段動詞,連用タ接続,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "高架を走っ"
        ),
        Dictionary(
            yomi = "こきょうの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "故郷の"
        ),
        Dictionary(
            yomi = "こめといで",
            leftId = IdDefConstants.`助詞,接続助詞,*,*,*,*,で`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "米研いで"
        ),
        Dictionary(
            yomi = "ごうはふかい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "業は深い"
        ),
        Dictionary(
            yomi = "ごうがふかい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "業が深い"
        ),
        Dictionary(
            yomi = "さいかいかいひ",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "最下位回避"
        ),
        Dictionary(
            yomi = "さいされつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "最左列"
        ),
        Dictionary(
            yomi = "さんりんとらっく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "三輪トラック"
        ),
        Dictionary(
            yomi = "せいかせんたー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "青果センター"
        ),
        Dictionary(
            yomi = "ちゅういりこーひー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "中煎りコーヒー"
        ),
        Dictionary(
            yomi = "とらふぃっくかた",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "トラフィック過多"
        ),
        Dictionary(
            yomi = "はいらいとしょく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "ハイライト色"
        ),
        Dictionary(
            yomi = "みずからにかす",
            leftId = `動詞,自立,*,*,五段動詞,基本形,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "自らに課す"
        ),
        Dictionary(
            yomi = "せんゆうりょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "占有量"
        ),
        Dictionary(
            yomi = "ようえんごしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "要援護者"
        ),
        Dictionary(
            yomi = "ようえんごしゃのかいじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "要援護者の介助"
        ),
        Dictionary(
            yomi = "ようかいごしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "要介護者"
        ),
        Dictionary(
            yomi = "れいせいをかい",
            leftId = IdDefConstants.`動詞,自立,*,*,五段・カ行イ音便,連用タ接続,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "冷静を欠い"
        ),
        Dictionary(
            yomi = "れっとうじしん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "列島地震"
        ),
        Dictionary(
            yomi = "えこしよう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "エコ仕様"
        ),
        Dictionary(
            yomi = "しんせんなかいせん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "新鮮な海鮮"
        ),
        Dictionary(
            yomi = "ごうかなかいせん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "豪華な海鮮"
        ),
        Dictionary(
            yomi = "かいせんせんべい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "海鮮せんべい"
        ),
        Dictionary(
            yomi = "かいれいやー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "下位レイヤー"
        ),
        Dictionary(
            yomi = "かんしょくをしない",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・ナイ,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "間食をしない"
        ),
        Dictionary(
            yomi = "きゅうようがはいる",
            leftId = `動詞,自立,*,*,五段動詞,基本形,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "急用が入る"
        ),
        Dictionary(
            yomi = "きゅうようがはいっ",
            leftId = IdDefConstants.`動詞,自立,*,*,五段動詞,連用タ接続,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "急用が入っ"
        ),
        Dictionary(
            yomi = "きょうとしせい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "京都市政"
        ),
        Dictionary(
            yomi = "ぎょうむのみえるか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 6000,
            tango = "業務の見える化"
        ),
        Dictionary(
            yomi = "くりすたるしゃいん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "クリスタルシャイン"
        ),
        Dictionary(
            yomi = "げきよわ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "激弱"
        ),
        Dictionary(
            yomi = "げっきゅうぎ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "月球儀"
        ),
        Dictionary(
            yomi = "こうくうせんじょうざい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "口腔洗浄剤"
        ),
        Dictionary(
            yomi = "こうしゅうきつえんじょ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "公衆喫煙所"
        ),
        Dictionary(
            yomi = "こうせいさいかん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "高精細感"
        ),
        Dictionary(
            yomi = "こんしんのせき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "懇親の席"
        ),
        Dictionary(
            yomi = "さいぶーつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "サイブーツ"
        ),
        Dictionary(
            yomi = "しわけかんりょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "仕分け完了"
        ),
        Dictionary(
            yomi = "たちかいぎ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "立ち会議"
        ),
        Dictionary(
            yomi = "どようびはつ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "土曜日発"
        ),
        Dictionary(
            yomi = "どられこおうしゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "ドラレコ押収"
        ),
        Dictionary(
            yomi = "のどからから",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "喉カラカラ"
        ),
        Dictionary(
            yomi = "ひろうぬき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "疲労抜き"
        ),
        Dictionary(
            yomi = "ぷろばいだりょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "プロバイダ料"
        ),
        Dictionary(
            yomi = "みあったせいか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "見合った成果"
        ),
        Dictionary(
            yomi = "らっくのちゅうだん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 7000,
            tango = "ラックの中段"
        ),
        Dictionary(
            yomi = "あてんどよういん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "アテンド要員"
        ),
        Dictionary(
            yomi = "あみやきき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "網焼き器"
        ),
        Dictionary(
            yomi = "いためめん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "炒め麺"
        ),
        Dictionary(
            yomi = "いんかったー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "インカッター"
        ),
        Dictionary(
            yomi = "えいきゅうできん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "永久出禁"
        ),
        Dictionary(
            yomi = "えつらんとうしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "閲覧謄写"
        ),
        Dictionary(
            yomi = "おやからかんどう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "親から勘当"
        ),
        Dictionary(
            yomi = "おやにかんどう",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "親に勘当"
        ),
        Dictionary(
            yomi = "かいごきゅう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "介護休"
        ),
        Dictionary(
            yomi = "かいせきかい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "解析解"
        ),
        Dictionary(
            yomi = "かんきのできない",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・ナイ,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "換気のできない"
        ),
        Dictionary(
            yomi = "かんしょくがおおい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "間食が多い"
        ),
        Dictionary(
            yomi = "かんしょくのおおい",
            leftId = IdDefConstants.`形容詞,自立,*,*,形容詞・アウオ段,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "間食の多い"
        ),
        Dictionary(
            yomi = "かんせいねさげ",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "官製値下げ"
        ),
        Dictionary(
            yomi = "かんぬきじょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "かんぬき錠"
        ),
        Dictionary(
            yomi = "かんれきのたいやく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "還暦の大厄"
        ),
        Dictionary(
            yomi = "きよつきょうけいこく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "清津峡渓谷"
        ),
        Dictionary(
            yomi = "けんげんのぶんしょう",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "権限の分掌"
        ),
        Dictionary(
            yomi = "がいさ",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "概査"
        ),
        Dictionary(
            yomi = "さいだーあめ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "サイダー飴"
        ),
        Dictionary(
            yomi = "しゅっけつとうろく",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "出欠登録"
        ),
        Dictionary(
            yomi = "しんの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "芯の"
        ),
        Dictionary(
            yomi = "しんが",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,が`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "芯が"
        ),
        Dictionary(
            yomi = "しんを",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,を`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "芯を"
        ),
        Dictionary(
            yomi = "せきりょうのかん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "寂寥の感"
        ),
        Dictionary(
            yomi = "たいしょうもだにずむ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "大正モダニズム"
        ),
        Dictionary(
            yomi = "ちょうこんでる",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "超混んでる"
        ),
        Dictionary(
            yomi = "ちょうへんどうが",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "長編動画"
        ),
        Dictionary(
            yomi = "がてんけい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 3000,
            tango = "ガテン系"
        ),
        Dictionary(
            yomi = "てんきさきの",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "転記先の"
        ),
        Dictionary(
            yomi = "とうかへもぐろびん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "糖化ヘモグロビン"
        ),
        Dictionary(
            yomi = "ぱりぴしよう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "パリピ仕様"
        ),
        Dictionary(
            yomi = "ゆうたいばん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "優待版"
        ),
        Dictionary(
            yomi = "きしゃのきしゃ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "貴社の記者"
        ),
        Dictionary(
            yomi = "きしゃできしゃ",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "汽車で帰社"
        ),
        Dictionary(
            yomi = "あまずだれ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "甘酢だれ"
        ),
        Dictionary(
            yomi = "おぜとくら",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "尾瀬戸倉"
        ),
        Dictionary(
            yomi = "おりでん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "折り電"
        ),
        Dictionary(
            yomi = "かってふみきり",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "勝手踏切"
        ),
        Dictionary(
            yomi = "きかんきょういん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "基幹教員"
        ),
        Dictionary(
            yomi = "きしゅへんじ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "機種変時"
        ),
        Dictionary(
            yomi = "きせいちゅうの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5000,
            tango = "帰省中の"
        ),
        Dictionary(
            yomi = "きせいちゅうの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5100,
            tango = "規制中の"
        ),
        Dictionary(
            yomi = "きせいちゅうの",
            leftId = IdDefConstants.`助詞,連体化,*,*,*,*,の`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 5200,
            tango = "寄生虫の"
        ),
        Dictionary(
            yomi = "きってぼん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "切手盆"
        ),
        Dictionary(
            yomi = "きんひろう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "筋疲労"
        ),
        Dictionary(
            yomi = "護摩供養",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "ごまくよう"
        ),
        Dictionary(
            yomi = "さいずをしょうに",
            leftId = IdDefConstants.`助詞,格助詞,一般,*,*,*,に`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "サイズを小に"
        ),
        Dictionary(
            yomi = "ざいじかん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "座位時間"
        ),
        Dictionary(
            yomi = "しょくとれ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "食トレ"
        ),
        Dictionary(
            yomi = "しんにゅうりょうせい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "新入寮生"
        ),
        Dictionary(
            yomi = "じきけんちしき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "磁気検知式"
        ),
        Dictionary(
            yomi = "じっそうさい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "実装差異"
        ),
        Dictionary(
            yomi = "すぱちゃがく",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "スパチャ額"
        ),
        Dictionary(
            yomi = "そうせんじょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "槽洗浄"
        ),
        Dictionary(
            yomi = "たいかろっかー",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "耐火ロッカー"
        ),
        Dictionary(
            yomi = "だいすうかいせき",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "代数解析"
        ),
        Dictionary(
            yomi = "ちるする",
            leftId = IdDefConstants.`動詞,自立,*,*,サ変・スル,基本形,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "チルする"
        ),
        Dictionary(
            yomi = "ていじせいやかんぶ",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "定時制夜間部"
        ),
        Dictionary(
            yomi = "でんわのちゃっこ",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "電話の着呼"
        ),
        Dictionary(
            yomi = "とうじょうしょうめい",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "搭乗証明"
        ),
        Dictionary(
            yomi = "ながくおさない",
            leftId = IdDefConstants.`助動詞,*,*,*,特殊・ナイ,基本形,ない`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "長く押さない"
        ),
        Dictionary(
            yomi = "ぱすわーどべっそう",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "パスワード別送"
        ),
        Dictionary(
            yomi = "ひだりじょうだん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "左上段"
        ),
        Dictionary(
            yomi = "みぎじょうだん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "右上段"
        ),
        Dictionary(
            yomi = "ほんだいぶぶん",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "本題部分"
        ),
        Dictionary(
            yomi = "ほんとうざい",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "ほんとうざい"
        ),
        Dictionary(
            yomi = "わちゅうてんそう",
            leftId = IdDefConstants.`名詞,サ変接続,*,*,*,*,上京`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "話中転送"
        ),
        Dictionary(
            yomi = "わはっか",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "和ハッカ"
        ),
        Dictionary(
            yomi = "おれいはさんぎょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4501,
            tango = "お礼は3行"
        ),
        Dictionary(
            yomi = "おれいはさんぎょう",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4500,
            tango = "お礼は三行"
        ),
    )

    val PLACE = listOf(
        Dictionary(
            yomi = "あきのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "安芸国"
        ),
        Dictionary(
            yomi = "あそうわん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "浅海湾"
        ),
        Dictionary(
            yomi = "あつべつ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "厚別"
        ),
        Dictionary(
            yomi = "あつべつく",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "厚別区"
        ),
        Dictionary(
            yomi = "あわじのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "淡路国"
        ),
        Dictionary(
            yomi = "あわのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "安房国"
        ),
        Dictionary(
            yomi = "あわのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "阿波国"
        ),
        Dictionary(
            yomi = "いがのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "伊賀国"
        ),
        Dictionary(
            yomi = "いきのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "壱岐国"
        ),
        Dictionary(
            yomi = "いしかりのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "石狩国"
        ),
        Dictionary(
            yomi = "いずのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "伊豆国"
        ),
        Dictionary(
            yomi = "いずみのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "和泉国"
        ),
        Dictionary(
            yomi = "いずものくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "出雲国"
        ),
        Dictionary(
            yomi = "いせのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "伊勢国"
        ),
        Dictionary(
            yomi = "いとうおんせん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "伊東温泉"
        ),
        Dictionary(
            yomi = "いとしの",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "愛し野"
        ),
        Dictionary(
            yomi = "いねこき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "稲㧡"
        ),
        Dictionary(
            yomi = "いぶりのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "胆振国"
        ),
        Dictionary(
            yomi = "いよのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "伊予国"
        ),
        Dictionary(
            yomi = "いりなか",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "杁中"
        ),
        Dictionary(
            yomi = "いりなかえき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "いりなか駅"
        ),
        Dictionary(
            yomi = "いわきのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "磐城国"
        ),
        Dictionary(
            yomi = "いわしろのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "岩代国"
        ),
        Dictionary(
            yomi = "いんちょん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "仁川"
        ),
        Dictionary(
            yomi = "うごのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "羽後国"
        ),
        Dictionary(
            yomi = "うぜん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "羽前"
        ),
        Dictionary(
            yomi = "うぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "羽前国"
        ),
        Dictionary(
            yomi = "うとろ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "宇登呂"
        ),
        Dictionary(
            yomi = "うらしべつ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "浦士別"
        ),
        Dictionary(
            yomi = "えちごのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "越後国"
        ),
        Dictionary(
            yomi = "えちぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "越前国"
        ),
        Dictionary(
            yomi = "えっちゅうのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "越中国"
        ),
        Dictionary(
            yomi = "えとんびやま",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "江鳶山"
        ),
        Dictionary(
            yomi = "えんけい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "燕京"
        ),
        Dictionary(
            yomi = "おうみのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "近江国"
        ),
        Dictionary(
            yomi = "おおすみのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "大隅国"
        ),
        Dictionary(
            yomi = "おくも",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "大芋"
        ),
        Dictionary(
            yomi = "おしまのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "渡島国"
        ),
        Dictionary(
            yomi = "おわりのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "尾張国"
        ),
        Dictionary(
            yomi = "おんねない",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "音根内"
        ),
        Dictionary(
            yomi = "おんねべつ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "遠音別"
        ),
        Dictionary(
            yomi = "がいえんまええき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "外苑前駅"
        ),
        Dictionary(
            yomi = "かいのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "甲斐国"
        ),
        Dictionary(
            yomi = "かいふぉん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "開封"
        ),
        Dictionary(
            yomi = "かいほう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "開封"
        ),
        Dictionary(
            yomi = "かがのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "加賀国"
        ),
        Dictionary(
            yomi = "かずさのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "上総国"
        ),
        Dictionary(
            yomi = "かっくみ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "活汲"
        ),
        Dictionary(
            yomi = "かのこだい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "鹿の子台"
        ),
        Dictionary(
            yomi = "かみいたえき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "上伊田駅"
        ),
        Dictionary(
            yomi = "かみとばぐちえき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "上鳥羽口駅"
        ),
        Dictionary(
            yomi = "かわちのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "河内国"
        ),
        Dictionary(
            yomi = "かんまきちょう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "上牧町"
        ),
        Dictionary(
            yomi = "きいのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "紀伊国"
        ),
        Dictionary(
            yomi = "ききん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "木禽"
        ),
        Dictionary(
            yomi = "きたみのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "北見国"
        ),
        Dictionary(
            yomi = "くしろのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "釧路国"
        ),
        Dictionary(
            yomi = "くまのさんざん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "熊野三山"
        ),
        Dictionary(
            yomi = "こうあんれい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "興安嶺"
        ),
        Dictionary(
            yomi = "こうずけのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "上野国"
        ),
        Dictionary(
            yomi = "ごきはちどう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "五畿八道"
        ),
        Dictionary(
            yomi = "こっといえき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "特牛駅"
        ),
        Dictionary(
            yomi = "さいくじょ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "細工所"
        ),
        Dictionary(
            yomi = "さがみのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "相模国"
        ),
        Dictionary(
            yomi = "さかわちょう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "佐川町"
        ),
        Dictionary(
            yomi = "さきむい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "崎無異"
        ),
        Dictionary(
            yomi = "さつまのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "薩摩国"
        ),
        Dictionary(
            yomi = "さどのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "佐渡国"
        ),
        Dictionary(
            yomi = "さぬきのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "讃岐国"
        ),
        Dictionary(
            yomi = "しつかわ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "後川"
        ),
        Dictionary(
            yomi = "しなののくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "信濃国"
        ),
        Dictionary(
            yomi = "しまのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "志摩国"
        ),
        Dictionary(
            yomi = "しもうさなかやま",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "下総中山"
        ),
        Dictionary(
            yomi = "しもうさのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "下総国"
        ),
        Dictionary(
            yomi = "しもつけのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "下野国"
        ),
        Dictionary(
            yomi = "しゅかい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "珠海"
        ),
        Dictionary(
            yomi = "しょうこうあんれい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "小興安嶺"
        ),
        Dictionary(
            yomi = "しょうこうあんれいさんみゃく",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "小興安嶺山脈"
        ),
        Dictionary(
            yomi = "しりべしのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "後志国"
        ),
        Dictionary(
            yomi = "しんせん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "深圳"
        ),
        Dictionary(
            yomi = "じんせん",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "仁川"
        ),
        Dictionary(
            yomi = "すおうのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "周防国"
        ),
        Dictionary(
            yomi = "するがのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "駿河国"
        ),
        Dictionary(
            yomi = "せっつのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "摂津国"
        ),
        Dictionary(
            yomi = "そうかまつばら",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "草加松原"
        ),
        Dictionary(
            yomi = "だいこうあんれい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "大興安嶺"
        ),
        Dictionary(
            yomi = "だいこうあんれいさんみゃく",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "大興安嶺山脈"
        ),
        Dictionary(
            yomi = "たいほく",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "台北"
        ),
        Dictionary(
            yomi = "たけしばえき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "竹芝駅"
        ),
        Dictionary(
            yomi = "たごうら",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "田子浦"
        ),
        Dictionary(
            yomi = "たちあらい",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "太刀洗"
        ),
        Dictionary(
            yomi = "ちえんべつ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "知円別"
        ),
        Dictionary(
            yomi = "ちくごのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "筑後国"
        ),
        Dictionary(
            yomi = "ちくぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "筑前国"
        ),
        Dictionary(
            yomi = "ちしまのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "千島国"
        ),
        Dictionary(
            yomi = "ちょうせんかいきょう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "朝鮮海峡"
        ),
        Dictionary(
            yomi = "つしまのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "対馬国"
        ),
        Dictionary(
            yomi = "ていしゅう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "鄭州"
        ),
        Dictionary(
            yomi = "てしおのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "天塩国"
        ),
        Dictionary(
            yomi = "でわのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "出羽国"
        ),
        Dictionary(
            yomi = "とおとうみのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "遠江国"
        ),
        Dictionary(
            yomi = "とかちのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "十勝国"
        ),
        Dictionary(
            yomi = "とさのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "土佐国"
        ),
        Dictionary(
            yomi = "とちょうまええき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "都庁前駅"
        ),
        Dictionary(
            yomi = "とっぷし",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "富武士"
        ),
        Dictionary(
            yomi = "とどがさき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "魹ヶ崎"
        ),
        Dictionary(
            yomi = "なかさと",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "中佐都"
        ),
        Dictionary(
            yomi = "ながとのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "長門国"
        ),
        Dictionary(
            yomi = "なんかいどう",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "南海道"
        ),
        Dictionary(
            yomi = "にしきょうく",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "西京区"
        ),
        Dictionary(
            yomi = "にほんだいら",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "日本平"
        ),
        Dictionary(
            yomi = "ぬぬき",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "沼貫"
        ),
        Dictionary(
            yomi = "ねぶたに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "掖谷"
        ),
        Dictionary(
            yomi = "ねむろのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "根室国"
        ),
        Dictionary(
            yomi = "のとのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "能登国"
        ),
        Dictionary(
            yomi = "はまひがしま",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "浜比嘉島"
        ),
        Dictionary(
            yomi = "はりまのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "播磨国"
        ),
        Dictionary(
            yomi = "はんきゅううめだ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "阪急梅田"
        ),
        Dictionary(
            yomi = "ひかりの",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "ひかり野"
        ),
        Dictionary(
            yomi = "ひごのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "肥後国"
        ),
        Dictionary(
            yomi = "びぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "備前国"
        ),
        Dictionary(
            yomi = "ひぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "肥前国"
        ),
        Dictionary(
            yomi = "ひだかのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "日高国"
        ),
        Dictionary(
            yomi = "ひたちのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "常陸国"
        ),
        Dictionary(
            yomi = "ひだのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "飛騨国"
        ),
        Dictionary(
            yomi = "ひだのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "飛驒国"
        ),
        Dictionary(
            yomi = "びっちゅうのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "備中国"
        ),
        Dictionary(
            yomi = "ひゅうがのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "日向国"
        ),
        Dictionary(
            yomi = "びんごのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "備後国"
        ),
        Dictionary(
            yomi = "ふじさんろく",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "富士山麓"
        ),
        Dictionary(
            yomi = "ぶぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "豊前国"
        ),
        Dictionary(
            yomi = "ぶんごのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "豊後国"
        ),
        Dictionary(
            yomi = "みかわのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "三河国"
        ),
        Dictionary(
            yomi = "みどり",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "美禽"
        ),
        Dictionary(
            yomi = "みぬめ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "敏馬"
        ),
        Dictionary(
            yomi = "みののくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "美濃国"
        ),
        Dictionary(
            yomi = "みまさかのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "美作国"
        ),
        Dictionary(
            yomi = "みるめ",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "敏馬"
        ),
        Dictionary(
            yomi = "むさしのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "武蔵国"
        ),
        Dictionary(
            yomi = "むつのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "陸奥国"
        ),
        Dictionary(
            yomi = "もとやわた",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "本八幡"
        ),
        Dictionary(
            yomi = "やましろのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "山城国"
        ),
        Dictionary(
            yomi = "やまとのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "大和国"
        ),
        Dictionary(
            yomi = "りくおうのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "陸奥国"
        ),
        Dictionary(
            yomi = "りくぜんのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "陸前国"
        ),
        Dictionary(
            yomi = "りくちゅうのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "陸中国"
        ),
        Dictionary(
            yomi = "りゅうきゅうのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "琉球国"
        ),
        Dictionary(
            yomi = "わかさのくに",
            leftId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            rightId = IdDefConstants.`名詞,固有名詞,地域,一般,*,*,*`,
            cost = 4000,
            tango = "若狭国"
        )
    )

    val WORDS = listOf(
        Dictionary(
            yomi = "CJKごかんかんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "CJK互換漢字"
        ),
        Dictionary(
            yomi = "CJKごかんようもじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "CJK互換用文字"
        ),
        Dictionary(
            yomi = "CJKとうごうかんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "CJK統合漢字"
        ),
        Dictionary(
            yomi = "FCとうきょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "FC東京"
        ),
        Dictionary(
            yomi = "FCまちだぜるびあ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "FC町田ゼルビア"
        ),
        Dictionary(
            yomi = "PFAS",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "PFAS"
        ),
        Dictionary(
            yomi = "あいしんかくら",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "愛新覚羅"
        ),
        Dictionary(
            yomi = "あおぞらぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "あおぞら銀行"
        ),
        Dictionary(
            yomi = "あくろばてぃっく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "アクロバティック"
        ),
        Dictionary(
            yomi = "あごだし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "あご出汁"
        ),
        Dictionary(
            yomi = "あさごはん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "朝ごはん"
        ),
        Dictionary(
            yomi = "あさごはん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "朝ご飯"
        ),
        Dictionary(
            yomi = "あてぬの",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "当て布"
        ),
        Dictionary(
            yomi = "あびすぱ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "アビスパ"
        ),
        Dictionary(
            yomi = "あびすぱふくおか",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "アビスパ福岡"
        ),
        Dictionary(
            yomi = "あもせ",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "阿茂瀬"
        ),
        Dictionary(
            yomi = "あるびれっくす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "アルビレックス"
        ),
        Dictionary(
            yomi = "あるびれっくすにいがた",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "アルビレックス新潟"
        ),
        Dictionary(
            yomi = "あんこめんと",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "アンコメント"
        ),
        Dictionary(
            yomi = "あんとらーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "アントラーズ"
        ),
        Dictionary(
            yomi = "あんのい",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "安ノ井"
        ),
        Dictionary(
            yomi = "いーぐるす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "イーグルス"
        ),
        Dictionary(
            yomi = "いえけい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "家系"
        ),
        Dictionary(
            yomi = "いおまぐぬっそ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "イオマグヌッソ"
        ),
        Dictionary(
            yomi = "いぐのーべるしょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "イグノーベル賞"
        ),
        Dictionary(
            yomi = "いくりんぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "育林業"
        ),
        Dictionary(
            yomi = "いけいざい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "違警罪"
        ),
        Dictionary(
            yomi = "いこみき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "已己巳己"
        ),
        Dictionary(
            yomi = "いただ",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "井唯"
        ),
        Dictionary(
            yomi = "いただきもの",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "頂き物"
        ),
        Dictionary(
            yomi = "いちい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "一意"
        ),
        Dictionary(
            yomi = "いちまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "一万"
        ),
        Dictionary(
            yomi = "いっきょうたじゃく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "一強他弱"
        ),
        Dictionary(
            yomi = "いばらてつどう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "井原鉄道"
        ),
        Dictionary(
            yomi = "いもじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "イ文字"
        ),
        Dictionary(
            yomi = "いもじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "彝文字"
        ),
        Dictionary(
            yomi = "いわぶろ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "岩風呂"
        ),
        Dictionary(
            yomi = "いんきゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "陰キャ"
        ),
        Dictionary(
            yomi = "いんてぃましー",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "intimacy"
        ),
        Dictionary(
            yomi = "いんてぃましー",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "インティマシー"
        ),
        Dictionary(
            yomi = "いんぴ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "隠秘"
        ),
        Dictionary(
            yomi = "いんむ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "淫夢"
        ),
        Dictionary(
            yomi = "ゔぃっせる",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ヴィッセル"
        ),
        Dictionary(
            yomi = "ゔぃっせるこうべ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ヴィッセル神戸"
        ),
        Dictionary(
            yomi = "ゔぇるでぃ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ヴェルディ"
        ),
        Dictionary(
            yomi = "うげん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "迂言"
        ),
        Dictionary(
            yomi = "うすいほん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "薄い本"
        ),
        Dictionary(
            yomi = "うっぷんばらし",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "鬱憤晴らし"
        ),
        Dictionary(
            yomi = "うらめん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "裏面"
        ),
        Dictionary(
            yomi = "うらわれっず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "浦和レッズ"
        ),
        Dictionary(
            yomi = "うりどき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "売り時"
        ),
        Dictionary(
            yomi = "うんてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "芸亭"
        ),
        Dictionary(
            yomi = "えいえいじてん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "英英辞典"
        ),
        Dictionary(
            yomi = "えきねっと",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "えきねっと"
        ),
        Dictionary(
            yomi = "えちぜんてつどう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "えちぜん鉄道"
        ),
        Dictionary(
            yomi = "えつご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "粤語"
        ),
        Dictionary(
            yomi = "えふしーとうきょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "FC東京"
        ),
        Dictionary(
            yomi = "えふしーまちだぜるびあ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "FC町田ゼルビア"
        ),
        Dictionary(
            yomi = "えみー",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "エミー"
        ),
        Dictionary(
            yomi = "えんりゃく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "延暦"
        ),
        Dictionary(
            yomi = "おーぷんきゃりー",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "オープンキャリー"
        ),
        Dictionary(
            yomi = "おおさかいかやっかだいがく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "大阪医科薬科大学"
        ),
        Dictionary(
            yomi = "おおさかこうりつだいがく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "大阪公立大学"
        ),
        Dictionary(
            yomi = "おおつきょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "大津京"
        ),
        Dictionary(
            yomi = "おくぶたえ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "奥二重"
        ),
        Dictionary(
            yomi = "おくりて",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "送り手"
        ),
        Dictionary(
            yomi = "おさらば",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "オサラバ"
        ),
        Dictionary(
            yomi = "おしごと",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "推し事"
        ),
        Dictionary(
            yomi = "おす",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "お酢"
        ),
        Dictionary(
            yomi = "おだいばこ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "お題箱"
        ),
        Dictionary(
            yomi = "おだえいいちろう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "尾田栄一郎"
        ),
        Dictionary(
            yomi = "おにのかくらん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "鬼の霍乱"
        ),
        Dictionary(
            yomi = "おねろり",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "おねロリ"
        ),
        Dictionary(
            yomi = "おりっくす・ばふぁろーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "オリックス・バファローズ"
        ),
        Dictionary(
            yomi = "おりっくすばふぁろーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "オリックスバファローズ"
        ),
        Dictionary(
            yomi = "かーぷ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "カープ"
        ),
        Dictionary(
            yomi = "かいかい",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "回回"
        ),
        Dictionary(
            yomi = "かいごかんせい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "下位互換性"
        ),
        Dictionary(
            yomi = "かいていこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "改訂稿"
        ),
        Dictionary(
            yomi = "かいとうらんま",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "快刀乱麻"
        ),
        Dictionary(
            yomi = "かえがみ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "替紙"
        ),
        Dictionary(
            yomi = "かぎょうしもいちだんかつよう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "カ行下一段活用"
        ),
        Dictionary(
            yomi = "かくしあじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "隠し味"
        ),
        Dictionary(
            yomi = "がくしかてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "学士課程"
        ),
        Dictionary(
            yomi = "かくしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "覚者"
        ),
        Dictionary(
            yomi = "かくしゃく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "赫灼"
        ),
        Dictionary(
            yomi = "かくらん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "霍乱"
        ),
        Dictionary(
            yomi = "かげきは",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "過激派"
        ),
        Dictionary(
            yomi = "かしまあんとらーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "鹿島アントラーズ"
        ),
        Dictionary(
            yomi = "かしゅうじゅ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "過収受"
        ),
        Dictionary(
            yomi = "かじょうわん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "渦状腕"
        ),
        Dictionary(
            yomi = "かしわれいそる",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "柏レイソル"
        ),
        Dictionary(
            yomi = "かねのなるき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "金のなる木"
        ),
        Dictionary(
            yomi = "かぶしきかいしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "株式会社"
        ),
        Dictionary(
            yomi = "かぶしきがいしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "株式会社"
        ),
        Dictionary(
            yomi = "かもふら",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "カモフラ"
        ),
        Dictionary(
            yomi = "からだき",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "空焚き"
        ),
        Dictionary(
            yomi = "かりおき",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "仮置き"
        ),
        Dictionary(
            yomi = "かわきもの",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "乾き物"
        ),
        Dictionary(
            yomi = "かわさきふろんたーれ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "川崎フロンターレ"
        ),
        Dictionary(
            yomi = "かんいかんようじたい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "簡易慣用字体"
        ),
        Dictionary(
            yomi = "かんさいはんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "簡裁判事"
        ),
        Dictionary(
            yomi = "かんさいみらいぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "関西みらい銀行"
        ),
        Dictionary(
            yomi = "かんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "巻次"
        ),
        Dictionary(
            yomi = "かんじこうせいきじゅつもじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "漢字構成記述文字"
        ),
        Dictionary(
            yomi = "かんじょうば",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "勘定場"
        ),
        Dictionary(
            yomi = "かんち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "漢地"
        ),
        Dictionary(
            yomi = "かんちょく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "漢直"
        ),
        Dictionary(
            yomi = "がんば",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ガンバ"
        ),
        Dictionary(
            yomi = "がんばおおさか",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ガンバ大阪"
        ),
        Dictionary(
            yomi = "かんりめいがら",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "監理銘柄"
        ),
        Dictionary(
            yomi = "きーぼーどしょーとかっと",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "キーボードショートカット"
        ),
        Dictionary(
            yomi = "きかんせっけい",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "機関設計"
        ),
        Dictionary(
            yomi = "きけろが",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "キケロガ"
        ),
        Dictionary(
            yomi = "きご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "徽語"
        ),
        Dictionary(
            yomi = "きそう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "寄贈"
        ),
        Dictionary(
            yomi = "きたい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "危殆"
        ),
        Dictionary(
            yomi = "きたいか",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "危殆化"
        ),
        Dictionary(
            yomi = "きたかたらーめん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "喜多方ラーメン"
        ),
        Dictionary(
            yomi = "きたにっぽんしんぶんはい",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "北日本新聞杯"
        ),
        Dictionary(
            yomi = "きっしょく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "喫食"
        ),
        Dictionary(
            yomi = "きったん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "契丹"
        ),
        Dictionary(
            yomi = "きてん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "輝点"
        ),
        Dictionary(
            yomi = "きやく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "既約"
        ),
        Dictionary(
            yomi = "きゅうかんそっかん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "吸汗速乾"
        ),
        Dictionary(
            yomi = "きゅうせいこうこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "旧制高校"
        ),
        Dictionary(
            yomi = "きゅうまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "九万"
        ),
        Dictionary(
            yomi = "ぎゅうめし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "牛めし"
        ),
        Dictionary(
            yomi = "きょうかいかくてい",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "境界確定"
        ),
        Dictionary(
            yomi = "きょうじょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "橋上"
        ),
        Dictionary(
            yomi = "きょうじょうえきしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "橋上駅舎"
        ),
        Dictionary(
            yomi = "きょうじょうかいさつ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "橋上改札"
        ),
        Dictionary(
            yomi = "きょうせいきそ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "強制起訴"
        ),
        Dictionary(
            yomi = "きょうとさんが",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "京都サンガ"
        ),
        Dictionary(
            yomi = "きょうとさんがF.C.",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "京都サンガF.C."
        ),
        Dictionary(
            yomi = "きょうとさんがえふしー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "京都サンガF.C."
        ),
        Dictionary(
            yomi = "きらぼしぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "きらぼし銀行"
        ),
        Dictionary(
            yomi = "ぎんぎん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "誾誾"
        ),
        Dictionary(
            yomi = "きんせんぶんぱいせいきゅうけん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "金銭分配請求権"
        ),
        Dictionary(
            yomi = "きんとれ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "筋トレ"
        ),
        Dictionary(
            yomi = "くうしゅうごう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "空集合"
        ),
        Dictionary(
            yomi = "くうぼうそう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "空乏層"
        ),
        Dictionary(
            yomi = "ぐらんぱす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "グランパス"
        ),
        Dictionary(
            yomi = "くるるぎ",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "枢木"
        ),
        Dictionary(
            yomi = "くれじっとかーどぎょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "クレジットカード業"
        ),
        Dictionary(
            yomi = "くわたけいすけ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "桑田佳祐"
        ),
        Dictionary(
            yomi = "けいゆう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "経由"
        ),
        Dictionary(
            yomi = "けいらんし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "鶏卵紙"
        ),
        Dictionary(
            yomi = "けっかんしゅうしゅく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "血管収縮"
        ),
        Dictionary(
            yomi = "けっていこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "決定稿"
        ),
        Dictionary(
            yomi = "けつりょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "結了"
        ),
        Dictionary(
            yomi = "げんごか",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "言語化"
        ),
        Dictionary(
            yomi = "げんしきょうさんしゅぎ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "原始共産主義"
        ),
        Dictionary(
            yomi = "けんじゅう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "県住"
        ),
        Dictionary(
            yomi = "けんちくせこう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "建築施工"
        ),
        Dictionary(
            yomi = "げんちょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "阮朝"
        ),
        Dictionary(
            yomi = "げんつきいっしゅ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "原付一種"
        ),
        Dictionary(
            yomi = "げんつきにしゅ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "原付二種"
        ),
        Dictionary(
            yomi = "げんな",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "元和"
        ),
        Dictionary(
            yomi = "けんばら",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "権原"
        ),
        Dictionary(
            yomi = "げんゆこうぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "原油鉱業"
        ),
        Dictionary(
            yomi = "げんわ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "元和"
        ),
        Dictionary(
            yomi = "ごーるでんいーぐるす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ゴールデンイーグルス"
        ),
        Dictionary(
            yomi = "ごいりよう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "ご入用"
        ),
        Dictionary(
            yomi = "こういこうしょくしゃはんざいそうさしょ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "高位公職者犯罪捜査処"
        ),
        Dictionary(
            yomi = "こういしつ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "更衣室"
        ),
        Dictionary(
            yomi = "こうえきつうほう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "公益通報"
        ),
        Dictionary(
            yomi = "こうか",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "弘化"
        ),
        Dictionary(
            yomi = "こうきかてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "後期課程"
        ),
        Dictionary(
            yomi = "こうきぶしゅ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "康煕部首"
        ),
        Dictionary(
            yomi = "こうこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "礦坑"
        ),
        Dictionary(
            yomi = "ごうしかいしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "合資会社"
        ),
        Dictionary(
            yomi = "こうじょ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "扣除"
        ),
        Dictionary(
            yomi = "こうせいほごほうじん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "更生保護法人"
        ),
        Dictionary(
            yomi = "こうそうしょ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "公捜処"
        ),
        Dictionary(
            yomi = "こうそけん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "公訴権"
        ),
        Dictionary(
            yomi = "こうにん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "弘仁"
        ),
        Dictionary(
            yomi = "こうばいりょくへいか",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "購買力平価"
        ),
        Dictionary(
            yomi = "こうはんいんさつ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "孔版印刷"
        ),
        Dictionary(
            yomi = "こうぶんかいせきき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "構文解析器"
        ),
        Dictionary(
            yomi = "こうらん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "皇蘭"
        ),
        Dictionary(
            yomi = "ごかんかんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "互換漢字"
        ),
        Dictionary(
            yomi = "こきゅう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "枯朽"
        ),
        Dictionary(
            yomi = "こきゅうきしっかん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "呼吸器疾患"
        ),
        Dictionary(
            yomi = "ごぐん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "語群"
        ),
        Dictionary(
            yomi = "ごじゅうそう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "五重奏"
        ),
        Dictionary(
            yomi = "ことでん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "琴電"
        ),
        Dictionary(
            yomi = "ごばらい",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "後払"
        ),
        Dictionary(
            yomi = "こま",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "独楽"
        ),
        Dictionary(
            yomi = "ごまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "五万"
        ),
        Dictionary(
            yomi = "こめだこーひー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "コメダ珈琲"
        ),
        Dictionary(
            yomi = "こめだこーひーてん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "コメダ珈琲店"
        ),
        Dictionary(
            yomi = "これざね",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "維城"
        ),
        Dictionary(
            yomi = "こんさどーれ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "コンサドーレ"
        ),
        Dictionary(
            yomi = "こんさどーれさっぽろ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "コンサドーレ札幌"
        ),
        Dictionary(
            yomi = "こんせ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "今世"
        ),
        Dictionary(
            yomi = "こんぜ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "今世"
        ),
        Dictionary(
            yomi = "こんせい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "今世"
        ),
        Dictionary(
            yomi = "さいかいじょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "催会場"
        ),
        Dictionary(
            yomi = "さいこん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "再建"
        ),
        Dictionary(
            yomi = "さいしゅうこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "最終稿"
        ),
        Dictionary(
            yomi = "さいじょうひでき",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "西城秀樹"
        ),
        Dictionary(
            yomi = "さいたませいぶらいおんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "埼玉西武ライオンズ"
        ),
        Dictionary(
            yomi = "さいたまりそなぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "埼玉りそな銀行"
        ),
        Dictionary(
            yomi = "ざいにちかきょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "在日華僑"
        ),
        Dictionary(
            yomi = "さいばねきかく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "サイバネ規格"
        ),
        Dictionary(
            yomi = "さいゆうすいてい",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "最尤推定"
        ),
        Dictionary(
            yomi = "さがしもの",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "探し物"
        ),
        Dictionary(
            yomi = "さかもとりゅういち",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "坂本龍一"
        ),
        Dictionary(
            yomi = "さがん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "サガン"
        ),
        Dictionary(
            yomi = "さがんとす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "サガン鳥栖"
        ),
        Dictionary(
            yomi = "さぶすく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "サブスク"
        ),
        Dictionary(
            yomi = "さらっと",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "さらっと"
        ),
        Dictionary(
            yomi = "さらっと",
            leftId = `名詞,一般,*,*,*,*,*`,
            rightId = `名詞,一般,*,*,*,*,*`,
            cost = 4000,
            tango = "サラッと"
        ),
        Dictionary(
            yomi = "さんが",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "サンガ"
        ),
        Dictionary(
            yomi = "さんけん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "産繭"
        ),
        Dictionary(
            yomi = "さんけんしょりとうせいほう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "産繭処理統制法"
        ),
        Dictionary(
            yomi = "さんこうにんしょうち",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "参考人招致"
        ),
        Dictionary(
            yomi = "さんしゃしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "三斜晶"
        ),
        Dictionary(
            yomi = "さんせりふたい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "サンセリフ体"
        ),
        Dictionary(
            yomi = "さんふれっちぇ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "サンフレッチェ"
        ),
        Dictionary(
            yomi = "さんふれっちぇひろしま",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "サンフレッチェ広島"
        ),
        Dictionary(
            yomi = "さんまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "三万"
        ),
        Dictionary(
            yomi = "じーくあくす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "GQuuuuuuX"
        ),
        Dictionary(
            yomi = "じーくあくす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ジークアクス"
        ),
        Dictionary(
            yomi = "じきしょうそう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "時期尚早"
        ),
        Dictionary(
            yomi = "しごでき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "しごでき"
        ),
        Dictionary(
            yomi = "じごな",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "地粉"
        ),
        Dictionary(
            yomi = "じし",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "自死"
        ),
        Dictionary(
            yomi = "じしいぞく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "自死遺族"
        ),
        Dictionary(
            yomi = "ししゅう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "歯周"
        ),
        Dictionary(
            yomi = "しっちゃく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "失着"
        ),
        Dictionary(
            yomi = "しっちゅう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "失注"
        ),
        Dictionary(
            yomi = "じってんぽ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "実店舗"
        ),
        Dictionary(
            yomi = "しなごは",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "シナ語派"
        ),
        Dictionary(
            yomi = "じぶんぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "じぶん銀行"
        ),
        Dictionary(
            yomi = "じゃいあんつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ジャイアンツ"
        ),
        Dictionary(
            yomi = "しゃかいほけんろうむしほうじん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "社会保険労務士法人"
        ),
        Dictionary(
            yomi = "じやさい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "地野菜"
        ),
        Dictionary(
            yomi = "しゃしんしょくじ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "写真植字"
        ),
        Dictionary(
            yomi = "しゃほうけい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "斜方形"
        ),
        Dictionary(
            yomi = "しゅうぎかい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "州議会"
        ),
        Dictionary(
            yomi = "しゅうこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "州侯"
        ),
        Dictionary(
            yomi = "しゅうしかてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "修士課程"
        ),
        Dictionary(
            yomi = "しゅうじゅう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "集住"
        ),
        Dictionary(
            yomi = "しゅうじんかんし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "衆人環視"
        ),
        Dictionary(
            yomi = "しゅうせいこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "修正稿"
        ),
        Dictionary(
            yomi = "じゅうまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "十万"
        ),
        Dictionary(
            yomi = "しゅじょうさいど",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "衆生済度"
        ),
        Dictionary(
            yomi = "しゅっとん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "出音"
        ),
        Dictionary(
            yomi = "しゅはり",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "守破離"
        ),
        Dictionary(
            yomi = "じゅびろ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ジュビロ"
        ),
        Dictionary(
            yomi = "じゅびろいわた",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ジュビロ磐田"
        ),
        Dictionary(
            yomi = "しょうあく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "性悪"
        ),
        Dictionary(
            yomi = "じょういごかんせい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "上位互換性"
        ),
        Dictionary(
            yomi = "しょうおう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "承応"
        ),
        Dictionary(
            yomi = "じょうおう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "承応"
        ),
        Dictionary(
            yomi = "じょうざんかきょう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "上山下郷"
        ),
        Dictionary(
            yomi = "しょうしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "盛者"
        ),
        Dictionary(
            yomi = "しょうじゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "盛者"
        ),
        Dictionary(
            yomi = "しょうしゃひっすい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "盛者必衰"
        ),
        Dictionary(
            yomi = "しょうじゃひっすい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "盛者必衰"
        ),
        Dictionary(
            yomi = "じょうしゃひっすい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "盛者必衰"
        ),
        Dictionary(
            yomi = "しょうじんか",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "省人化"
        ),
        Dictionary(
            yomi = "しょうなんべるまーれ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "湘南ベルマーレ"
        ),
        Dictionary(
            yomi = "しょうりょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "秤量"
        ),
        Dictionary(
            yomi = "しんがいかくめい",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "辛亥革命"
        ),
        Dictionary(
            yomi = "しんかん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "身幹"
        ),
        Dictionary(
            yomi = "しんきとうろく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "新規登録"
        ),
        Dictionary(
            yomi = "しんご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "身後"
        ),
        Dictionary(
            yomi = "じんじょうこうとうしょうがっこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "尋常高等小学校"
        ),
        Dictionary(
            yomi = "じんじょうしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "尋常小"
        ),
        Dictionary(
            yomi = "じんじょうしょうがっこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "尋常小学校"
        ),
        Dictionary(
            yomi = "しんしょかいふうざい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "信書開封罪"
        ),
        Dictionary(
            yomi = "しんせいぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "新生銀行"
        ),
        Dictionary(
            yomi = "しんちとせくうこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "新千歳空港"
        ),
        Dictionary(
            yomi = "すいぎょーざ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "水餃子"
        ),
        Dictionary(
            yomi = "すいくち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "吸い口"
        ),
        Dictionary(
            yomi = "すきまばいと",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "スキマバイト"
        ),
        Dictionary(
            yomi = "すざくもん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "朱雀門"
        ),
        Dictionary(
            yomi = "すみけし",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "墨消し"
        ),
        Dictionary(
            yomi = "すみしん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "住信"
        ),
        Dictionary(
            yomi = "すらんと",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "スラント"
        ),
        Dictionary(
            yomi = "すわろーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "スワローズ"
        ),
        Dictionary(
            yomi = "せいしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "盛者"
        ),
        Dictionary(
            yomi = "せいしんたんぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "製薪炭業"
        ),
        Dictionary(
            yomi = "せいしんやまてせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "西神・山手線"
        ),
        Dictionary(
            yomi = "せいしんやまてせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "西神山手線"
        ),
        Dictionary(
            yomi = "せいぶらいおんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "西武ライオンズ"
        ),
        Dictionary(
            yomi = "せいほうしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "正方晶"
        ),
        Dictionary(
            yomi = "せいりめいがら",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "整理銘柄"
        ),
        Dictionary(
            yomi = "せきたんこうぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "石炭鉱業"
        ),
        Dictionary(
            yomi = "せきにんひょうじ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "責任表示"
        ),
        Dictionary(
            yomi = "せきゆせいせいぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "石油精製業"
        ),
        Dictionary(
            yomi = "せっせん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "接栓"
        ),
        Dictionary(
            yomi = "ぜるびあ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ゼルビア"
        ),
        Dictionary(
            yomi = "せれっそ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "セレッソ"
        ),
        Dictionary(
            yomi = "せれっそおおさか",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "セレッソ大阪"
        ),
        Dictionary(
            yomi = "ぜんきかてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "前期課程"
        ),
        Dictionary(
            yomi = "ぜんざいさん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "全財産"
        ),
        Dictionary(
            yomi = "そうけつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "倉頡"
        ),
        Dictionary(
            yomi = "そうけつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "蒼頡"
        ),
        Dictionary(
            yomi = "ぞうじるし",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "象印"
        ),
        Dictionary(
            yomi = "そうだりん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "操舵輪"
        ),
        Dictionary(
            yomi = "そきゃく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "阻却"
        ),
        Dictionary(
            yomi = "そっかん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "速乾"
        ),
        Dictionary(
            yomi = "そふとばんくほーくす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ソフトバンクホークス"
        ),
        Dictionary(
            yomi = "たいがーす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "タイガース"
        ),
        Dictionary(
            yomi = "たいがいじょうほうちょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "対外情報庁"
        ),
        Dictionary(
            yomi = "たいしょうあんごう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "対称暗号"
        ),
        Dictionary(
            yomi = "たいしょうがい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "対象外"
        ),
        Dictionary(
            yomi = "たいしょうかぎ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "対称鍵"
        ),
        Dictionary(
            yomi = "たいしょうかぎあんごう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "対称鍵暗号"
        ),
        Dictionary(
            yomi = "たいしょうない",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "対象内"
        ),
        Dictionary(
            yomi = "たいしんりっぽうこうし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "体心立方格子"
        ),
        Dictionary(
            yomi = "たいせつ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "堆雪"
        ),
        Dictionary(
            yomi = "たいせっそう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "耐切創"
        ),
        Dictionary(
            yomi = "だいにほんていこく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "大日本帝国"
        ),
        Dictionary(
            yomi = "たいほうきんば",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "台澎金馬"
        ),
        Dictionary(
            yomi = "だいようつい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "代用対"
        ),
        Dictionary(
            yomi = "たいりょうしあんごう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "耐量子暗号"
        ),
        Dictionary(
            yomi = "だうなー",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "ダウナー"
        ),
        Dictionary(
            yomi = "だきまくら",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "抱き枕"
        ),
        Dictionary(
            yomi = "たしせたい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "多子世帯"
        ),
        Dictionary(
            yomi = "たちあらい",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "太刀洗"
        ),
        Dictionary(
            yomi = "たちわざ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "立ち技"
        ),
        Dictionary(
            yomi = "たもあみ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "タモ網"
        ),
        Dictionary(
            yomi = "たようそにんしょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "多要素認証"
        ),
        Dictionary(
            yomi = "だりん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "舵輪"
        ),
        Dictionary(
            yomi = "たんしゃしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "単斜晶"
        ),
        Dictionary(
            yomi = "たんめん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "端面"
        ),
        Dictionary(
            yomi = "たんよく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "貪欲"
        ),
        Dictionary(
            yomi = "たんろくでんち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "単6電池"
        ),
        Dictionary(
            yomi = "たんろくでんち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "単六電池"
        ),
        Dictionary(
            yomi = "ちかてつどう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "地下鉄道"
        ),
        Dictionary(
            yomi = "ちかてつどうぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "地下鉄道業"
        ),
        Dictionary(
            yomi = "ちくさんるいじぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "畜産類似業"
        ),
        Dictionary(
            yomi = "ちずきゅうこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "智頭急行"
        ),
        Dictionary(
            yomi = "ちずきゅうこうせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "智頭急行線"
        ),
        Dictionary(
            yomi = "ちばろって",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "千葉ロッテ"
        ),
        Dictionary(
            yomi = "ちばろってまりーんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "千葉ロッテマリーンズ"
        ),
        Dictionary(
            yomi = "ちほうぎょうせいきかん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "地方行政機関"
        ),
        Dictionary(
            yomi = "ちゃーん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "チャーン"
        ),
        Dictionary(
            yomi = "ちゃくが",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "着画"
        ),
        Dictionary(
            yomi = "ちゃくさ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "着差"
        ),
        Dictionary(
            yomi = "ちゃくどん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "着丼"
        ),
        Dictionary(
            yomi = "ちゅうおん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "注音"
        ),
        Dictionary(
            yomi = "ちゅうおんじぼ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "注音字母"
        ),
        Dictionary(
            yomi = "ちゅうきん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "中近"
        ),
        Dictionary(
            yomi = "ちゅうきんりょうよう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "中近両用"
        ),
        Dictionary(
            yomi = "ちゅうごくけんせつぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "中国建設銀行"
        ),
        Dictionary(
            yomi = "ちゅうごくこうていいん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "中国工程院"
        ),
        Dictionary(
            yomi = "ちゅうさつ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "駐紮"
        ),
        Dictionary(
            yomi = "ちゅうにちどらごんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "中日ドラゴンズ"
        ),
        Dictionary(
            yomi = "ちょうほうとくむちょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "諜報特務庁"
        ),
        Dictionary(
            yomi = "ちょくほうしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "直方晶"
        ),
        Dictionary(
            yomi = "ちょちく",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "儲蓄"
        ),
        Dictionary(
            yomi = "つうちよきん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "通知預金"
        ),
        Dictionary(
            yomi = "つじた",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "つじ田"
        ),
        Dictionary(
            yomi = "つなぎめ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "繋ぎ目"
        ),
        Dictionary(
            yomi = "ていきよきん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "定期預金"
        ),
        Dictionary(
            yomi = "ていしゅ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "丁種"
        ),
        Dictionary(
            yomi = "ていせいぶん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "訂正分"
        ),
        Dictionary(
            yomi = "ていせいぶん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "訂正文"
        ),
        Dictionary(
            yomi = "てづかおさむ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "手塚治虫"
        ),
        Dictionary(
            yomi = "ではば",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "出幅"
        ),
        Dictionary(
            yomi = "でびあん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "デビアン"
        ),
        Dictionary(
            yomi = "でんてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "電停"
        ),
        Dictionary(
            yomi = "てんな",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "天和"
        ),
        Dictionary(
            yomi = "てんむす",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "天むす"
        ),
        Dictionary(
            yomi = "てんわ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "天和"
        ),
        Dictionary(
            yomi = "とうきょうゔぇるでぃ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "東京ヴェルディ"
        ),
        Dictionary(
            yomi = "とうきょうすたーぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "東京スター銀行"
        ),
        Dictionary(
            yomi = "とうきょうやくるとすわろーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "東京ヤクルトスワローズ"
        ),
        Dictionary(
            yomi = "とうごうかんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "統合漢字"
        ),
        Dictionary(
            yomi = "とうじょ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "倒叙"
        ),
        Dictionary(
            yomi = "とうほくらくてんごーるでんいーぐるす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "東北楽天ゴールデンイーグルス"
        ),
        Dictionary(
            yomi = "とうよ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "党与"
        ),
        Dictionary(
            yomi = "とえいあさくさせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "都営浅草線"
        ),
        Dictionary(
            yomi = "とえいしんじゅくせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "都営新宿線"
        ),
        Dictionary(
            yomi = "とえいみたせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "都営三田線"
        ),
        Dictionary(
            yomi = "とかさくせん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "渡河作戦"
        ),
        Dictionary(
            yomi = "とがしよしひろ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "冨樫義博"
        ),
        Dictionary(
            yomi = "とくせいそば",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "特製そば"
        ),
        Dictionary(
            yomi = "どじっこ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "ドジっ子"
        ),
        Dictionary(
            yomi = "とっくつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "突厥"
        ),
        Dictionary(
            yomi = "とっけつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "突厥"
        ),
        Dictionary(
            yomi = "とでんあらかわせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "都電荒川線"
        ),
        Dictionary(
            yomi = "とびこうじぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "とび工事業"
        ),
        Dictionary(
            yomi = "どらごんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ドラゴンズ"
        ),
        Dictionary(
            yomi = "とりやまあきら",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "鳥山明"
        ),
        Dictionary(
            yomi = "なかう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "なか卯"
        ),
        Dictionary(
            yomi = "なごやぐらんぱす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "名古屋グランパス"
        ),
        Dictionary(
            yomi = "ななまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "七万"
        ),
        Dictionary(
            yomi = "なまやさい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "生野菜"
        ),
        Dictionary(
            yomi = "なるひと",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "徳仁"
        ),
        Dictionary(
            yomi = "にがめ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "苦め"
        ),
        Dictionary(
            yomi = "にかんじ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "二簡字"
        ),
        Dictionary(
            yomi = "にくどん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "肉丼"
        ),
        Dictionary(
            yomi = "にくようぎゅうせいさんぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "肉用牛生産業"
        ),
        Dictionary(
            yomi = "にたまご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "煮卵"
        ),
        Dictionary(
            yomi = "にだんかいうせつ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "二段階右折"
        ),
        Dictionary(
            yomi = "にだんかいにんしょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "二段階認証"
        ),
        Dictionary(
            yomi = "にっぽりとねりせん",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "日暮里・舎人線"
        ),
        Dictionary(
            yomi = "にっぽりとねりらいなー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "日暮里・舎人ライナー"
        ),
        Dictionary(
            yomi = "にっぽんじゅう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "日本中"
        ),
        Dictionary(
            yomi = "にっぽんはむふぁいたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "日本ハムファイターズ"
        ),
        Dictionary(
            yomi = "にほんじゅう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "日本中"
        ),
        Dictionary(
            yomi = "にまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "二万"
        ),
        Dictionary(
            yomi = "にゅうちょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "入庁"
        ),
        Dictionary(
            yomi = "にようそにんしょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "二要素認証"
        ),
        Dictionary(
            yomi = "のうがっこう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "農学校"
        ),
        Dictionary(
            yomi = "のみくち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "飲み口"
        ),
        Dictionary(
            yomi = "のりよし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "義良"
        ),
        Dictionary(
            yomi = "ばいあぐら",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "バイアグラ"
        ),
        Dictionary(
            yomi = "はいたしょり",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "排他処理"
        ),
        Dictionary(
            yomi = "ぱいたん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "白湯"
        ),
        Dictionary(
            yomi = "ばうんしゃ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "馬運車"
        ),
        Dictionary(
            yomi = "はきいん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "破毀院"
        ),
        Dictionary(
            yomi = "はくしかてい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "博士課程"
        ),
        Dictionary(
            yomi = "ばくそく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "爆速"
        ),
        Dictionary(
            yomi = "はくたく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "白沢"
        ),
        Dictionary(
            yomi = "はたしじょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "果たし状"
        ),
        Dictionary(
            yomi = "はちまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "八万"
        ),
        Dictionary(
            yomi = "はっしゃいち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "発射位置"
        ),
        Dictionary(
            yomi = "ばばあ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "婆"
        ),
        Dictionary(
            yomi = "ばふぁろーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "バファローズ"
        ),
        Dictionary(
            yomi = "はやしだ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "はやし田"
        ),
        Dictionary(
            yomi = "はらわた",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "腑"
        ),
        Dictionary(
            yomi = "はんき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "搬器"
        ),
        Dictionary(
            yomi = "ばんごはん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "晩ごはん"
        ),
        Dictionary(
            yomi = "はんじ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "版次"
        ),
        Dictionary(
            yomi = "はんしゃかいてきせいりょく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "反社会的勢力"
        ),
        Dictionary(
            yomi = "はんしんたいがーす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "阪神タイガース"
        ),
        Dictionary(
            yomi = "はんぷ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "坂阜"
        ),
        Dictionary(
            yomi = "ぴーふぁす",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "PFAS"
        ),
        Dictionary(
            yomi = "ひーるど",
            leftId = `名詞,固有名詞,人名,姓,*,*,*`,
            rightId = `名詞,固有名詞,人名,姓,*,*,*`,
            cost = 4000,
            tango = "ヒールド"
        ),
        Dictionary(
            yomi = "ひえろぐりふ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ヒエログリフ"
        ),
        Dictionary(
            yomi = "ひきなみ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "引き波"
        ),
        Dictionary(
            yomi = "ひとぐり",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "人繰り"
        ),
        Dictionary(
            yomi = "ひともうけ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "一儲け"
        ),
        Dictionary(
            yomi = "びほう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "弥縫"
        ),
        Dictionary(
            yomi = "びほうさく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "弥縫策"
        ),
        Dictionary(
            yomi = "ひゃっきん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "百均"
        ),
        Dictionary(
            yomi = "ひらしゃいん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "平社員"
        ),
        Dictionary(
            yomi = "ひらぶん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "平文"
        ),
        Dictionary(
            yomi = "ひろしまかーぷ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "広島カープ"
        ),
        Dictionary(
            yomi = "ひろしまとうようかーぷ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "広島東洋カープ"
        ),
        Dictionary(
            yomi = "ぴんいん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "拼音"
        ),
        Dictionary(
            yomi = "ぴんきー",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "ピンキー"
        ),
        Dictionary(
            yomi = "びんご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "閩語"
        ),
        Dictionary(
            yomi = "ふぁいたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ファイターズ"
        ),
        Dictionary(
            yomi = "ふぁいるぴっかー",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "ファイルピッカー"
        ),
        Dictionary(
            yomi = "ふいふい",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "回回"
        ),
        Dictionary(
            yomi = "ふきだしぐち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "吹き出し口"
        ),
        Dictionary(
            yomi = "ふくおかそふとばんくほーくす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "福岡ソフトバンクホークス"
        ),
        Dictionary(
            yomi = "ふしんぱんせいきゅう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "付審判請求"
        ),
        Dictionary(
            yomi = "ふしんぱんてつづき",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "付審判手続"
        ),
        Dictionary(
            yomi = "ふたつ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "不達"
        ),
        Dictionary(
            yomi = "ふつーら",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "フツーラ"
        ),
        Dictionary(
            yomi = "ふとぅーら",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "フトゥーラ"
        ),
        Dictionary(
            yomi = "ふもうご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "不妄語"
        ),
        Dictionary(
            yomi = "ぷらちなでびっと",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "プラチナデビット"
        ),
        Dictionary(
            yomi = "ぶらばん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "ブラバン"
        ),
        Dictionary(
            yomi = "ぷりいんすとーる",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "プリインストール"
        ),
        Dictionary(
            yomi = "ふりたんい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "付利単位"
        ),
        Dictionary(
            yomi = "ふりにげ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "振り逃げ"
        ),
        Dictionary(
            yomi = "ぷろくし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "プロクシ"
        ),
        Dictionary(
            yomi = "ふろんたーれ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "フロンターレ"
        ),
        Dictionary(
            yomi = "ぶんぽう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "文保"
        ),
        Dictionary(
            yomi = "へいしゅ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "丙種"
        ),
        Dictionary(
            yomi = "べいすたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ベイスターズ"
        ),
        Dictionary(
            yomi = "べるまーれ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ベルマーレ"
        ),
        Dictionary(
            yomi = "へんかんそしょう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "返還訴訟"
        ),
        Dictionary(
            yomi = "へんむてき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "片務的"
        ),
        Dictionary(
            yomi = "ぼうたいか",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "暴対課"
        ),
        Dictionary(
            yomi = "ほーくす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ホークス"
        ),
        Dictionary(
            yomi = "ほしいも",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "干し芋"
        ),
        Dictionary(
            yomi = "ほしゅうごう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "補集合"
        ),
        Dictionary(
            yomi = "ほじょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "圃場"
        ),
        Dictionary(
            yomi = "ほせんご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "莆仙語"
        ),
        Dictionary(
            yomi = "ほっかいどうこんさどーれさっぽろ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "北海道コンサドーレ札幌"
        ),
        Dictionary(
            yomi = "ほっかいどうにっぽんはむふぁいたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "北海道日本ハムファイターズ"
        ),
        Dictionary(
            yomi = "ほっけ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "𩸽"
        ),
        Dictionary(
            yomi = "ほったて",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "掘立"
        ),
        Dictionary(
            yomi = "ぽるてぃちのおしむすめ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ポルティチの唖娘"
        ),
        Dictionary(
            yomi = "ほんじ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "翻字"
        ),
        Dictionary(
            yomi = "まいとしこうれい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "毎年恒例"
        ),
        Dictionary(
            yomi = "まいぶーむ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "マイブーム"
        ),
        Dictionary(
            yomi = "まじれす",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "マジレス"
        ),
        Dictionary(
            yomi = "まちだぜるびあ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "町田ゼルビア"
        ),
        Dictionary(
            yomi = "まつもとふかし",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "松本深志"
        ),
        Dictionary(
            yomi = "まつもとみすずがおかこうこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "松本美須々ヶ丘高校"
        ),
        Dictionary(
            yomi = "まつりか",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "茉莉花"
        ),
        Dictionary(
            yomi = "まりーんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "マリーンズ"
        ),
        Dictionary(
            yomi = "まりのす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "マリノス"
        ),
        Dictionary(
            yomi = "まんがたいむ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "まんがタイム"
        ),
        Dictionary(
            yomi = "みずきしげる",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "水木しげる"
        ),
        Dictionary(
            yomi = "みなみまんしゅうてつどう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "南満洲鉄道"
        ),
        Dictionary(
            yomi = "みぬめじんじゃ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "敏馬神社"
        ),
        Dictionary(
            yomi = "みやこそば",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "宮古そば"
        ),
        Dictionary(
            yomi = "みるめじんじゃ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "敏馬神社"
        ),
        Dictionary(
            yomi = "むえき",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "無益"
        ),
        Dictionary(
            yomi = "むしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "無床"
        ),
        Dictionary(
            yomi = "むしょうしんりょうじょ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "無床診療所"
        ),
        Dictionary(
            yomi = "むびゅう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "無謬"
        ),
        Dictionary(
            yomi = "むびゅうせい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "無謬性"
        ),
        Dictionary(
            yomi = "むやく",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "無役"
        ),
        Dictionary(
            yomi = "めろぶ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "メロブ"
        ),
        Dictionary(
            yomi = "めんしんりっぽうこうし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "面心立方格子"
        ),
        Dictionary(
            yomi = "もくさじんじゃ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "儛草神社"
        ),
        Dictionary(
            yomi = "もくさとう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "舞草刀"
        ),
        Dictionary(
            yomi = "もどりち",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "戻り値"
        ),
        Dictionary(
            yomi = "もよりいち",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "もより市"
        ),
        Dictionary(
            yomi = "やくご",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "訳語"
        ),
        Dictionary(
            yomi = "やくたたず",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "役立たず"
        ),
        Dictionary(
            yomi = "やくるとすわろーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ヤクルトスワローズ"
        ),
        Dictionary(
            yomi = "ゆうげんじっこう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "有言実行"
        ),
        Dictionary(
            yomi = "ゆうしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "有床"
        ),
        Dictionary(
            yomi = "ゆうしょうしんりょうじょ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "有床診療所"
        ),
        Dictionary(
            yomi = "ゆうちょぎんこう",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ゆうちょ銀行"
        ),
        Dictionary(
            yomi = "ゆうりょうごにん",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "優良誤認"
        ),
        Dictionary(
            yomi = "ようかいおんど",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "溶解温度"
        ),
        Dictionary(
            yomi = "ようさんのうぎょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "養蚕農業"
        ),
        Dictionary(
            yomi = "よこはまDeNAべいすたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "横浜DeNAベイスターズ"
        ),
        Dictionary(
            yomi = "よこはまF・まりのす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "横浜F・マリノス"
        ),
        Dictionary(
            yomi = "よこはまえふ・まりのす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "横浜F・マリノス"
        ),
        Dictionary(
            yomi = "よこはまでぃーえぬえーべいすたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "横浜DeNAベイスターズ"
        ),
        Dictionary(
            yomi = "よこはまべいすたーず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "横浜ベイスターズ"
        ),
        Dictionary(
            yomi = "よこはままりのす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "横浜マリノス"
        ),
        Dictionary(
            yomi = "よみうりじゃいあんつ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "読売ジャイアンツ"
        ),
        Dictionary(
            yomi = "よるごはん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "夜ごはん"
        ),
        Dictionary(
            yomi = "よんまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "四万"
        ),
        Dictionary(
            yomi = "らいおんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ライオンズ"
        ),
        Dictionary(
            yomi = "らくてんいーぐるす",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "楽天イーグルス"
        ),
        Dictionary(
            yomi = "らのべ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "ラノベ"
        ),
        Dictionary(
            yomi = "りっぽうしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "立方晶"
        ),
        Dictionary(
            yomi = "りねーむ",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "リネーム"
        ),
        Dictionary(
            yomi = "りまいんど",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "リマインド"
        ),
        Dictionary(
            yomi = "りゅうこうごたいしょう",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "流行語大賞"
        ),
        Dictionary(
            yomi = "れいきし",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "励起子"
        ),
        Dictionary(
            yomi = "れいそる",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "レイソル"
        ),
        Dictionary(
            yomi = "れいたくだいがく",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "麗澤大学"
        ),
        Dictionary(
            yomi = "れいわ",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "令和"
        ),
        Dictionary(
            yomi = "れっず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "レッズ"
        ),
        Dictionary(
            yomi = "れんさいもの",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "連載もの"
        ),
        Dictionary(
            yomi = "ろうくみ",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "労組"
        ),
        Dictionary(
            yomi = "ろくじゅうそう",
            leftId = `名詞,サ変接続,*,*,*,*,*`,
            rightId = `名詞,サ変接続,*,*,*,*,*`,
            cost = 4000,
            tango = "六重奏"
        ),
        Dictionary(
            yomi = "ろくまん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "六万"
        ),
        Dictionary(
            yomi = "ろってまりーんず",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "ロッテマリーンズ"
        ),
        Dictionary(
            yomi = "わいろざい",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "賄賂罪"
        ),
        Dictionary(
            yomi = "わせだあかでみー",
            leftId = `名詞,固有名詞,一般,*,*,*,*`,
            rightId = `名詞,固有名詞,一般,*,*,*,*`,
            cost = 4000,
            tango = "早稲田アカデミー"
        ),
        Dictionary(
            yomi = "わぜん",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "和膳"
        ),
        Dictionary(
            yomi = "わびさび",
            leftId = `名詞,固有名詞,人名,名,*,*,*`,
            rightId = `名詞,固有名詞,人名,名,*,*,*`,
            cost = 4000,
            tango = "侘び寂び"
        )
    )

}
