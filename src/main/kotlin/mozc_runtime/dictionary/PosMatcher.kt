package mozc_runtime.dictionary

import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/dictionary/pos_matcher.h
class PosMatcher(
    data: ByteBuffer,
) {
    private val entries: IntArray

    init {
        val buffer = data.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(buffer.remaining() % Short.SIZE_BYTES == 0) {
            "POS matcher data size must be divisible by 2: size=${buffer.remaining()}"
        }
        entries = IntArray(buffer.remaining() / Short.SIZE_BYTES) { index ->
            buffer.getShort(index * Short.SIZE_BYTES).toInt() and 0xffff
        }
        require(entries.size > PosMatcherRule.entries.size * 2) {
            "POS matcher data is too small: shorts=${entries.size} rules=${PosMatcherRule.entries.size}"
        }
        PosMatcherRule.entries.forEach { rule ->
            require(rangeOffset(rule) in entries.indices) {
                "POS matcher range offset is out of bounds: rule=${rule.name} offset=${rangeOffset(rule)} size=${entries.size}"
            }
            validateRanges(rule)
        }
    }

    fun id(rule: PosMatcherRule): Int = entries[rule.ordinal]

    fun matches(rule: PosMatcherRule, posId: Int): Boolean {
        require(posId in 0..UShort.MAX_VALUE.toInt()) {
            "POS id is out of uint16 range: $posId"
        }
        var offset = rangeOffset(rule)
        while (true) {
            require(offset in entries.indices) {
                "POS matcher range is missing sentinel: rule=${rule.name}"
            }
            val start = entries[offset]
            if (start == Sentinel) {
                return false
            }
            require(offset + 1 in entries.indices) {
                "POS matcher range end is missing: rule=${rule.name} offset=$offset"
            }
            val end = entries[offset + 1]
            if (posId in start..end) {
                return true
            }
            offset += 2
        }
    }

    fun size(): Int = entries.size

    fun contains(posId: Int): Boolean = PosMatcherRule.entries.any { matches(it, posId) }

    fun getFunctionalId(): Int = id(PosMatcherRule.Functional)
    fun isFunctional(id: Int): Boolean = matches(PosMatcherRule.Functional, id)
    fun getUnknownId(): Int = id(PosMatcherRule.Unknown)
    fun isUnknown(id: Int): Boolean = matches(PosMatcherRule.Unknown, id)
    fun getFirstNameId(): Int = id(PosMatcherRule.FirstName)
    fun isFirstName(id: Int): Boolean = matches(PosMatcherRule.FirstName, id)
    fun getLastNameId(): Int = id(PosMatcherRule.LastName)
    fun isLastName(id: Int): Boolean = matches(PosMatcherRule.LastName, id)
    fun getNumberId(): Int = id(PosMatcherRule.Number)
    fun isNumber(id: Int): Boolean = matches(PosMatcherRule.Number, id)
    fun getKanjiNumberId(): Int = id(PosMatcherRule.KanjiNumber)
    fun isKanjiNumber(id: Int): Boolean = matches(PosMatcherRule.KanjiNumber, id)
    fun getWeakCompoundNounPrefixId(): Int = id(PosMatcherRule.WeakCompoundNounPrefix)
    fun isWeakCompoundNounPrefix(id: Int): Boolean = matches(PosMatcherRule.WeakCompoundNounPrefix, id)
    fun getWeakCompoundVerbPrefixId(): Int = id(PosMatcherRule.WeakCompoundVerbPrefix)
    fun isWeakCompoundVerbPrefix(id: Int): Boolean = matches(PosMatcherRule.WeakCompoundVerbPrefix, id)
    fun getWeakCompoundFillerPrefixId(): Int = id(PosMatcherRule.WeakCompoundFillerPrefix)
    fun isWeakCompoundFillerPrefix(id: Int): Boolean = matches(PosMatcherRule.WeakCompoundFillerPrefix, id)
    fun getWeakCompoundNounSuffixId(): Int = id(PosMatcherRule.WeakCompoundNounSuffix)
    fun isWeakCompoundNounSuffix(id: Int): Boolean = matches(PosMatcherRule.WeakCompoundNounSuffix, id)
    fun getWeakCompoundVerbSuffixId(): Int = id(PosMatcherRule.WeakCompoundVerbSuffix)
    fun isWeakCompoundVerbSuffix(id: Int): Boolean = matches(PosMatcherRule.WeakCompoundVerbSuffix, id)
    fun getAcceptableParticleAtBeginOfSegmentId(): Int = id(PosMatcherRule.AcceptableParticleAtBeginOfSegment)
    fun isAcceptableParticleAtBeginOfSegment(id: Int): Boolean =
        matches(PosMatcherRule.AcceptableParticleAtBeginOfSegment, id)

    fun getJapanesePunctuationsId(): Int = id(PosMatcherRule.JapanesePunctuations)
    fun isJapanesePunctuations(id: Int): Boolean = matches(PosMatcherRule.JapanesePunctuations, id)
    fun getOpenBracketId(): Int = id(PosMatcherRule.OpenBracket)
    fun isOpenBracket(id: Int): Boolean = matches(PosMatcherRule.OpenBracket, id)
    fun getCloseBracketId(): Int = id(PosMatcherRule.CloseBracket)
    fun isCloseBracket(id: Int): Boolean = matches(PosMatcherRule.CloseBracket, id)
    fun getGeneralSymbolId(): Int = id(PosMatcherRule.GeneralSymbol)
    fun isGeneralSymbol(id: Int): Boolean = matches(PosMatcherRule.GeneralSymbol, id)
    fun getZipcodeId(): Int = id(PosMatcherRule.Zipcode)
    fun isZipcode(id: Int): Boolean = matches(PosMatcherRule.Zipcode, id)
    fun getIsolatedWordId(): Int = id(PosMatcherRule.IsolatedWord)
    fun isIsolatedWord(id: Int): Boolean = matches(PosMatcherRule.IsolatedWord, id)
    fun getSuggestOnlyWordId(): Int = id(PosMatcherRule.SuggestOnlyWord)
    fun isSuggestOnlyWord(id: Int): Boolean = matches(PosMatcherRule.SuggestOnlyWord, id)
    fun getContentWordWithConjugationId(): Int = id(PosMatcherRule.ContentWordWithConjugation)
    fun isContentWordWithConjugation(id: Int): Boolean = matches(PosMatcherRule.ContentWordWithConjugation, id)
    fun getSuffixWordId(): Int = id(PosMatcherRule.SuffixWord)
    fun isSuffixWord(id: Int): Boolean = matches(PosMatcherRule.SuffixWord, id)
    fun getCounterSuffixWordId(): Int = id(PosMatcherRule.CounterSuffixWord)
    fun isCounterSuffixWord(id: Int): Boolean = matches(PosMatcherRule.CounterSuffixWord, id)
    fun getUniqueNounId(): Int = id(PosMatcherRule.UniqueNoun)
    fun isUniqueNoun(id: Int): Boolean = matches(PosMatcherRule.UniqueNoun, id)
    fun getGeneralNounId(): Int = id(PosMatcherRule.GeneralNoun)
    fun isGeneralNoun(id: Int): Boolean = matches(PosMatcherRule.GeneralNoun, id)
    fun getPronounId(): Int = id(PosMatcherRule.Pronoun)
    fun isPronoun(id: Int): Boolean = matches(PosMatcherRule.Pronoun, id)
    fun getContentNounId(): Int = id(PosMatcherRule.ContentNoun)
    fun isContentNoun(id: Int): Boolean = matches(PosMatcherRule.ContentNoun, id)
    fun getNounPrefixId(): Int = id(PosMatcherRule.NounPrefix)
    fun isNounPrefix(id: Int): Boolean = matches(PosMatcherRule.NounPrefix, id)
    fun getEOSSymbolId(): Int = id(PosMatcherRule.EOSSymbol)
    fun isEOSSymbol(id: Int): Boolean = matches(PosMatcherRule.EOSSymbol, id)
    fun getAdverbId(): Int = id(PosMatcherRule.Adverb)
    fun isAdverb(id: Int): Boolean = matches(PosMatcherRule.Adverb, id)
    fun getAdverbSegmentSuffixId(): Int = id(PosMatcherRule.AdverbSegmentSuffix)
    fun isAdverbSegmentSuffix(id: Int): Boolean = matches(PosMatcherRule.AdverbSegmentSuffix, id)
    fun getParallelMarkerId(): Int = id(PosMatcherRule.ParallelMarker)
    fun isParallelMarker(id: Int): Boolean = matches(PosMatcherRule.ParallelMarker, id)
    fun getTeSuffixId(): Int = id(PosMatcherRule.TeSuffix)
    fun isTeSuffix(id: Int): Boolean = matches(PosMatcherRule.TeSuffix, id)
    fun getVerbSuffixId(): Int = id(PosMatcherRule.VerbSuffix)
    fun isVerbSuffix(id: Int): Boolean = matches(PosMatcherRule.VerbSuffix, id)
    fun getKagyoTaConnectionVerbId(): Int = id(PosMatcherRule.KagyoTaConnectionVerb)
    fun isKagyoTaConnectionVerb(id: Int): Boolean = matches(PosMatcherRule.KagyoTaConnectionVerb, id)
    fun getWagyoRenyoConnectionVerbId(): Int = id(PosMatcherRule.WagyoRenyoConnectionVerb)
    fun isWagyoRenyoConnectionVerb(id: Int): Boolean = matches(PosMatcherRule.WagyoRenyoConnectionVerb, id)

    private fun rangeOffset(rule: PosMatcherRule): Int =
        entries[PosMatcherRule.entries.size + rule.ordinal]

    private fun validateRanges(rule: PosMatcherRule) {
        var offset = rangeOffset(rule)
        while (true) {
            require(offset in entries.indices) {
                "POS matcher range is missing sentinel: rule=${rule.name}"
            }
            val start = entries[offset]
            if (start == Sentinel) {
                return
            }
            require(offset + 1 in entries.indices) {
                "POS matcher range end is missing: rule=${rule.name} offset=$offset"
            }
            val end = entries[offset + 1]
            require(start <= end) {
                "POS matcher range start exceeds end: rule=${rule.name} start=$start end=$end"
            }
            offset += 2
        }
    }

    private companion object {
        const val Sentinel: Int = 0xffff
    }
}

enum class PosMatcherRule {
    Functional,
    Unknown,
    FirstName,
    LastName,
    Number,
    KanjiNumber,
    WeakCompoundNounPrefix,
    WeakCompoundVerbPrefix,
    WeakCompoundFillerPrefix,
    WeakCompoundNounSuffix,
    WeakCompoundVerbSuffix,
    AcceptableParticleAtBeginOfSegment,
    JapanesePunctuations,
    OpenBracket,
    CloseBracket,
    GeneralSymbol,
    Zipcode,
    IsolatedWord,
    SuggestOnlyWord,
    ContentWordWithConjugation,
    SuffixWord,
    CounterSuffixWord,
    UniqueNoun,
    GeneralNoun,
    Pronoun,
    ContentNoun,
    NounPrefix,
    EOSSymbol,
    Adverb,
    AdverbSegmentSuffix,
    ParallelMarker,
    TeSuffix,
    VerbSuffix,
    KagyoTaConnectionVerb,
    WagyoRenyoConnectionVerb,
}
