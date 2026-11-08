import grammar.Lexicon
import java.io.File
import kotlin.io.path.createTempDirectory
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DistributionPolicyTest {
    @Test
    fun aProperNameExclusionDoesNotCascadeThroughAnOrdinaryHomonymLemma() {
        val root=createTempDirectory("proper-name-homonym").toFile()
        try {
            val grammar=root.resolve("grammar").apply { mkdir() }
            for(name in listOf("categories.tsv","forms.tsv","memberships.tsv")) File("data/grammar",name).copyTo(grammar.resolve(name))
            grammar.resolve("forms.tsv").appendText("proper-python\tPython\tPython\thttps://example.org/name\nproper-python\tPython\tpython\thttps://example.org/name\nordinary-python\tpython\tpython\thttps://example.org/word\nordinary-python\tpython\tpythons\thttps://example.org/word\n")
            grammar.resolve("memberships.tsv").appendText("noun\tproper-python\tPython\nnoun_proper\tproper-python\tPython\nnoun\tproper-python\tpython\nnoun_proper\tproper-python\tpython\nnoun\tordinary-python\tpython\nnoun\tordinary-python\tpythons\n")
            val file=root.resolve("policy.tsv").apply { writeText("surface\tmatch\treason\tevidence\tlicense\nPython\texact\tvictim-person\thttps://example.org/flag\tCC0-1.0\n") }
            val policy=DistributionPolicy(file,Lexicon.load(grammar),emptyList())
            assertTrue(policy.allows("python"));assertTrue(policy.allows("pythons"));assertFalse(policy.allows("Python"))
            policy.filterGrammar(grammar)
            val forms=Lexicon.load(grammar).forms
            assertTrue(forms.none { it.key.lexemeId=="proper-python" })
            assertTrue(forms.count { it.key.lexemeId=="ordinary-python" }==2)
        } finally { root.deleteRecursively() }
    }

    @Test
    fun hashedProperNamesPreserveOrdinaryLowercaseHomonyms() {
        val blocked=setOf(distributionWordKey("She","sha256-exact"),distributionRuleKey("Belladonna","exact"),
            distributionWordKey("Example Victim","sha256-casefold"))
        assertTrue(distributionMatches("She",blocked))
        assertTrue(distributionMatches("Belladonna",blocked))
        assertTrue(distributionMatches("example victim",blocked))
        assertFalse(distributionMatches("she",blocked))
        assertFalse(distributionMatches("belladonna",blocked))
        assertFalse(distributionMatches("shell",blocked))
    }

    @Test
    fun filtersWholeSpellingsAndTheirLexemesWithoutBlockingSubstringsOrMedicalWords() {
        val root=createTempDirectory("distribution-policy").toFile()
        try {
            val grammar=root.resolve("grammar").apply { mkdir() }
            File("data/grammar").listFiles()!!.filter { it.name in setOf("forms.tsv","memberships.tsv","categories.tsv") }
                .forEach { it.copyTo(grammar.resolve(it.name)) }
            val base=Lexicon.load(grammar)
            val policyFile=root.resolve("policy.tsv").apply {
                writeText("surface\tmatch\treason\tevidence\tlicense\nfast\tcasefold\tsexual-slang\thttps://example.org/fixture\tCC-BY-SA-4.0\n")
            }
            val policy=DistributionPolicy(policyFile,base,emptyList())
            assertFalse(policy.allows("Fast"))
            assertTrue(policy.allows("breakfast"))
            assertTrue(policy.allows("consent"))
            assertTrue(policy.allows("contraception"))
            policy.filterGrammar(grammar)
            val filtered=Lexicon.load(grammar)
            assertTrue(filtered.forms.none { it.key.surface.equals("fast",true) || it.lemma.equals("fast",true) })
            assertTrue(filtered.forms.isNotEmpty())
            assertTrue(base.forms.filter { it.key.surface=="consent" }.all { it in filtered.forms })
            assertTrue(policyFile.readText().contains("fast\tcasefold\tsexual-slang"))
        } finally { root.deleteRecursively() }
    }
}
