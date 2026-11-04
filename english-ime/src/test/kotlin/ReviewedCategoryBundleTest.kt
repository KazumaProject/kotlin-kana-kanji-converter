import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.Properties
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

class ReviewedCategoryBundleTest {
    @Test fun carriesNoticesAndHashesWithoutChangingTheirText() {
        val root = Files.createTempDirectory("category-notices").toFile()
        try {
            val lexicon = root.resolve("lexicon").apply { mkdir() }
            listOf("categories.tsv", "forms.tsv", "memberships.tsv").forEach { File("data/grammar", it).copyTo(lexicon.resolve(it)) }
            val relations = root.resolve("relations.tsv").apply { writeText("fixture relations\n") }
            val ledger = root.resolve("decisions.tsv").apply { writeText("id\treading\tsurface\tcost\tdecision\tlexeme_ids\treason\tevidence\n1\tx\tx\t1\tinclude\tlex-x\tverified\thttps://example.org\n") }
            val notices = root.resolve("notices").apply { mkdir() }
            val license = notices.resolve("LICENSE.txt").apply { writeText("Full synthetic fixture notice\n") }
            val out = root.resolve("output").apply { mkdir() }
            writeReviewedCategoryBundle(lexicon, relations, ledger, notices, out)
            assertEquals(license.readText(), out.resolve("grammar/notices/LICENSE.txt").readText())
            val properties = Properties().apply { out.resolve("grammar/bundle.properties").reader().use(::load) }
            assertEquals("true", properties.getProperty("reviewComplete"))
            assertEquals("0", properties.getProperty("pendingRows"))
            assertEquals("1", properties.getProperty("noticeCount"))
            assertEquals(MessageDigest.getInstance("SHA-256").digest(license.readBytes()).joinToString("") { "%02x".format(it) },
                properties.getProperty("notice.LICENSE.txt.sha256"))
        } finally { root.deleteRecursively() }
    }

    @Test fun rejectsChangedMaterializationNoticesBeforeCopyingGrammar() {
        val root = Files.createTempDirectory("category-notice-provenance").toFile()
        try {
            val lexicon = root.resolve("grammar").apply { mkdir() }
            root.resolve("manifest.json").writeText("{\"files\":{\"notices/LICENSE.txt\":\"${"0".repeat(64)}\"}}")
            val notices = root.resolve("notices").apply { mkdir() }
            notices.resolve("LICENSE.txt").writeText("Changed\n")
            val out = root.resolve("output").apply { mkdir() }
            assertFailsWith<IllegalArgumentException> {
                writeReviewedCategoryBundle(lexicon, File("unused"), File("unused"), notices, out)
            }
            assertFalse(out.resolve("grammar").exists())
        } finally { root.deleteRecursively() }
    }
}
