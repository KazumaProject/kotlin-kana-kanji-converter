package com.kazumaproject.single_kanji

import com.kazumaproject.Constants.DIC_LIST
import com.kazumaproject.dictionary.models.Dictionary

class SingleKanjiBuilder {

    fun build(fileName: String): List<Dictionary> {
        val singleKanjiInMap = getSingleKanjiList(fileName)
        val tempList = mutableListOf<Dictionary>()
        for (entry in singleKanjiInMap){
            for (singleKanji in entry.value){
                if (entry.key.length == 1){
                    println("key1: $singleKanji")
                    tempList.add(
                        Dictionary(
                            yomi = entry.key,
                            leftId = 1916,
                            rightId = 1916,
                            cost = 4000,
                            tango = singleKanji.toString()
                        )
                    )
                }else{
                    println("key else: $singleKanji")
                    tempList.add(
                        Dictionary(
                            yomi = entry.key,
                            leftId = 1916,
                            rightId = 1916,
                            cost = 1000,
                            tango = singleKanji.toString()
                        )
                    )
                }
            }
        }
        tempList.addAll(DIC_LIST)
        return tempList.toList()
    }

    fun getSingleKanjiInMap(fileName: String): Map<String, List<Char>>{
        return getSingleKanjiList(fileName)
    }

    private fun getSingleKanjiList(fileName: String): Map<String, List<Char>> {
        val lines = this::class.java.getResourceAsStream(fileName)
            ?.bufferedReader()
            ?.readLines()

        lines?.let {  l ->
            val tempList = l.map { str1 ->
                str1.split(",".toRegex()).flatMap { str2 ->
                    str2.split("\\t".toRegex())
                }
            }
            return tempList.associate {
                it[0] to it[1].toList()
            }
        }

        return emptyMap()
    }

}