package com.kazumaproject.quality

import kotlinx.serialization.json.*
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

object CategoryPackage {
    fun write(directory: File, output: File, notices: File) {
        require(notices.isFile) { "Missing dictionary notices" }
        val manifest = Json.parseToJsonElement(File(directory, "manifest.json").readText()).jsonObject
        val artifacts = manifest.getValue("artifacts").jsonObject
        artifacts.forEach { (name, hash) -> require(sha256(File(directory, name)) == hash.jsonPrimitive.content) { "Checksum mismatch: $name" } }
        output.absoluteFile.parentFile.mkdirs()
        val temporary = File(output.parentFile, ".${output.name}.tmp")
        try {
            ZipOutputStream(temporary.outputStream().buffered()).use { zip ->
                (artifacts.keys + "manifest.json" + "NOTICES.md").sorted().forEach { name ->
                    require(!name.startsWith('/') && name.split('/').none { it == ".." }) { "Unsafe artifact path" }
                    zip.putNextEntry(ZipEntry(name).apply { time = 0 })
                    (if (name == "NOTICES.md") notices else File(directory, name)).inputStream().use { it.copyTo(zip) }
                    zip.closeEntry()
                }
            }
            verify(temporary)
            java.nio.file.Files.move(temporary.toPath(), output.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING)
        } finally { temporary.delete() }
    }
    fun verify(file: File) = ZipFile(file).use { zip ->
        val names = zip.entries().asSequence().map { it.name }.toList()
        require(names.size == names.toSet().size) { "Duplicate ZIP entries" }
        val manifest = Json.parseToJsonElement(zip.getInputStream(zip.getEntry("manifest.json") ?: error("Missing manifest")).bufferedReader().use { it.readText() }).jsonObject
        require(manifest.getValue("format").jsonPrimitive.content == "legacy-louds-triplets-v1") { "Invalid dictionary format" }
        val artifacts = manifest.getValue("artifacts").jsonObject
        val expected = setOf("pos_table.dat") + publishedCategories.flatMap { c -> listOf("yomi.dat", "tango.dat", "token.dat").map { "$c/$it" } }
        require(artifacts.keys == expected && names.toSet() == expected + setOf("manifest.json", "NOTICES.md")) { "Unexpected category package entries" }
        require(zip.getEntry("NOTICES.md").size > 0) { "Empty notices" }
        artifacts.forEach { (name, hash) ->
            val digest = MessageDigest.getInstance("SHA-256")
            zip.getInputStream(zip.getEntry(name) ?: error("Missing $name")).use { input ->
                val buffer = ByteArray(65536); while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer,0,n) }
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == hash.jsonPrimitive.content) { "ZIP checksum mismatch: $name" }
        }
    }
}
