package com.kazumaproject.reading_correction

import com.kazumaproject.dictionary.models.Dictionary
import java.io.File
import java.io.InputStream

class ReadingCorrectionBuilder {
    fun parseKotowazaTSV(filePath: String): List<Dictionary> {
        val leftId = (1851).toShort()
        val rightId = (1851).toShort()
        val cost = (3000).toShort()

        return File(filePath).useLines { lines ->
            lines.map { line ->
                val parts = line.split("\t")
                if (parts.size == 2) {
                    Dictionary(
                        yomi = parts[1],
                        leftId = leftId,
                        rightId = rightId,
                        cost = cost,
                        tango = parts[0]
                    )
                } else {
                    null
                }
            }.filterNotNull().toList()
        }
    }

    fun parseReadingCorrectionTSV(filePath: String): List<Dictionary> {
        val leftId = (1851).toShort()
        val rightId = (1851).toShort()
        val cost = (4000).toShort()

        return File(filePath).useLines { lines ->
            lines.map { line ->
                val parts = line.split("\t")
                if (parts.size == 3) {
                    Dictionary(
                        yomi = parts[1],
                        leftId = leftId,
                        rightId = rightId,
                        cost = cost,
                        tango = parts[0] + "\t" + parts[2]
                    )
                } else {
                    null
                }
            }.filterNotNull().toList()
        }
    }

    fun parseMozcUTDictionary(filePath: String): List<Dictionary> {
        return File(filePath).useLines { lines ->
            lines.map { line ->
                val yomi = line.split("\\t".toRegex())[0]
                val leftId = line.split("\\t".toRegex())[1]
                val rightId = line.split("\\t".toRegex())[2]
                val cost = line.split("\\t".toRegex())[3]
                val tango = line.split("\\t".toRegex())[4]
                Dictionary(
                    yomi = yomi,
                    leftId = leftId.toShort(),
                    rightId = rightId.toShort(),
                    cost = cost.toShort(),
                    tango = tango
                )
            }.toList()
        }
    }

    fun parseMozcUTDictionaryCompressedDictionary(inputStream: InputStream): List<Dictionary> {
        return inputStream.bufferedReader().useLines { lines ->
            lines.map { line ->
                val yomi = line.split("\\t".toRegex())[0]
                val leftId = line.split("\\t".toRegex())[1]
                val rightId = line.split("\\t".toRegex())[2]
                val cost = line.split("\\t".toRegex())[3]
                val tango = line.split("\\t".toRegex())[4]
                Dictionary(
                    yomi = yomi,
                    leftId = leftId.toShort(),
                    rightId = rightId.toShort(),
                    cost = cost.toShort(),
                    tango = tango
                )
            }.toList()
        }
    }
}
