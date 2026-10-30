package com.kazumaproject.english

import com.kazumaproject.classification.DictionaryFilter
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

fun main(args: Array<String>) {
    val source = loadEnglishDictionarySource(args)
    val zip = Path.of(englishOption(args, "--release-zip") ?: error("Missing required option: --release-zip"))
    val entries = DictionaryFilter.fromEnvironment().filterRecords(source.runtimeEntries, skipKanaOnlyTango = true)
    val result = EnglishDictionaryBinaryValidator.validateReleaseZip(entries, zip)
    val digest = MessageDigest.getInstance("SHA-256")
    Files.newInputStream(zip).use { input ->
        val buffer = ByteArray(65536)
        while (true) {
            val size = input.read(buffer)
            if (size < 0) break
            digest.update(buffer, 0, size)
        }
    }
    println("Verified English dictionary release binary: $result, zip=$zip, sha256=${digest.digest().joinToString("") { "%02x".format(it) }}")
}
