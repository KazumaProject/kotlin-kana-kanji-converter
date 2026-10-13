package english

import com.kazumaproject.english.*
import com.kazumaproject.dictionary.models.Dictionary
import java.io.ByteArrayInputStream
import java.util.Locale
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class EnglishReadingSupplementTest {
    private val header = "reading\tsurface\tcost\tsource\tnote\n"
    private fun parse(rows: String) = EnglishReadingSupplement.parse(
        ByteArrayInputStream((header + rows).toByteArray()), "fixture.tsv", 1851,
    )
    private fun dictionary(reading: String, surface: String, cost: Int = 12500) =
        Dictionary(reading, 1851, 1851, cost.toShort(), surface)

    @Test
    fun parsesProvenanceAndKeepsOriginalAbbreviationAndCompound() {
        val rows = parse("えーぴーあい\tAPI\t12500\tjmdict:2285430\t標準読み\n" +
            "うぇぶさいと\tweb site\t12800\thttps://example.org/web\t確認した複合語\n")
        assertEquals(listOf("API", "web site"), rows.map { it.dictionary.tango })
        assertEquals("jmdict:2285430", rows[0].source)
        assertTrue(rows.all { it.dictionary.leftId.toInt() == 1851 && it.dictionary.rightId.toInt() == 1851 })
    }

    @Test
    fun invalidRowsFailWithSourceAndLineNumber() {
        for (row in listOf(
            "さーばー\tserver\t12500\tjmdict:1", // missing note
            "サーバー\tserver\t12500\tjmdict:1\t読み未正規化",
            "さーばー\tserver (machine)\t12500\tjmdict:1\t注釈",
            "さーばー\tserver\t32768\tjmdict:1\t範囲外",
            "さーばー\tserver\t12500\thttp://example.org\tHTTPSではない",
            "さーばー\tserver\t12500\tjmdict:1\t",
            "さーばー\tserver\t12500\tjmdict:1\t備考\textra",
        )) {
            val error = assertFailsWith<IllegalArgumentException> { parse(row + "\n") }
            assertTrue(error.message!!.contains("fixture.tsv"))
            assertTrue(error.message!!.contains("line=2"))
        }
    }

    @Test
    fun rejectsCaseInsensitiveDuplicatePairs() {
        val error = assertFailsWith<IllegalArgumentException> {
            parse("こーど\tcode\t12500\tjmdict:1\t標準\nこーど\tCODE\t12800\tjmdict:2\t重複\n")
        }
        assertTrue(error.message!!.contains("line=3"))
        assertTrue(error.message!!.contains("duplicate"))
    }

    @Test
    fun approvalDoesNotBypassNumericFunctionWordOrExplanatoryExclusions() {
        for ((reading, surface) in listOf("ぜろ" to "zero", "あんど" to "and", "えー" to "A",
            "でばいす" to "device used for writing", "めそっど" to "method of writing")) {
            assertFailsWith<IllegalArgumentException> { parse("$reading\t$surface\t12500\tjmdict:1\t禁止例\n") }
        }
    }

    @Test
    fun compoundApprovalAppliesOnlyToTheCompletePair() {
        val supplement = parse("うぇぶさいと\tweb site\t12500\tjmdict:1\t読み全体を確認\n")
        val source = EnglishDictionarySource(listOf(dictionary("さいと", "web site")), supplement)
        assertEquals(listOf("うぇぶさいと"), source.runtimeEntries.map { it.yomi })
        assertEquals(EnglishCandidateStatus.REVIEW, source.assessments[0].status)
    }

    @Test
    fun acceptsApprovedSoundCardWithoutAdmittingSoundExplanations() {
        val rows = parse("さうんどかーど\tsound card\t12500\tjmdict:2299000\t完全な複合語\n")
        val source = EnglishDictionarySource(listOf(dictionary("さうんど", "sound card")), rows)
        assertEquals(listOf("さうんどかーど"), source.runtimeEntries.map { it.yomi })
        for (surface in listOf("sound of a bell", "sound produced by a bell")) {
            assertFailsWith<IllegalArgumentException> { parse("べる\t$surface\t12500\tjmdict:1\t説明文\n") }
        }
    }

    @Test
    fun keepsHomophonesAndSelectsMinimumCostWithUpstreamWinningTies() {
        val source = EnglishDictionarySource(
            listOf(dictionary("こーど", "CODE", 12500), dictionary("きゃっしゅ", "cash", 12800)),
            parse("こーど\tcode\t12500\tjmdict:1\t重複\n" +
                "きゃっしゅ\tcash\t12500\tjmdict:2\t低コスト\n" +
                "きゃっしゅ\tcache\t12500\tjmdict:3\t同音語\n"),
        )
        assertEquals("CODE", source.runtimeEntries.single { it.yomi == "こーど" }.tango)
        assertEquals(listOf("cache", "cash"), source.runtimeEntries.filter { it.yomi == "きゃっしゅ" }.map { it.tango })
        assertTrue(source.runtimeEntries.all { it.cost.toInt() == 12500 })
        assertEquals(1, source.addedEntries.size)
        assertEquals(1, source.newEnglishSurfaces)
        assertEquals(listOf("cash"), source.changedExistingEntries.map { it.tango })
    }

    @Test
    fun countsNewEnglishSurfacesSeparatelyFromAdditionalReadings() {
        val source = EnglishDictionarySource(listOf(dictionary("さーばー", "server")),
            parse("さーば\tserver\t12800\tjmdict:1\t読み揺れ\nこーひー\tcoffee\t12500\tjmdict:2\t標準\n"))
        assertEquals(2, source.addedEntries.size)
        assertEquals(1, source.newEnglishSurfaces)
        assertEquals(1, source.addedReadingsForExistingSurfaces)
    }

    @Test
    fun keepsAttestedStandardReadingsAheadOfSearchOnlyVariants() {
        val rows = EnglishReadingSupplement.parseResource(1851).associateBy { it.dictionary.yomi to it.dictionary.tango }
        for ((standard, variant, surface) in listOf(
            Triple("でぃれくとりつりー", "でぃれくとりーつりー", "directory tree"),
            Triple("しぇあーどらいぶらり", "しぇあーどらいぶらりー", "shared library"),
            Triple("きゃぷすろっく", "きゃっぷすろっく", "caps lock"),
        )) {
            assertEquals(12500, rows.getValue(standard to surface).dictionary.cost.toInt())
            assertEquals(12800, rows.getValue(variant to surface).dictionary.cost.toInt())
        }
    }

    @Test
    fun coversChosenDailyDevelopmentAndWorkUsageExamples() {
        // A chosen regression sample, not a frequency-weighted coverage estimate or an IME ranking test.
        val source = EnglishDictionarySource.loadResources(1851)
        val pairs = source.runtimeEntries.map { it.yomi to it.tango.lowercase(Locale.ROOT) }.toSet()
        val samples = listOf(
            "あっぷる" to "apple",
            "とまと" to "tomato",
            "おれんじ" to "orange",
            "れもん" to "lemon",
            "ばなな" to "banana",
            "こーひー" to "coffee",
            "ちょこれーと" to "chocolate",
            "みるく" to "milk",
            "ぶるー" to "blue",
            "ぐりーん" to "green",
            "ぴんく" to "pink",
            "ぺん" to "pen",
            "てーぶる" to "table",
            "ほてる" to "hotel",
            "ぱすぽーと" to "passport",
            "ちけっと" to "ticket",
            "れすとらん" to "restaurant",
            "かれんだー" to "calendar",
            "すけじゅーる" to "schedule",
            "ぷれぜんと" to "present",
            "はっぴー" to "happy",
            "へるぷ" to "help",
            "はろー" to "hello",
            "せんきゅー" to "thank you",
            "こーど" to "code",
            "こみっと" to "commit",
            "ぎっと" to "git",
            "ぎっとはぶ" to "github",
            "どっかー" to "docker",
            "こまんど" to "command",
            "こまんどらいん" to "command line",
            "ぷるりくえすと" to "pull request",
            "そーすこーど" to "source code",
            "りふぁくたりんぐ" to "refactoring",
            "でばっぐ" to "debug",
            "まーじ" to "merge",
            "ぶらんち" to "branch",
            "くろーん" to "clone",
            "りべーす" to "rebase",
            "ぱいそん" to "python",
            "じゃばすくりぷと" to "javascript",
            "たいぷすくりぷと" to "typescript",
            "えーぴーあい" to "api",
            "じぇいそん" to "json",
            "えすきゅーえる" to "sql",
            "でーたべーす" to "database",
            "りぽじとり" to "repository",
            "てすとけーす" to "test case",
            "めーる" to "mail",
            "いーめーる" to "email",
            "みーてぃんぐ" to "meeting",
            "おんらいんみーてぃんぐ" to "online meeting",
            "あじぇんだ" to "agenda",
            "でっどらいん" to "deadline",
            "たすく" to "task",
            "すけじゅーる" to "schedule",
            "れぽーと" to "report",
            "ぷれぜんてーしょん" to "presentation",
            "ふぃーどばっく" to "feedback",
            "りまいんだー" to "reminder",
            "ふぉろーあっぷ" to "follow-up",
            "りもーとわーく" to "remote work",
            "ぷろじぇくと" to "project",
            "まねーじゃー" to "manager",
            "ちーむ" to "team",
            "ちぇっくりすと" to "checklist",
            "あくしょんあいてむ" to "action item",
            "おんぼーでぃんぐ" to "onboarding",
            "ちゃっと" to "chat",
            "りんく" to "link",
            "きゃんせる" to "cancel",
        )
        samples.forEach { assertTrue(it in pairs, "Missing usage example: $it") }
    }

    @Test
    fun committedSupplementHasRequiredCoverageAndNoMeaningOnlyPairs() {
        val rows = EnglishReadingSupplement.parseResource(1851)
        val pairs = rows.map { it.dictionary.yomi to it.dictionary.tango }.toSet()
        for (pair in listOf("こーひー" to "coffee", "さーばー" to "server", "さーば" to "server",
            "ぶらうざー" to "browser", "ぶらうざ" to "browser", "きーぼーど" to "keyboard",
            "ぱすわーど" to "password", "えーぴーあい" to "API", "じぇいそん" to "JSON",
            "そーすこーど" to "source code", "こまんどらいん" to "command line",
            "ぷるりくえすと" to "pull request", "おんらいんみーてぃんぐ" to "online meeting",
            "りもーとわーく" to "remote work", "めーるぼっくす" to "mailbox")) {
            assertTrue(pair in pairs, "Missing required supplement pair: $pair")
        }
        assertTrue(("りんご" to "apple") !in pairs)
        assertTrue(("ぎゃらりー" to "art gallery") !in pairs)
        assertTrue(rows.all { '(' !in it.dictionary.tango && ')' !in it.dictionary.tango })
    }
}
