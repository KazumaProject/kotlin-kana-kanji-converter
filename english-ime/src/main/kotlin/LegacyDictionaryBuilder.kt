import converters.Converter
import converters.ConverterWithTermId
import dictionary.BuildDictionary
import dictionary.Dictionary
import glide.QwertyGlideIndexGenerator
import louds.LOUDS
import louds.louds_with_term_id.LOUDSWithTermId
import prefix.PrefixTree
import prefix.prefix_with_term_id.PrefixTreeWithTermId
import tokenArray.TokenArray
import java.io.File
import java.io.ObjectInputStream
import java.io.ObjectOutputStream

fun buildLegacyDictionary(source: File, output: File) {
    require(output.isDirectory || output.mkdirs()) { "Cannot create output directory: $output" }
    val dictList: List<Dictionary> = (BuildDictionary.loadDictionaryFromZip(source) +
            MANUAL_WORD +
            TERMINAL_COMMAND +
            PYTHON_COMMAND +
            WEB_COMMAND +
            WEB_COMMAND_EXTRA +
            PYTHON_COMMAND_EXTRA +
            DEVOPS_COMMAND +
            UTIL_COMMAND
            )
        .sortedWith(
            compareBy<Dictionary> { it.reading.length }
                .thenBy { it.cost }
        )
    println("読み込んだエントリ数: ${dictList.size}")
    buildDictionaries(dictList, output)
    val qwertyGlideEntryCount = QwertyGlideIndexGenerator.generate(
        dictList = dictList,
        outputFile = output.resolve("qwerty_glide_index.dat")
    )
    println("qwerty_glide_index.dat entries: $qwertyGlideEntryCount")
}

private fun buildDictionaries(dictList: List<Dictionary>, output: File) {
    val readingTree = PrefixTreeWithTermId()
    val wordTree = PrefixTree()

    for (entry in dictList) {
        readingTree.insert(entry.reading)
        if (entry.withUpperCase) {
            wordTree.insert(entry.word)
        }
    }

    val readingLOUDSTemp = ConverterWithTermId().convert(readingTree.root)
    val wordLOUDSTemp = Converter().convert(wordTree.root)
    readingLOUDSTemp.convertListToBitSet()
    wordLOUDSTemp.convertListToBitSet()
    ObjectOutputStream(output.resolve("reading.dat").outputStream().buffered()).use {
        readingLOUDSTemp.writeExternalNotCompress(it)
    }
    val wordFile = output.resolve("word.dat")
    ObjectOutputStream(wordFile.outputStream().buffered()).use {
        wordLOUDSTemp.writeExternalNotCompress(it)
    }
    val wordLOUDS = ObjectInputStream(wordFile.inputStream().buffered()).use {
        LOUDS().readExternalNotCompress(it)
    }
    ObjectOutputStream(output.resolve("token.dat").outputStream().buffered()).use {
        TokenArray().buildTokenArray(dictList, wordLOUDS, it)
    }
}
