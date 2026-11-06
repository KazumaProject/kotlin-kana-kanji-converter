package conversion

import categoryFileHash
import grammar.CompactGrammarRoles
import grammar.RUNTIME_ROLES_FILE
import grammar.writeRuntimeGrammarRoles
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS

internal fun packReviewedRuntime(source: File, output: File) {
    val target = output.absoluteFile.toPath().normalize()
    require(Files.notExists(target, NOFOLLOW_LINKS)) { "Output already exists: $target" }
    val metadata = readReviewedMetadata(source)
    val grammar = source.resolve("grammar")
    require(grammar.resolve("categories.ecat").isFile && metadata.containsKey("categories.ecat.sha256")) {
        "Expected a full reviewed bundle with a checked ECAT index in $source"
    }
    val roles = requireNotNull(ReviewedDictionary.load(source).grammarRoles as? CompactGrammarRoles) {
        "Expected a full reviewed bundle in $source"
    }
    val notices = grammar.resolve("notices")
    val noticeFiles = requireNotNull(notices.listFiles()) { "Missing dictionary notices in $source" }
    require(noticeFiles.isNotEmpty() && noticeFiles.size.toString() == metadata.getProperty("noticeCount")) {
        "Incomplete dictionary notices in $source"
    }

    Files.createDirectories(target.parent)
    val staged = Files.createTempDirectory(target.parent, ".english-runtime-").toFile()
    try {
        for (name in listOf("reading.dat", "word.dat", "token.dat", "qwerty_glide_index.dat")) {
            val file = source.resolve(name)
            require(file.isFile) { "Missing dictionary file: $file" }
            file.copyTo(staged.resolve(name))
        }
        for (name in listOf("source-evidence-manifest.json", "supplement-manifest.json")) {
            val file = source.resolve(name)
            if (file.isFile) file.copyTo(staged.resolve(name))
        }
        val targetGrammar = staged.resolve("grammar").apply { mkdir() }
        val targetNotices = targetGrammar.resolve("notices").apply { mkdir() }
        for (file in noticeFiles) {
            require(file.isFile) { "Invalid dictionary notice: $file" }
            val copied = file.copyTo(targetNotices.resolve(file.name))
            require(categoryFileHash(copied) == metadata.getProperty("notice.${file.name}.sha256")) {
                "Dictionary notice checksum mismatch: $file"
            }
        }

        val runtime = targetGrammar.resolve(RUNTIME_ROLES_FILE)
        writeRuntimeGrammarRoles(roles, runtime.toPath())
        for (name in listOf("categories.tsv", "forms.tsv", "memberships.tsv", "categories.ecat")) {
            metadata.remove("$name.sha256")
        }
        metadata.setProperty("$RUNTIME_ROLES_FILE.sha256", categoryFileHash(runtime))
        val encoded = ByteArrayOutputStream().also { metadata.store(it, null) }
        // Keep the escaped properties but omit the timestamp added by Properties.store.
        targetGrammar.resolve("bundle.properties").writeText(
            encoded.toString(Charsets.ISO_8859_1).lineSequence().drop(1).filter { it.isNotEmpty() }.sorted()
                .joinToString("\n", postfix = "\n"),
        )
        Files.move(staged.toPath(), target)
    } finally {
        staged.deleteRecursively()
    }
}
