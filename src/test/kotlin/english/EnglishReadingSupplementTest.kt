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

    private fun reviewedSource(upstream: List<Dictionary>, supplement: List<EnglishSupplementEntry>): EnglishDictionarySource {
        val rows = (upstream + supplement.map { it.dictionary }).distinctBy { it.yomi to it.tango }
        val review = "reading\tsurface\tdecision\toutput_surface\tsource\treason\n" + rows.joinToString("\n") {
            "${it.yomi}\t${it.tango}\tkeep\t${if (it.tango == "CODE") "code" else it.tango}\thttps://example.org/evidence\tfixture review"
        } + "\n"
        return EnglishDictionarySource(upstream, supplement,
            EnglishCandidateReview.parse(ByteArrayInputStream(review.toByteArray()), "fixture-review.tsv"))
    }

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
    fun acceptsCaseDistinctPairsButRejectsExactDuplicatePairs() {
        assertEquals(2, parse("こーど\tcode\t12500\tjmdict:1\t標準\nこーど\tCODE\t12800\tjmdict:2\t大小文字違い\n").size)
        val error = assertFailsWith<IllegalArgumentException> {
            parse("こーど\tcode\t12500\tjmdict:1\t標準\nこーど\tcode\t12800\tjmdict:2\t重複\n")
        }
        assertTrue(error.message!!.contains("line=3"))
        assertTrue(error.message!!.contains("duplicate"))
    }

    @Test
    fun pronunciationDerivedReadingsRequireFixedSourceAndReviewRecord() {
        val url = "https://github.com/cmusphinx/cmudict/blob/74790861f652b15e4ac49015a90074ad62a27690/cmudict.dict#L1"
        val note = "英語発音から作成・確認した読み; ARPAbet=R IH0 V Y UW1; 全発音を確認"
        assertEquals("review", parse("りびゅー\treview\t12500\t$url\t$note\n").single().dictionary.tango)
        val rawUrl = url.replace("github.com/cmusphinx/cmudict/blob/", "raw.githubusercontent.com/cmusphinx/cmudict/")
        assertEquals("review", parse("りびゅー\treview\t12500\t$rawUrl\t$note\n").single().dictionary.tango)
        for ((source, record) in listOf(
            url.replace("74790861f652b15e4ac49015a90074ad62a27690", "master") to note,
            url.replace("github.com", "GITHUB.COM").replace("74790861f652b15e4ac49015a90074ad62a27690", "master") to note,
            rawUrl.replace("74790861f652b15e4ac49015a90074ad62a27690", "master") to "自動生成・未確認",
            rawUrl to "自動生成・未確認",
            "https://github.com/cmusphinx/cmudict" to note,
            url to "自動生成・未確認; ARPAbet=R IH0 V Y UW1",
            url to "英語発音から作成・確認した読み; 発音未記録",
            url to "英語発音から作成・確認した読み; ARPAbet=R IH V Y UW1",
            url to "英語発音から作成・確認した読み; ARPAbet=R IH0 UNKNOWN UW1",
        )) {
            val error = assertFailsWith<IllegalArgumentException> {
                parse("りびゅー\treview\t12500\t$source\t$record\n")
            }
            assertTrue(error.message!!.contains("line=2"))
        }
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
        val source = reviewedSource(listOf(dictionary("さいと", "web site")), supplement)
        assertEquals(listOf("うぇぶさいと"), source.runtimeEntries.map { it.yomi })
        assertEquals(EnglishCandidateStatus.REVIEW, source.assessments[0].status)
    }

    @Test
    fun acceptsApprovedSoundCardWithoutAdmittingSoundExplanations() {
        val rows = parse("さうんどかーど\tsound card\t12500\tjmdict:2299000\t完全な複合語\n")
        val source = reviewedSource(listOf(dictionary("さうんど", "sound card")), rows)
        assertEquals(listOf("さうんどかーど"), source.runtimeEntries.map { it.yomi })
        for (surface in listOf("sound of a bell", "sound produced by a bell")) {
            assertFailsWith<IllegalArgumentException> { parse("べる\t$surface\t12500\tjmdict:1\t説明文\n") }
        }
    }

    @Test
    fun acceptsTheWordIndicateWhileKeepingItsExplanatorySentencesOut() {
        assertEquals("indicate", parse("いんでぃけいと\tindicate\t12500\tjmdict:1\t全単語の読み\n").single().dictionary.tango)
        for (surface in listOf("indicates interest", "indicate a condition")) {
            assertFailsWith<IllegalArgumentException> {
                parse("いんでぃけいと\t$surface\t12500\tjmdict:1\t説明文\n")
            }
        }
    }

    @Test
    fun keepsHomophonesAndSelectsMinimumCostWithUpstreamWinningTies() {
        val source = reviewedSource(
            listOf(dictionary("こーど", "CODE", 12500), dictionary("きゃっしゅ", "cash", 12800)),
            parse("こーど\tcode\t12500\tjmdict:1\t重複\n" +
                "きゃっしゅ\tcash\t12500\tjmdict:2\t低コスト\n" +
                "きゃっしゅ\tcache\t12500\tjmdict:3\t同音語\n"),
        )
        assertEquals("code", source.runtimeEntries.single { it.yomi == "こーど" }.tango)
        assertEquals(listOf("cache", "cash"), source.runtimeEntries.filter { it.yomi == "きゃっしゅ" }.map { it.tango })
        assertTrue(source.runtimeEntries.all { it.cost.toInt() == 12500 })
        assertEquals(2, source.addedEntries.size)
        assertEquals(1, source.newEnglishSurfaces)
        assertEquals(listOf("cash"), source.changedExistingEntries.map { it.tango })
    }

    @Test
    fun countsNewEnglishSurfacesSeparatelyFromAdditionalReadings() {
        val source = reviewedSource(listOf(dictionary("さーばー", "server")),
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
            Triple("ぷろきし", "ぷろきしー", "proxy"),
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
    fun coversGeneralHeadwordsAndAllSevenAdditionalDomainWords() {
        val pairs = EnglishReadingSupplement.parseResource(1851).associateBy { it.dictionary.yomi to it.dictionary.tango }
        for (pair in listOf(
            "いんぽーたんと" to "important", "あべいらぶる" to "available", "あんだーすたんど" to "understand",
            "れびゅー" to "review", "せーぶ" to "save", "こぴー" to "copy", "えんばいろんめんと" to "environment",
            "どきゅめんと" to "document", "えすてぃめーと" to "estimate", "あぷるーばる" to "approval",
            "でぷろい" to "deploy", "でぃぺんでんしー" to "dependency", "おーせんてぃけーしょん" to "authentication",
            "おーそらいぜーしょん" to "authorization", "こるーちん" to "coroutine", "べんだー" to "vendor",
            "すてーくほるだー" to "stakeholder", "えこのみっく" to "economic", "でぃれくりー" to "directly",
        )) {
            assertEquals(12500, pairs.getValue(pair).dictionary.cost.toInt(), "Missing standard word: $pair")
        }
    }

    @Test
    fun coversAttestedJapaneseReadingsRatherThanOnlyEnglishPronunciations() {
        // Check the adopted dictionary, including upstream rows; these are lexical regression examples,
        // not a claim about frequency, complete Japanese spelling coverage, or final IME ranking.
        val pairs = EnglishDictionarySource.loadResources(1851).runtimeEntries
            .associateBy { it.yomi to it.tango.lowercase(Locale.ROOT) }
        for (pair in listOf(
            "でぷろい" to "deploy", "とらんすふぉーむ" to "transform",
            "てーま" to "theme", "ふるーつ" to "fruit", "すぽーつ" to "sport",
            "すとろーく" to "stroke", "ぴあの" to "piano", "ぷろでゅーさー" to "producer",
            "しゃつ" to "shirt", "とれーす" to "trace", "すとーりー" to "story",
            "ぷりてぃー" to "pretty", "ちゅーん" to "tune", "ぴりおど" to "period",
            "ろー" to "raw", "きゃぴたる" to "capital", "めでぃあむ" to "medium",
            "むーびー" to "movie", "ふぇっち" to "fetch", "にゅーくりあ" to "nuclear",
            "てくにっく" to "technique", "てきすたいる" to "textile",
            "ほいーる" to "wheel", "ぽんど" to "pound", "たっくる" to "tackle",
            "どらっぐ" to "drag", "ふりーくえんしー" to "frequency",
        )) {
            assertEquals(12500, pairs[pair]?.cost?.toInt(), "Missing Japanese input reading: $pair")
        }
        for (pair in listOf(
            "でべろっぷめんと" to "development", "はっぴねす" to "happiness",
            "いりゅーじょん" to "illusion", "でまんど" to "demand", "でぃれー" to "delay",
            "りぽーと" to "report", "いんふぉーめーしょん" to "information",
        )) {
            assertEquals(12800, pairs[pair]?.cost?.toInt(), "Missing documented alternative: $pair")
        }
    }

    @Test
    fun keepsPronunciationReadingsAsAlternativesToAttestedJapaneseInput() {
        val pairs = EnglishDictionarySource.loadResources(1851).runtimeEntries
            .associateBy { it.yomi to it.tango.lowercase(Locale.ROOT) }
        for ((standard, pronunciation, surface) in listOf(
            Triple("でぷろい", "でぃぷろい", "deploy"),
            Triple("てーま", "しーむ", "theme"),
            Triple("ぴあの", "ぴあのー", "piano"),
            Triple("ぷろでゅーさー", "ぷらどぅーさー", "producer"),
            Triple("しゃつ", "しゃーと", "shirt"),
        )) {
            assertEquals(12500, pairs.getValue(standard to surface).cost.toInt())
            assertEquals(12800, pairs.getValue(pronunciation to surface).cost.toInt(), surface)
        }
        // Movie's older spelling is upstream data; preserve its existing cost rather than rewriting it.
        assertEquals(12500, pairs.getValue("むーびー" to "movie").cost.toInt())
        assertEquals(18500, pairs.getValue("むーゔぃー" to "movie").cost.toInt())
        // The shared trie can keep homophones: adding fruit must not remove flute.
        assertTrue("ふるーつ" to "fruit" in pairs)
        assertTrue("ふるーと" to "fruit" in pairs)
        assertTrue("ふるーと" to "flute" in pairs)
    }

    @Test
    fun readingAuditDoesNotAdmitMeaningOnlyOrPartialMatches() {
        val pairs = EnglishDictionarySource.loadResources(1851).runtimeEntries
            .map { it.yomi to it.tango.lowercase(Locale.ROOT) }.toSet()
        for (pair in listOf(
            "すといっく" to "strict", "こんつぇるん" to "combine",
            "ふりーだむ" to "free", "ぷらいむれーと" to "prime",
            "さいすたーと" to "restart", "さいはい" to "deploy",
        )) {
            assertTrue(pair !in pairs, "Meaning-only or partial match was adopted: $pair")
        }
    }

    @Test
    fun coversWholeWordReadingsFromQualifiedGlossesInfinitivesAndProperNames() {
        val pairs = EnglishDictionarySource.loadResources(1851).runtimeEntries
            .associateBy { it.yomi to it.tango }
        for (pair in listOf(
            "ぷろでゅーす" to "produce", "べてらん" to "veteran",
            "うぃるす" to "virus", "おりおん" to "Orion", "さむすん" to "Samsung",
            "すとりくと" to "strict", "らっぷ" to "wrap",
            "えねるぎー" to "energy", "こらむ" to "column", "べくとる" to "vector",
        )) {
            assertEquals(12500, pairs[pair]?.cost?.toInt(), "Missing audited whole-word reading: $pair")
        }
        assertEquals(12800, pairs["れーべる" to "label"]?.cost?.toInt())
        assertEquals(12800, pairs["びーるす" to "virus"]?.cost?.toInt())
        assertTrue(pairs.keys.none { it.second == "samsung" || it.second == "orion" })
        // Irregular/search-only forms are not newly promoted as ordinary missing readings.
        assertTrue("ぷろでゅうす" to "produce" !in pairs)
    }

    @Test
    fun preservesAuditedAlternatePhonemesWithTheirPinnedSource() {
        val pairs = EnglishReadingSupplement.parseResource(1851)
            .associateBy { it.dictionary.yomi to it.dictionary.tango }
        for ((reading, surface, phonemes) in listOf(
            Triple("いくすきゅーず", "excuse", "IH0 K S K Y UW1 Z"),
            Triple("えすためっと", "estimate", "EH1 S T AH0 M AH0 T"),
            Triple("まだれいと", "moderate", "M AA1 D ER0 EY2 T"),
            Triple("ぷろーどぅーす", "produce", "P R OW1 D UW0 S"),
            Triple("れふゅーず", "refuse", "R EH1 F Y UW2 Z"),
            Triple("りーさいん", "resign", "R IY0 S AY1 N"),
            Triple("でゅー", "due", "D Y UW1"),
            Triple("でゅりんぐ", "during", "D Y UH1 R IH0 NG"),
            Triple("まいにゅーと", "minute", "M AY0 N Y UW1 T"),
            Triple("だいれくりー", "directly", "D AY0 R EH1 K L IY0"),
            Triple("じぇにゅーわいん", "genuine", "JH EH1 N Y UW1 W AY2 N"),
        )) {
            val row = pairs.getValue(reading to surface)
            assertEquals(12800, row.dictionary.cost.toInt())
            assertTrue(row.source.contains("74790861f652b15e4ac49015a90074ad62a27690"))
            assertTrue(row.note.contains("ARPAbet=$phonemes;"))
        }
    }

    @Test
    fun preservesDistinctPronunciationsAndTheExistingStemAbbreviation() {
        val supplement = EnglishReadingSupplement.parseResource(1851)
        val source = EnglishDictionarySource(listOf(dictionary("すてむ", "STEM", 18501)), supplement)
        val pairs = source.runtimeEntries.map { it.yomi to it.tango }.toSet()
        for ((surface, first, second) in listOf(
            Triple("read", "りーど", "れっど"), Triple("lead", "りーど", "れっど"),
            Triple("wind", "うぃんど", "わいんど"), Triple("minute", "みにっと", "まいぬーと"),
        )) {
            assertTrue(first to surface in pairs)
            assertTrue(second to surface in pairs)
        }
        assertTrue("すてむ" to "STEM" in pairs)
        assertTrue("すてむ" to "stem" in pairs)
        assertTrue("えーぴーあい" to "API" in pairs)
        assertTrue("じぇいそん" to "JSON" in pairs)
        val newRows = supplement.filter { it.note.startsWith("日本語資料で確認した読み") ||
            it.note.startsWith("英語発音から作成・確認した読み") }
        assertTrue(newRows.all { it.dictionary.tango.matches(Regex("[a-z]+")) })
        assertTrue("いそんかんけい" to "dependency" !in pairs)
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
