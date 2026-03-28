package com.kazumaproject

import com.kazumaproject.Louds.Converter
import com.kazumaproject.Louds.with_term_id.ConverterWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.prefix.PrefixTree
import com.kazumaproject.prefix.with_term_id.PrefixTreeWithTermId
import java.io.BufferedOutputStream
import java.io.FileOutputStream
import java.io.ObjectOutputStream
import java.util.SortedMap

internal fun buildAndWriteDictionaryArtifacts(
    dictionaryList: SortedMap<String, List<Dictionary>>,
    yomiOutputPath: String,
    tangoOutputPath: String,
    tokenOutputPath: String,
    mode: Int = 1,
    skipKanaOnlyTango: Boolean = false,
    posTableForBuildPath: String? = null,
) {
    val yomiTree = PrefixTreeWithTermId()
    val tangoTree = PrefixTree()

    dictionaryList.forEach { (yomi, dictionaries) ->
        yomiTree.insert(yomi)
        dictionaries.forEach { dictionary ->
            if (!skipKanaOnlyTango || !dictionary.tango.isHiraganaOrKatakana()) {
                tangoTree.insert(dictionary.tango)
            }
        }
    }

    val yomiLOUDS = ConverterWithTermId().convert(yomiTree.root).apply {
        convertListToBitSet()
    }
    val tangoLOUDS = Converter().convert(tangoTree.root).apply {
        convertListToBitSet()
    }

    ObjectOutputStream(BufferedOutputStream(FileOutputStream(yomiOutputPath))).use { out ->
        yomiLOUDS.writeExternalNotCompress(out)
    }
    ObjectOutputStream(BufferedOutputStream(FileOutputStream(tangoOutputPath))).use { out ->
        tangoLOUDS.writeExternalNotCompress(out)
    }
    ObjectOutputStream(BufferedOutputStream(FileOutputStream(tokenOutputPath))).use { out ->
        TokenArray().buildTokenArray(dictionaryList, tangoLOUDS, out, mode, posTableForBuildPath)
    }
}
