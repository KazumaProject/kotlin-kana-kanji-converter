package dictionary

import hasInternalUpperCase
import java.io.File
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.zip.ZipInputStream

object BuildDictionary {
    fun loadDictionaryFromZip(source: File): List<Dictionary> {
        val result = mutableListOf<Dictionary>()
        source.inputStream().use { zipIs ->
            ZipInputStream(zipIs).use { zipStream ->
                while (true) {
                    val entry = zipStream.nextEntry ?: break
                    if (!entry.isDirectory && entry.name.endsWith(".txt")) {
                        val reader = BufferedReader(InputStreamReader(zipStream, Charsets.UTF_8))
                        // ヘッダー行2行を読み飛ばし、それぞれを表示
                        val header1 = reader.readLine()
                        println("Skipped header: $header1")
                        val header2 = reader.readLine()
                        println("Skipped header: $header2")
                        while (true) {
                            val line = reader.readLine() ?: break
                            if (line.isBlank()) continue
                            val cols = line.split('\t')
                            if (cols.size >= 4) {
                                val reading = cols[0]
                                val word = cols[1]
                                val cost = cols[3].toIntOrNull()
                                    ?.let { if (it > Short.MAX_VALUE) Short.MAX_VALUE else it.toShort() }
                                    ?: 0
                                val withUpperCase = word.hasInternalUpperCase()
                                result += Dictionary(reading, cost, word, withUpperCase)
                            }
                        }
                    }
                    zipStream.closeEntry()
                }
            }
        }
        return result
    }
}
