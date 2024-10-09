package com.kazumaproject.reading_correction

import com.kazumaproject.dictionary.models.Dictionary
import java.io.File

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
}