package com.kazumaproject.symbol

import com.kazumaproject.dictionary.models.Dictionary
import java.io.File

class SymbolDictionaryBuilder {

    fun convertSymbolDataToDictionaryList(filePath: String): List<Dictionary> {
        val symbolList = mutableListOf<Dictionary>()

        // Define default values
        val defaultLeftId = (2641).toShort()
        val defaultRightId = (2641).toShort()
        val defaultCost = (4000).toShort()

        // Read the file line by line
        File(filePath).useLines { lines ->
            lines.forEach { line ->
                val columns = line.split("\t") // Assuming it's tab-separated

                // The first column is the symbol (tango), the second is readings (yomi)
                if (columns.size == 2) {
                    val tango = columns[0].trim() // First column as tango (symbol)
                    val yomiEntries = columns[1].trim().split(" ") // Second column, split readings by space

                    // Create a Dictionary entry for each separated yomi
                    for (yomi in yomiEntries) {
                        if (yomi.isNotEmpty()) { // Ensure non-empty yomi
                            symbolList.add(
                                Dictionary(
                                    yomi = yomi.trim(),  // Each part of the yomi
                                    leftId = defaultLeftId,
                                    rightId = defaultRightId,
                                    cost = defaultCost,
                                    tango = tango  // Use the first column as symbol
                                )
                            )
                        }
                    }
                }
            }
        }

        return symbolList
    }

}