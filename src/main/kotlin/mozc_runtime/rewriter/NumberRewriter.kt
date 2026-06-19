package mozc_runtime.rewriter

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.data.SerializedStringArray
import mozc_runtime.dictionary.PosMatcher
import java.nio.ByteBuffer

// Ported from mozc/src/rewriter/number_rewriter.cc
// Ported from mozc/src/rewriter/number_rewriter.h
class NumberRewriter(
    counterSuffixData: ByteBuffer,
    private val posMatcher: PosMatcher,
) : Rewriter {
    private val counterSuffixes = SerializedStringArray.from(counterSuffixData).toList()

    override fun capability(request: RewriterRequest): Int =
        if (request.mixedConversion) Capability.ALL else Capability.CONVERSION

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useNumberConversion) {
            return false
        }
        var updated = false
        segments.conversionSegments().forEach { segment ->
            updated = rewriteOneSegment(request, segment, segments) || updated
        }
        return updated
    }

    private fun rewriteOneSegment(request: RewriterRequest, segment: Segment, segments: Segments): Boolean {
        val infos = rewriteCandidateInfos(segment)
        if (infos.isEmpty()) {
            return false
        }
        var updated = false
        val erasePositions = sortedSetOf<Int>()
        infos.asReversed().forEach { info ->
            val numberText = info.arabicNumber
            val preferFullWidth = info.candidate.contentValue.isFullWidthDigitsOnly()
            val results = numberCandidates(
                numberText,
                info.type,
                segments.conversionSegmentsSize() == 1 && request.requestType == mozc_runtime.converter.RequestType.CONVERSION,
                preferFullWidth = preferFullWidth,
            )
            setNumberInfoToExistingCandidates(results, segment)
            val candidates = generateCandidates(info.candidate, results)
            if (candidates.all { result -> segment.candidates().any { it.value == result.value } }) {
                return@forEach
            }
            val eraseCandidates = if (preferFullWidth && info.type == RewriteType.ARABIC_FIRST) {
                candidates + generateCandidates(info.candidate, listOf(NumberSurface(numberText, "数字")))
            } else {
                candidates
            }
            findEraseCandidates(eraseCandidates, info.position, info.type, segment, erasePositions)
            insertConvertedCandidates(candidates, info.position, insertPosition(info.position, segment, info.type), segment)
            updated = true
        }
        erasePositions.toList().asReversed().forEach { index -> segment.eraseCandidate(index) }
        return updated
    }

    private fun rewriteCandidateInfos(segment: Segment): List<RewriteCandidateInfo> {
        val result = ArrayList<RewriteCandidateInfo>()
        val seen = HashSet<String>()
        for (index in 0 until segment.candidatesSize()) {
            val candidate = segment.candidate(index)
            if (candidate.attributes and Attribute.NO_MODIFICATION != 0) {
                continue
            }
            val normalized = digitsToHalfWidth(candidate.contentValue)
            val number = when {
                normalized.allDigits() -> normalized
                candidate.contentValue in KanjiToArabic -> KanjiToArabic.getValue(candidate.contentValue)
                hasNumberSuffix(candidate.contentValue) -> leadingDigits(normalized)
                else -> null
            } ?: continue
            if (!seen.add(number)) {
                continue
            }
            val type = if (normalized.allDigits() || candidate.contentKey.allDigits() || digitsToHalfWidth(candidate.contentKey).allDigits()) {
                RewriteType.ARABIC_FIRST
            } else {
                RewriteType.KANJI_FIRST
            }
            result += RewriteCandidateInfo(type, index, candidate.cloneCandidate(), number)
        }
        return result
    }

    private fun hasNumberSuffix(value: String): Boolean =
        counterSuffixes.any { suffix -> value.endsWith(suffix) && value.length > suffix.length }

    private fun leadingDigits(value: String): String? {
        val digits = value.takeWhile { it in '0'..'9' }
        return if (digits.isNotEmpty()) digits else null
    }

    private fun numberCandidates(
        number: String,
        type: RewriteType,
        radix: Boolean,
        preferFullWidth: Boolean,
    ): List<NumberSurface> {
        val result = ArrayList<NumberSurface>()
        fun add(value: String, description: String, noVariants: Boolean = false) {
            if (result.none { it.value == value && it.description == description }) {
                result += NumberSurface(value, description, noVariants)
            }
        }
        if (type == RewriteType.ARABIC_FIRST) {
            if (preferFullWidth) {
                add(toFullWidthDigits(number), "")
            } else {
                add(number, "")
            }
            add(kanjiDigitSequence(number), "漢数字")
            add(toFullWidthDigits(number), "数字")
            addSeparatedForms(number, ::add)
            addMixedArabicKanji(number, ::add)
            add(regularKanjiNumber(number), "漢数字")
            daijiNumbers(number).forEach { add(it, "大字") }
            addSmallNumberForms(number, ::add)
        } else {
            add(regularKanjiNumber(number), "漢数字")
            daijiNumbers(number).forEach { add(it, "大字") }
            add(number, "数字")
            add(toFullWidthDigits(number), "数字")
            addSeparatedForms(number, ::add)
            addMixedArabicKanji(number, ::add)
            addSmallNumberForms(number, ::add)
        }
        if (radix) {
            val numeric = number.toLongOrNull()
            if (numeric != null) {
                if (numeric > 9) {
                    add("0x${numeric.toString(16)}", "16進数", noVariants = true)
                }
                if (numeric > 7) {
                    add("0${numeric.toString(8)}", "8進数", noVariants = true)
                }
                if (numeric > 1) {
                    add("0b${numeric.toString(2)}", "2進数", noVariants = true)
                }
            }
        }
        return result
    }

    private fun generateCandidates(base: Candidate, surfaces: List<NumberSurface>): List<Candidate> =
        surfaces.map { surface ->
            Candidate().also { candidate ->
                candidate.key = base.key
                candidate.contentKey = base.contentKey
                candidate.contentValue = surface.value
                candidate.value = surface.value + base.functionalSuffix()
                candidate.consumedKeySize = base.consumedKeySize
                candidate.cost = base.cost
                candidate.lid = base.lid
                candidate.rid = base.rid
                candidate.description = surface.description
                candidate.attributes = candidate.attributes or
                    (base.attributes and (Attribute.PARTIALLY_KEY_CONSUMED or Attribute.NO_LEARNING))
                if (surface.noVariants) {
                    candidate.attributes = candidate.attributes or Attribute.NO_VARIANTS_EXPANSION
                }
            }
        }

    private fun setNumberInfoToExistingCandidates(surfaces: List<NumberSurface>, segment: Segment) {
        for (index in 0 until segment.candidatesSize()) {
            val candidate = segment.mutableCandidate(index)
            val surface = surfaces.firstOrNull { it.value == candidate.value }
            if (surface != null && candidate.description.isEmpty()) {
                if (digitsToHalfWidth(candidate.contentKey).allDigits() &&
                    digitsToHalfWidth(candidate.value).allDigits()
                ) {
                    continue
                }
                candidate.description = surface.description
            }
        }
    }

    private fun findEraseCandidates(
        results: List<Candidate>,
        basePosition: Int,
        type: RewriteType,
        segment: Segment,
        erasePositions: MutableSet<Int>,
    ) {
        val start = minOf(basePosition + insertOffset(type), segment.candidatesSize() - 1)
        for (position in start downTo 0) {
            if (position == basePosition) {
                continue
            }
            if (segment.candidate(position).attributes and Attribute.NO_MODIFICATION != 0) {
                continue
            }
            if (results.any { it.value == segment.candidate(position).value }) {
                erasePositions += position
            }
        }
    }

    private fun insertConvertedCandidates(
        results: List<Candidate>,
        basePosition: Int,
        initialInsertPosition: Int,
        segment: Segment,
    ) {
        if (results.isEmpty() || basePosition >= segment.candidatesSize()) {
            return
        }
        var insertPos = initialInsertPosition
        val baseValue = segment.candidate(basePosition).value
        val sameSurfaceIndex = results.indexOfFirst { it.value == baseValue }
        if (sameSurfaceIndex == 0 && results[sameSurfaceIndex].description != "漢数字") {
            mergeNumberCandidateInfo(info = results[0], into = segment.mutableCandidate(basePosition))
        } else {
            segment.insertCandidateCopy(basePosition + 1, results[0])
            insertPos += 1
        }
        for (index in 1 until results.size) {
            segment.insertCandidateCopy(insertPos, results[index])
            insertPos += 1
        }
    }

    private fun insertPosition(basePosition: Int, segment: Segment, type: RewriteType): Int =
        minOf(basePosition + insertOffset(type), segment.candidatesSize())

    private fun insertOffset(type: RewriteType): Int =
        if (type == RewriteType.ARABIC_FIRST) 2 else 5

    private fun mergeNumberCandidateInfo(info: Candidate, into: Candidate) {
        into.key = info.key
        into.value = info.value
        into.contentKey = info.contentKey
        into.contentValue = info.contentValue
        into.consumedKeySize = info.consumedKeySize
        into.cost = info.cost
        into.lid = info.lid
        into.rid = info.rid
        into.description = info.description
        into.attributes = into.attributes or info.attributes
    }

    private enum class RewriteType {
        ARABIC_FIRST,
        KANJI_FIRST,
    }

    private data class RewriteCandidateInfo(
        val type: RewriteType,
        val position: Int,
        val candidate: Candidate,
        val arabicNumber: String,
    )

    private data class NumberSurface(
        val value: String,
        val description: String,
        val noVariants: Boolean = false,
    )
}

private fun String.allDigits(): Boolean = isNotEmpty() && all { it in '0'..'9' }

private fun String.isFullWidthDigitsOnly(): Boolean = isNotEmpty() && all { it in '０'..'９' }

internal fun digitsToHalfWidth(value: String): String =
    buildString {
        value.codePoints().forEachOrdered { codePoint ->
            appendCodePoint(if (codePoint in 0xff10..0xff19) codePoint - 0xfee0 else codePoint)
        }
    }

internal fun toFullWidthDigits(value: String): String =
    buildString {
        value.forEach { ch ->
            append(
                when (ch) {
                    in '0'..'9' -> (ch.code + 0xfee0).toChar()
                    ',' -> '，'
                    '.' -> '．'
                    else -> ch
                },
            )
        }
    }

private fun addSeparatedForms(number: String, add: (String, String, Boolean) -> Unit) {
    if (number.length <= 3) {
        return
    }
    val separated = number.reversed().chunked(3).joinToString(",").reversed()
    add(separated, "数字", false)
    add(toFullWidthDigits(separated), "数字", false)
}

private fun addMixedArabicKanji(number: String, add: (String, String, Boolean) -> Unit) {
    val numeric = number.toLongOrNull() ?: return
    if (numeric < 10000) {
        return
    }
    val high = numeric / 10000
    val low = numeric % 10000
    val half = buildString {
        append(high)
        append("万")
        if (low != 0L) {
            append(low)
        }
    }
    add(half, "数字", false)
    add(toFullWidthDigits(half), "数字", false)
}

internal fun kanjiDigitSequence(number: String): String =
    number.map { KanjiDigits[it] ?: it.toString() }.joinToString("")

internal fun regularKanjiNumber(number: String): String {
    val numeric = number.toLongOrNull() ?: return kanjiDigitSequence(number)
    if (numeric == 0L) {
        return "〇"
    }
    return buildLargeKanji(numeric, RegularDigits, "万")
}

private fun daijiNumbers(number: String): List<String> {
    val numeric = number.toLongOrNull() ?: return listOf()
    if (numeric == 0L) {
        return listOf("零")
    }
    val primary = buildLargeKanji(numeric, DaijiDigits, "萬", useDaijiUnits = true, useTwenty = false)
    val values = arrayListOf(primary)
    if (numeric in 20..29 || numeric % 100 in 20..29) {
        val alt = buildLargeKanji(numeric, DaijiDigits, "萬", useDaijiUnits = true, useTwenty = true)
        if (alt != primary) {
            values += alt
        }
    }
    return values
}

private fun buildLargeKanji(
    numeric: Long,
    digits: Map<Int, String>,
    man: String,
    useDaijiUnits: Boolean = false,
    useTwenty: Boolean = false,
): String {
    val high = numeric / 10000
    val low = (numeric % 10000).toInt()
    return buildString {
        if (high > 0) {
            append(buildSmallKanji(high.toInt(), digits, useDaijiUnits, useTwenty))
            append(man)
        }
        if (low > 0) {
            append(buildSmallKanji(low, digits, useDaijiUnits, useTwenty))
        }
    }
}

private fun buildSmallKanji(number: Int, digits: Map<Int, String>, useDaijiUnits: Boolean, useTwenty: Boolean): String {
    val units = if (useDaijiUnits) listOf(1000 to "千", 100 to "百", 10 to "拾") else listOf(1000 to "千", 100 to "百", 10 to "十")
    var rest = number
    return buildString {
        units.forEach { (unit, label) ->
            val digit = rest / unit
            rest %= unit
            if (digit == 0) {
                return@forEach
            }
            if (unit == 10 && digit == 2 && useTwenty) {
                append("廿")
            } else {
                if (digit > 1 || useDaijiUnits) {
                    append(digits.getValue(digit))
                }
                append(label)
            }
        }
        if (rest > 0) {
            append(digits.getValue(rest))
        }
    }
}

private fun addSmallNumberForms(number: String, add: (String, String, Boolean) -> Unit) {
    if (number != "1") {
        return
    }
    add("Ⅰ", "ローマ数字(大文字)", false)
    add("ⅰ", "ローマ数字(小文字)", false)
    add("①", "丸数字", false)
    add("¹", "上付き文字", false)
    add("₁", "下付き文字", false)
}

private val KanjiDigits = mapOf(
    '0' to "〇",
    '1' to "一",
    '2' to "二",
    '3' to "三",
    '4' to "四",
    '5' to "五",
    '6' to "六",
    '7' to "七",
    '8' to "八",
    '9' to "九",
)

private val RegularDigits = mapOf(
    1 to "一",
    2 to "二",
    3 to "三",
    4 to "四",
    5 to "五",
    6 to "六",
    7 to "七",
    8 to "八",
    9 to "九",
)

private val DaijiDigits = mapOf(
    1 to "壱",
    2 to "弐",
    3 to "参",
    4 to "四",
    5 to "伍",
    6 to "六",
    7 to "七",
    8 to "八",
    9 to "九",
)

private val KanjiToArabic = mapOf(
    "一" to "1",
    "二" to "2",
    "三" to "3",
    "四" to "4",
    "五" to "5",
    "六" to "6",
    "七" to "7",
    "八" to "8",
    "九" to "9",
    "〇" to "0",
    "零" to "0",
)
