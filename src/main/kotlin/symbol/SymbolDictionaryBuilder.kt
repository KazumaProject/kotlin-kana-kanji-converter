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
                // Trim the line and skip if empty
                val trimmedLine = line.trim()
                if (trimmedLine.isEmpty()) {
                    return@forEach // Continue to next line
                }

                // Split the line by the first occurrence of one or more whitespace characters.
                // The limit '2' ensures we only get two parts: the symbol and the rest of the string.
                val columns = trimmedLine.split(Regex("\\s+"), 2)

                // The first column is the symbol (tango), the second is readings (yomi)
                if (columns.size == 2) {
                    val tango = columns[0] // The symbol is the first part
                    val yomiEntries = columns[1].trim().split(" ") // The second part contains all readings

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
