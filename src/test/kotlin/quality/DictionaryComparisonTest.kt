package quality

import com.kazumaproject.quality.DictionaryComparison
import java.nio.file.Files
import kotlinx.serialization.json.*
import kotlin.test.*

class DictionaryComparisonTest {
    @Test fun terminalNonDistributionDoesNotBecomeAHeldQueue() {
        val dir=Files.createTempDirectory("comparison-final-").toFile()
        try {
            val header="phase\treading\tsurface\tleft_id\tright_id\tcategories\treason\tquality_status\treading_evidence\n"
            val before=dir.resolve("before.tsv").apply { writeText(header+"classification\tかな\t仮名\t1\t1\tunclassified\tunknown\theld\t\n") }
            val after=dir.resolve("after.tsv").apply { writeText(header+"classification\tかな\t仮名\t1\t1\t\tcompleted-insufficient-evidence\tnot_distributed\t\n") }
            val result=DictionaryComparison.compare(before,after,dir.resolve("out"))
            assertEquals(1,result.getValue("states").jsonObject.getValue("not_distributed").jsonPrimitive.int)
            assertFalse("held" in result.getValue("states").jsonObject)
        } finally { dir.deleteRecursively() }
    }
    @Test fun accountsForAdoptionAndExplicitExclusionWithoutCallingMissingEvidenceWrong() {
        val dir=Files.createTempDirectory("comparison-").toFile()
        try {
            val header="phase\treading\tsurface\tleft_id\tright_id\tcategories\treason\tquality_status\treading_evidence\n"
            val before=dir.resolve("before.tsv").apply { writeText(header+"classification\tかな\t仮名\t1\t1\tunclassified\tunknown\theld\t\nclassification\tごどく\t誤読\t1\t1\tperson\tunknown\theld\t\n") }
            val after=dir.resolve("after.tsv").apply { writeText(header+"classification\tかな\t仮名\t1\t1\tgeneral\tJMdict\taccepted\treading\nnormalization\tごどく\t誤読\t1\t1\t\tconfirmed-error\texcluded\tURL\n") }
            val summary=DictionaryComparison.compare(before,after,dir.resolve("out"))
            assertEquals(2,summary.getValue("accounted").jsonPrimitive.int)
            assertEquals(1,summary.getValue("states").jsonObject.getValue("adopted").jsonPrimitive.int)
            after.writeText(header)
            assertFailsWith<IllegalArgumentException> { DictionaryComparison.compare(before,after,dir.resolve("missing")) }
        } finally { dir.deleteRecursively() }
    }
}
