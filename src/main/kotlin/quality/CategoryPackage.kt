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
        val licenses = listOf("LICENSE-JMDICT.html", "LICENSE-CC-BY-SA-4.0.txt").associateWith { File(notices.absoluteFile.parentFile,it) }
        licenses.forEach { (name,file) -> require(file.isFile && file.length()>0) { "Missing dictionary license: $name" } }
        val sourceManifest = Json.parseToJsonElement(File(directory, "manifest.json").readText()).jsonObject
        val manifest = buildJsonObject { sourceManifest.forEach { (k,v)->put(k,v) };put("packageNotices",buildJsonObject { put("NOTICES.md",sha256(notices));licenses.forEach { (name,file)->put(name,sha256(file)) } }) }
        val artifacts = manifest.getValue("artifacts").jsonObject
        artifacts.forEach { (name, hash) -> require(sha256(File(directory, name)) == hash.jsonPrimitive.content) { "Checksum mismatch: $name" } }
        output.absoluteFile.parentFile.mkdirs()
        val temporary = File(output.parentFile, ".${output.name}.tmp")
        try {
            ZipOutputStream(temporary.outputStream().buffered()).use { zip ->
                (artifacts.keys + "manifest.json" + "NOTICES.md" + licenses.keys).sorted().forEach { name ->
                    require(!name.startsWith('/') && name.split('/').none { it == ".." }) { "Unsafe artifact path" }
                    zip.putNextEntry(ZipEntry(name).apply { time = 0 })
                    if(name=="manifest.json") zip.write((Json { prettyPrint=true }.encodeToString(JsonObject.serializer(),manifest)+"\n").toByteArray())
                    else (if (name == "NOTICES.md") notices else licenses[name] ?: File(directory, name)).inputStream().use { it.copyTo(zip) }
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
        require(artifacts.keys == expected && names.toSet() == expected + setOf("manifest.json", "NOTICES.md", "LICENSE-JMDICT.html", "LICENSE-CC-BY-SA-4.0.txt")) { "Unexpected category package entries" }
        require(zip.getEntry("NOTICES.md").size > 0) { "Empty notices" }
        val noticeHashes=manifest.getValue("packageNotices").jsonObject
        require(noticeHashes.keys==setOf("NOTICES.md","LICENSE-JMDICT.html","LICENSE-CC-BY-SA-4.0.txt")) { "Missing license hashes" }
        (artifacts + noticeHashes).forEach { (name, hash) ->
            val digest = MessageDigest.getInstance("SHA-256")
            zip.getInputStream(zip.getEntry(name) ?: error("Missing $name")).use { input ->
                val buffer = ByteArray(65536); while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer,0,n) }
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == hash.jsonPrimitive.content) { "ZIP checksum mismatch: $name" }
        }
    }
}
