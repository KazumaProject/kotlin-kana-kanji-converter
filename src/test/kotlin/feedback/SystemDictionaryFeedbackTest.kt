package feedback

import com.kazumaproject.dictionary.models.Dictionary
import com.kazumaproject.feedback.SystemDictionaryFeedback
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import kotlin.test.*

class SystemDictionaryFeedbackTest {
    @Test
    fun exactRemovalKeepsRiverCaseVariantsAndExistingPosCost() {
        val root = Files.createTempDirectory("dictionary-feedback").toFile()
        try {
            val id = File(root, "id.def").apply { writeText("0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n") }
            val checksum = MessageDigest.getInstance("SHA-256").digest(id.readBytes()).joinToString("") { "%02x".format(it) }
            val source = File(root, "system.json").apply {
                writeText("""{"schemaVersion":1,"idDefSha256":"$checksum","exclusions":[["りばーと","Riverと"]],"additions":[["りばー",1,1,9000,"River"],["しんご",1,1,9000,"新語"],["しんご",0,1,9000,"新語"]]}""")
            }
            val river = Dictionary("りばー", 1, 0, 1234, "River")
            val baseline = listOf(river, Dictionary("りばー", 1, 1, 2000, "RIVER"),
                Dictionary("りばーと", 1, 1, 1000, "Riverと"), Dictionary("りばーと", 1, 1, 2000, "RIVERと"))
            val actual = SystemDictionaryFeedback.apply(baseline, source, id)
            assertTrue(river in actual)
            assertEquals(1, actual.count { it.yomi == "りばー" && it.tango == "River" })
            assertFalse(actual.any { it.yomi == "りばーと" && it.tango == "Riverと" })
            assertTrue(actual.any { it.yomi == "りばーと" && it.tango == "RIVERと" })
            assertEquals(2, actual.count { it.yomi == "しんご" })
            assertEquals(actual, SystemDictionaryFeedback.apply(actual, source, id))
            id.appendText("2 other\n")
            assertFailsWith<IllegalArgumentException> { SystemDictionaryFeedback.apply(baseline, source, id) }
        } finally { root.deleteRecursively() }
    }
}
