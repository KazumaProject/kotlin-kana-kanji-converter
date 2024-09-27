package com.kazumaproject.emoticon

import com.kazumaproject.dictionary.models.Dictionary
import java.io.File

class EmoticonDictionaryBuilder {
    fun convertEmoticonDataToDictionaryList(filePath: String): List<Dictionary> {
        val emoticonList = mutableListOf<Dictionary>()

        // Define default values
        val defaultLeftId = (2641).toShort()
        val defaultRightId = (2641).toShort()
        val defaultCost = (4000).toShort()

        // Read the file line by line
        File(filePath).useLines { lines ->
            lines.forEach { line ->
                val columns = line.split("\t") // Assuming it's tab-separated

                // The first column is the emoticon (tango), the others are readings (yomi)
                if (columns.isNotEmpty()) {
                    val tango = columns[0] // First column as tango (emoticon)

                    // Process each yomi (reading) in the row, split by spaces, and create Dictionary entries
                    for (yomiEntry in columns.drop(1)) {
                        val yomiList = yomiEntry.trim().split(" ") // Split yomi by space

                        // Create a Dictionary entry for each separated yomi
                        for (yomi in yomiList) {
                            if (yomi.isNotEmpty()) { // Ensure non-empty yomi
                                emoticonList.add(
                                    Dictionary(
                                        yomi = yomi.trim(),  // Each part of the yomi
                                        leftId = defaultLeftId,
                                        rightId = defaultRightId,
                                        cost = defaultCost,
                                        tango = tango.trim()  // Use the first column as emoticon
                                    )
                                )
                            }
                        }
                    }
                }
            }
        }

        return emoticonList
    }
}