package mozc_runtime.prediction

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.charsLen
import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/prediction/number_decoder.h
// Ported from mozc/src/prediction/number_decoder.cc
class NumberDecoder(
    private val posMatcher: PosMatcher,
) {
    fun decode(key: String): List<NumberDecoderResult> {
        val state = NumberState(key = key)
        val results = ArrayList<NumberDecoderResult>()
        decodeAux(key, state, results)
        maybeAppendResult(state, results)
        return results
    }

    fun decodeResults(key: String): List<Result> {
        val results = ArrayList<Result>()
        decode(key).forEach { decoded ->
            val resultKey = key.substringByUtf8Bytes(0, decoded.consumedKeyByteLength)
            val isArabic = decoded.candidate.all { it in '0'..'9' }
            var attributes = Attribute.DEFAULT_ATTRIBUTE or PredictionTypes.Number or Attribute.NO_SUGGEST_LEARNING
            val consumedChars = resultKey.charsLen()
            if (decoded.consumedKeyByteLength < key.toByteArray(Charsets.UTF_8).size) {
                attributes = attributes or PredictionTypes.Prefix
            }
            results += Result(
                key = resultKey,
                value = decoded.candidate,
                contentKey = resultKey,
                contentValue = decoded.candidate,
                attributes = attributes,
                wcost = 1000 * (1 + decoded.digitNumber),
                lid = if (isArabic) posMatcher.getNumberId() else posMatcher.getKanjiNumberId(),
                rid = if (isArabic) posMatcher.getNumberId() else posMatcher.getKanjiNumberId(),
                consumedKeySize = if (decoded.consumedKeyByteLength < key.toByteArray(Charsets.UTF_8).size) consumedChars else 0,
            )
        }
        return results
    }

    private fun decodeAux(key: String, state: NumberState, results: MutableList<NumberDecoderResult>) {
        if (key.isEmpty()) {
            return
        }
        val match = Entries.longestMatch(key) ?: return
        val entry = match.entry
        val consumed = match.key
        when (entry.type) {
            NumberEntryType.STOP_DECODING -> return
            NumberEntryType.UNIT -> {
                if (!handleUnitEntry(consumed, entry, state, results)) return
                state.consumedKeyByteLength += consumed.toByteArray(Charsets.UTF_8).size
            }
            NumberEntryType.SMALL_DIGIT -> {
                if (!handleSmallDigitEntry(consumed, entry, state, results)) return
                state.consumedKeyByteLength += consumed.toByteArray(Charsets.UTF_8).size
            }
            NumberEntryType.BIG_DIGIT -> {
                if (!handleBigDigitEntry(consumed, entry, state, results)) return
                state.consumedKeyByteLength += consumed.toByteArray(Charsets.UTF_8).size
            }
            NumberEntryType.UNIT_AND_BIG_DIGIT -> {
                val unitKey = consumed.substringByUtf8Bytes(0, entry.consumeByteLengthOfFirst)
                if (!handleUnitEntry(unitKey, entry, state, results)) return
                state.consumedKeyByteLength += entry.consumeByteLengthOfFirst
                val digitKey = consumed.substringByUtf8Bytes(entry.consumeByteLengthOfFirst)
                if (!handleBigDigitEntry(digitKey, entry, state, results)) return
                state.consumedKeyByteLength += consumed.toByteArray(Charsets.UTF_8).size - entry.consumeByteLengthOfFirst
            }
            NumberEntryType.UNIT_AND_STOP_DECODING -> {
                val unitKey = consumed.substringByUtf8Bytes(0, entry.consumeByteLengthOfFirst)
                if (!handleUnitEntry(unitKey, entry, state, results)) return
                state.consumedKeyByteLength += entry.consumeByteLengthOfFirst
                return
            }
        }
        decodeAux(key.removePrefix(consumed), state, results)
    }

    private fun handleUnitEntry(
        key: String,
        entry: NumberEntry,
        state: NumberState,
        results: MutableList<NumberDecoderResult>,
    ): Boolean {
        results.clear()
        if (state.isValid() && entry.number == 0) return false
        if (state.smallDigitNumber == 0 || (state.smallDigitNumber != -1 && state.smallDigitNumber % 10 != 0)) {
            return false
        }
        if (entry.outputBeforeDecode) {
            maybeAppendResult(state, results)
        }
        state.smallDigitNumber = if (state.smallDigitNumber == -1) {
            entry.number
        } else {
            state.smallDigitNumber + entry.number
        }
        state.consumedKeys += key
        state.digitNumber = maxOf(state.digitNumber, 1)
        return true
    }

    private fun handleSmallDigitEntry(
        key: String,
        entry: NumberEntry,
        state: NumberState,
        results: MutableList<NumberDecoderResult>,
    ): Boolean {
        results.clear()
        if (state.smallDigit > 1 && entry.digit >= state.smallDigit) return false
        if (state.smallDigitNumber == 0) return false
        if (entry.outputBeforeDecode) {
            maybeAppendResult(state, results)
        }
        state.smallDigitNumber = if (state.smallDigitNumber == -1) {
            entry.number
        } else {
            val unit = maxOf(1, state.smallDigitNumber % 10)
            val base = (state.smallDigitNumber / 10) * 10
            base + unit * entry.number
        }
        state.smallDigit = entry.digit
        state.consumedKeys += key
        state.digitNumber = maxOf(state.digitNumber, entry.digit)
        return true
    }

    private fun handleBigDigitEntry(
        key: String,
        entry: NumberEntry,
        state: NumberState,
        results: MutableList<NumberDecoderResult>,
    ): Boolean {
        results.clear()
        if (state.bigDigit > 0 && entry.digit >= state.bigDigit) return false
        if (state.smallDigitNumber == -1 || state.smallDigitNumber == 0) return false
        if (entry.outputBeforeDecode) {
            maybeAppendResult(state, results)
        }
        state.currentNumber += state.smallDigitNumber.toString() + entry.digitString
        state.digitNumber = maxOf(state.digitNumber, entry.digit + state.smallDigitNumber.toString().length - 1)
        state.smallDigitNumber = -1
        state.smallDigit = -1
        state.bigDigit = entry.digit
        state.consumedKeys += key
        return true
    }

    private fun maybeAppendResult(state: NumberState, results: MutableList<NumberDecoderResult>) {
        val result = state.result() ?: return
        val keys = ArrayList(state.consumedKeys)
        val keyBytes = state.key.toByteArray(Charsets.UTF_8)
        if (state.consumedKeyByteLength < keyBytes.size) {
            keys += state.key.substringByUtf8Bytes(state.consumedKeyByteLength)
        }
        keys.forEachIndexed { index, key ->
            if ((key == "よ" || key == "く") && index + 1 < keys.size) {
                return
            }
            if (key == "し" && !(index + 1 == keys.size || keys[index + 1] == "じゅう")) {
                return
            }
        }
        results += result
    }

    private data class NumberState(
        var smallDigitNumber: Int = -1,
        var currentNumber: String = "",
        var smallDigit: Int = -1,
        var bigDigit: Int = -1,
        var consumedKeyByteLength: Int = 0,
        val key: String,
        val consumedKeys: MutableList<String> = ArrayList(),
        var digitNumber: Int = 0,
    ) {
        fun isValid(): Boolean = !(smallDigitNumber == -1 && smallDigit == -1 && bigDigit == -1)

        fun result(): NumberDecoderResult? {
            if (!isValid()) return null
            val small = maxOf(smallDigitNumber, 0)
            return when {
                small > 0 -> NumberDecoderResult(consumedKeyByteLength, currentNumber + small, digitNumber)
                currentNumber.isNotEmpty() -> NumberDecoderResult(consumedKeyByteLength, currentNumber, digitNumber)
                small == 0 -> NumberDecoderResult(consumedKeyByteLength, "0", 1)
                else -> null
            }
        }
    }

    private enum class NumberEntryType {
        STOP_DECODING,
        UNIT,
        SMALL_DIGIT,
        BIG_DIGIT,
        UNIT_AND_BIG_DIGIT,
        UNIT_AND_STOP_DECODING,
    }

    private data class NumberEntry(
        val type: NumberEntryType = NumberEntryType.STOP_DECODING,
        val number: Int = 0,
        val digit: Int = 1,
        val digitString: String = "",
        val outputBeforeDecode: Boolean = false,
        val consumeByteLengthOfFirst: Int = 0,
    )

    private data class EntryMatch(val key: String, val entry: NumberEntry)

    private object Entries {
        private val entries: Map<String, NumberEntry> = buildMap {
            add("ぜろ", NumberEntry(NumberEntryType.UNIT, 0))
            add("いち", NumberEntry(NumberEntryType.UNIT, 1))
            add("いっ", NumberEntry(NumberEntryType.UNIT, 1))
            add("に", NumberEntry(NumberEntryType.UNIT, 2))
            add("さん", NumberEntry(NumberEntryType.UNIT, 3))
            add("し", NumberEntry(NumberEntryType.UNIT, 4))
            add("よん", NumberEntry(NumberEntryType.UNIT, 4))
            add("よ", NumberEntry(NumberEntryType.UNIT, 4))
            add("ご", NumberEntry(NumberEntryType.UNIT, 5))
            add("ろく", NumberEntry(NumberEntryType.UNIT, 6))
            add("ろっ", NumberEntry(NumberEntryType.UNIT, 6))
            add("なな", NumberEntry(NumberEntryType.UNIT, 7))
            add("しち", NumberEntry(NumberEntryType.UNIT, 7))
            add("はち", NumberEntry(NumberEntryType.UNIT, 8))
            add("はっ", NumberEntry(NumberEntryType.UNIT, 8))
            add("きゅう", NumberEntry(NumberEntryType.UNIT, 9))
            add("きゅー", NumberEntry(NumberEntryType.UNIT, 9))
            add("く", NumberEntry(NumberEntryType.UNIT, 9))
            add("じゅう", NumberEntry(NumberEntryType.SMALL_DIGIT, 10, 2, outputBeforeDecode = true))
            add("じゅー", NumberEntry(NumberEntryType.SMALL_DIGIT, 10, 2, outputBeforeDecode = true))
            add("じゅっ", NumberEntry(NumberEntryType.SMALL_DIGIT, 10, 2))
            add("ひゃく", NumberEntry(NumberEntryType.SMALL_DIGIT, 100, 3))
            add("ひゃっ", NumberEntry(NumberEntryType.SMALL_DIGIT, 100, 3))
            add("びゃく", NumberEntry(NumberEntryType.SMALL_DIGIT, 100, 3))
            add("びゃっ", NumberEntry(NumberEntryType.SMALL_DIGIT, 100, 3))
            add("ぴゃく", NumberEntry(NumberEntryType.SMALL_DIGIT, 100, 3))
            add("ぴゃっ", NumberEntry(NumberEntryType.SMALL_DIGIT, 100, 3))
            add("せん", NumberEntry(NumberEntryType.SMALL_DIGIT, 1000, 4, outputBeforeDecode = true))
            add("ぜん", NumberEntry(NumberEntryType.SMALL_DIGIT, 1000, 4, outputBeforeDecode = true))
            add("まん", NumberEntry(NumberEntryType.BIG_DIGIT, 10000, 5, "万"))
            add("おく", NumberEntry(NumberEntryType.BIG_DIGIT, -1, 9, "億"))
            add("おっ", NumberEntry(NumberEntryType.BIG_DIGIT, -1, 9, "億"))
            add("ちょう", NumberEntry(NumberEntryType.BIG_DIGIT, -1, 13, "兆", true))
            add("けい", NumberEntry(NumberEntryType.BIG_DIGIT, -1, 17, "京", true))
            add("がい", NumberEntry(NumberEntryType.BIG_DIGIT, -1, 21, "垓"))
            add("にちょう", NumberEntry(NumberEntryType.UNIT_AND_BIG_DIGIT, 2, 13, "兆", true, 3))
            add("にちょうめ", NumberEntry(NumberEntryType.UNIT_AND_STOP_DECODING, 2, -1, consumeByteLengthOfFirst = 3))
            add("にちゃん", NumberEntry(NumberEntryType.UNIT_AND_STOP_DECODING, 2, -1, consumeByteLengthOfFirst = 3))
            add("さんちーむ", NumberEntry(NumberEntryType.UNIT_AND_STOP_DECODING, 3, -1, outputBeforeDecode = true, consumeByteLengthOfFirst = 6))
            listOf(
                "にぎり", "にち", "にん", "しーしー", "しーと", "しーべると", "しあい", "しき", "しつ",
                "しな", "しゃ", "しゅ", "しょう", "しょく", "しりんぐ", "しん", "よう", "ごう",
                "くだり", "くち", "くみ", "くらす", "くろーな", "せんち", "せんと", "おくたーぶ", "ちょうめ",
            ).forEach { add(it, NumberEntry()) }
        }

        fun longestMatch(key: String): EntryMatch? =
            entries.keys.asSequence()
                .filter { key.startsWith(it) }
                .maxByOrNull { it.toByteArray(Charsets.UTF_8).size }
                ?.let { EntryMatch(it, entries.getValue(it)) }

        private fun MutableMap<String, NumberEntry>.add(key: String, entry: NumberEntry) {
            put(key, entry)
        }
    }
}

data class NumberDecoderResult(
    val consumedKeyByteLength: Int,
    val candidate: String,
    val digitNumber: Int,
)

private fun String.substringByUtf8Bytes(start: Int, byteSize: Int = toByteArray(Charsets.UTF_8).size - start): String {
    val bytes = toByteArray(Charsets.UTF_8)
    return String(bytes, start, byteSize, Charsets.UTF_8)
}
