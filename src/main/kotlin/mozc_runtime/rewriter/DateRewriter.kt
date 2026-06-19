package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import java.time.Clock
import java.time.LocalDate
import java.time.ZoneOffset

// Ported from mozc/src/rewriter/date_rewriter.cc
// Ported from mozc/src/rewriter/date_rewriter.h
class DateRewriter(
    private val clock: Clock,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        var updated = false
        segments.conversionSegments().forEach { segment ->
            updated = rewriteRelativeDate(segment) || updated
            updated = rewriteNumericDateAndTime(segment) || updated
        }
        return updated
    }

    private fun rewriteRelativeDate(segment: Segment): Boolean {
        val data = RelativeDateData[segment.key()] ?: return false
        val base = segment.candidates().firstOrNull { it.value == data.baseValue } ?: segment.baseCandidate() ?: return false
        val date = LocalDate.now(clock.withZone(ZoneOffset.UTC)).plusDays(data.days.toLong())
        val values = listOf(
            "%04d/%02d/%02d".format(date.year, date.monthValue, date.dayOfMonth),
            "%04d-%02d-%02d".format(date.year, date.monthValue, date.dayOfMonth),
            "${date.year}年${date.monthValue}月${date.dayOfMonth}日",
            "${eraName(date)}${eraYear(date)}年${date.monthValue}月${date.dayOfMonth}日",
            "${Weekdays[date.dayOfWeek.value - 1]}曜日",
        )
        segment.insertCandidates(
            minOf(3, segment.candidatesSize()),
            values.map { value -> createDateCandidate(base, value, data.description) },
        )
        return true
    }

    private fun rewriteNumericDateAndTime(segment: Segment): Boolean {
        val base = segment.baseCandidate() ?: return false
        val digits = digitsToHalfWidth(segment.key())
        if (!digits.allDigitsForDate() || digits.length !in 3..4) {
            return false
        }
        val candidates = ArrayList<Candidate>()
        if (digits.length == 3) {
            val a = digits.substring(0, 1).toInt()
            val bc = digits.substring(1, 3).toInt()
            val ab = digits.substring(0, 2).toInt()
            val c = digits.substring(2, 3).toInt()
            candidates += createDateCandidate(base, "$a/$bc", "日付")
            candidates += createDateCandidate(base, "$ab/$c", "日付")
            candidates += createDateCandidate(base, "$a:$bc", "時刻")
            candidates += createDateCandidate(base, "${a}月${bc}日", "日付")
            candidates += createDateCandidate(base, "${ab}月${c}日", "日付")
            candidates += createDateCandidate(base, "${a}時${bc}分", "時刻")
            candidates += createDateCandidate(base, "${ab}時${c}分", "時刻")
            candidates += createDateCandidate(base, "午前${a}時${bc}分", "時刻")
            candidates += createDateCandidate(base, "午後${a}時${bc}分", "時刻")
        } else if (digits.length == 4) {
            val month = digits.substring(0, 2).toInt()
            val day = digits.substring(2, 4).toInt()
            val hour = month
            val minute = day
            candidates += createDateCandidate(base, "$month/$day", "日付")
            candidates += createDateCandidate(base, "$hour:$minute", "時刻")
            candidates += createDateCandidate(base, "${month}月${day}日", "日付")
            candidates += createDateCandidate(base, "${hour}時${minute}分", "時刻")
        }
        if (candidates.isEmpty()) {
            return false
        }
        segment.insertCandidates(segment.candidatesSize(), candidates)
        return true
    }

    private fun createDateCandidate(base: Candidate, value: String, description: String): Candidate =
        Candidate().also { candidate ->
            candidate.key = base.key
            candidate.contentKey = base.contentKey
            candidate.value = value
            candidate.contentValue = ""
            candidate.lid = base.lid
            candidate.rid = base.rid
            candidate.cost = base.cost
            candidate.description = description
            candidate.attributes = candidate.attributes or
                Attribute.NO_HISTORY_LEARNING or
                Attribute.NO_SUGGEST_LEARNING or
                Attribute.NO_VARIANTS_EXPANSION
            candidate.category = Candidate.Category.OTHER
        }

    private data class RelativeDate(
        val days: Int,
        val description: String,
        val baseValue: String,
    )

    companion object {
        private val RelativeDateData = mapOf(
            "きょう" to RelativeDate(0, "今日の日付", "今日"),
            "あした" to RelativeDate(1, "明日の日付", "明日"),
            "あす" to RelativeDate(1, "明日の日付", "明日"),
            "きのう" to RelativeDate(-1, "昨日の日付", "昨日"),
            "さくじつ" to RelativeDate(-1, "昨日の日付", "昨日"),
        )
        private val Weekdays = listOf("月", "火", "水", "木", "金", "土", "日")
    }
}

private fun eraName(date: LocalDate): String =
    when {
        date >= LocalDate.of(2019, 5, 1) -> "令和"
        date >= LocalDate.of(1989, 1, 8) -> "平成"
        date >= LocalDate.of(1926, 12, 25) -> "昭和"
        date >= LocalDate.of(1912, 7, 30) -> "大正"
        else -> "明治"
    }

private fun eraYear(date: LocalDate): Int =
    when {
        date >= LocalDate.of(2019, 5, 1) -> date.year - 2018
        date >= LocalDate.of(1989, 1, 8) -> date.year - 1988
        date >= LocalDate.of(1926, 12, 25) -> date.year - 1925
        date >= LocalDate.of(1912, 7, 30) -> date.year - 1911
        else -> date.year - 1867
    }

private fun String.allDigitsForDate(): Boolean = isNotEmpty() && all { it in '0'..'9' }
