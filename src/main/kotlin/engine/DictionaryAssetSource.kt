package com.kazumaproject.engine

import com.kazumaproject.Louds.LOUDS
import com.kazumaproject.Louds.with_term_id.LOUDSWithTermId
import com.kazumaproject.dictionary.TokenArray
import com.kazumaproject.hiraToKata
import java.io.*
import java.util.BitSet
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

/** Reads generated resources or the shipped ZIP without mixing their common POS tables. */
internal class DictionaryAssetSource(
    private val directory: File = File("src/main/resources"),
    archive: File? = null,
) : Closeable {
    private val zip = archive?.let(::ZipFile)

    fun open(generated: String, packaged: String = generated): InputStream {
        if (zip == null) return File(directory, generated).inputStream().buffered()
        val path = "app/src/main/assets/$packaged"
        val stream = zip.getInputStream(zip.getEntry(path) ?: error("Missing dictionary asset: $path"))
        if (!packaged.endsWith(".zip")) return stream.buffered()
        val nested = ZipInputStream(stream)
        require(nested.nextEntry?.name == File(packaged.removeSuffix(".zip")).name) {
            nested.close()
            "Invalid nested dictionary ZIP: $path"
        }
        return nested.buffered()
    }

    fun optionalBytes(path: String): ByteArray? {
        if (zip == null && !File(directory, path).isFile) return null
        if (zip != null && zip.getEntry("app/src/main/assets/$path") == null) return null
        return open(path).use { it.readBytes() }
    }

    fun dictionary(category: String? = null): LoadedDictionary {
        val generated = if (category == null) "" else "dictionary_categories/$category/"
        val packaged = if (category == null) "system/" else "categories/$category/"
        fun objects(name: String) = ObjectInputStream(open("$generated$name.dat", "$packaged$name.dat.zip"))
        val yomi = objects("yomi").use {
            val lbs = it.readObject() as BitSet
            val leaves = it.readObject() as BitSet
            val labels = (it.readObject() as CharArray).toMutableList()
            LOUDSWithTermId(lbs, labels, leaves, it.readObject() as IntArray)
        }
        val tango = objects("tango").use {
            val lbs = it.readObject() as BitSet
            val leaves = it.readObject() as BitSet
            LOUDS(lbs, (it.readObject() as CharArray).toMutableList(), leaves)
        }
        val tokens = objects("token").use { input -> TokenArray().also { it.readExternalNotCompressStrict(input) } }
        return LoadedDictionary(category, yomi, tango, tokens)
    }

    override fun close() { zip?.close() }
}

internal data class LoadedDictionary(
    val category: String?,
    val yomi: LOUDSWithTermId,
    val tango: LOUDS,
    val tokens: TokenArray,
) {
    fun surface(node: Int, reading: String): String = when (node) {
        -2 -> reading
        -1 -> reading.hiraToKata()
        else -> tango.getLetter(node)
    }
}
