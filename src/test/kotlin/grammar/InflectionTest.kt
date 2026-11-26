package grammar

import com.kazumaproject.grammar.*
import kotlin.test.*

class InflectionTest {
    @Test
    fun coversEachProductiveClassAndCommonIrregularPattern() {
        val rows = listOf(
            row("かく", "書く", InflectionClass.GODAN, "書かない", "書いた", "書いて", "書きます", "書けば"),
            row("およぐ", "泳ぐ", InflectionClass.GODAN, "泳がない", "泳いだ", "泳いで", "泳ぎます", "泳げば"),
            row("はなす", "話す", InflectionClass.GODAN, "話さない", "話した", "話して", "話します", "話せば"),
            row("まつ", "待つ", InflectionClass.GODAN, "待たない", "待った", "待って", "待ちます", "待てば"),
            row("しぬ", "死ぬ", InflectionClass.GODAN, "死なない", "死んだ", "死んで", "死にます", "死ねば"),
            row("よぶ", "呼ぶ", InflectionClass.GODAN, "呼ばない", "呼んだ", "呼んで", "呼びます", "呼べば"),
            row("よむ", "読む", InflectionClass.GODAN, "読まない", "読んだ", "読んで", "読みます", "読めば"),
            row("かえる", "帰る", InflectionClass.GODAN, "帰らない", "帰った", "帰って", "帰ります", "帰れば"),
            row("あう", "会う", InflectionClass.GODAN, "会わない", "会った", "会って", "会います", "会えば"),
            row("きる", "切る", InflectionClass.GODAN, "切らない", "切った", "切って", "切ります", "切れば"),
            row("きる", "着る", InflectionClass.ICHIDAN, "着ない", "着た", "着て", "着ます", "着れば"),
            row("かえる", "変える", InflectionClass.ICHIDAN, "変えない", "変えた", "変えて", "変えます", "変えれば"),
            row("いく", "行く", InflectionClass.GODAN_K_GEMINATE, "行かない", "行った", "行って", "行きます", "行けば"),
            row("とう", "問う", InflectionClass.GODAN_W_U_ONBIN, "問わない", "問うた", "問うて", "問います", "問えば"),
            row("くださる", "下さる", InflectionClass.GODAN_R_HONORIFIC, "下さらない", "下さった", "下さって", "下さいます", "下されば"),
            row("ある", "有る", InflectionClass.ARU, "ない", "有った", "有って", "有ります", "有れば"),
            row("くる", "来る", InflectionClass.KURU, "来ない", "来た", "来て", "来ます", "来れば"),
            row("してくる", "して来る", InflectionClass.KURU, "して来ない", "して来た", "して来て", "して来ます", "して来れば"),
            row("べんきょうする", "勉強する", InflectionClass.SURU, "勉強しない", "勉強した", "勉強して", "勉強します", "勉強すれば"),
            row("ろんずる", "論ずる", InflectionClass.SURU, "論じない", "論じた", "論じて", "論じます", "論ずれば"),
            row("たかい", "高い", InflectionClass.I_ADJECTIVE, "高くない", "高かった", "高くて", "高いです", "高ければ"),
            row("いい", "いい", InflectionClass.I_ADJECTIVE_ALTERNATING, "よくない", "よかった", "よくて", "いいです", "よければ"),
        )
        for ((lexeme, expected) in rows) {
            assertEquals(expected, InflectionForm.entries.map { JapaneseInflection.generate(lexeme, it).surface }, lexeme.surface)
        }
        assertEquals("こない", JapaneseInflection.generate(rows[16].first, InflectionForm.NEGATIVE).reading)
        assertFailsWith<IllegalArgumentException> {
            JapaneseInflection.generate(InflectionLexeme("かく", "書く", InflectionClass.ICHIDAN), InflectionForm.TE)
        }
    }

    private fun row(reading: String, surface: String, type: InflectionClass, vararg forms: String) =
        InflectionLexeme(reading, surface, type) to forms.toList()
}
