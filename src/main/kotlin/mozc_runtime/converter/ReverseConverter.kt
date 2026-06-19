package mozc_runtime.converter

import mozc_runtime.dictionary.system.SystemDictionary

// Ported from mozc/src/converter/reverse_converter.cc
// Ported from mozc/src/converter/reverse_converter.h
class ReverseConverter(
    private val systemDictionary: SystemDictionary,
    private val immutableConverter: ImmutableConverter,
) {
    fun lookup(value: String, maxCandidates: Int = DefaultMaxCandidates): List<Candidate> {
        require(value.isNotEmpty()) { "Reverse lookup value must not be empty" }
        require(maxCandidates > 0) { "Reverse lookup candidate size must be positive: $maxCandidates" }
        val candidates = ArrayList<Candidate>()
        systemDictionary.lookupReverse(value) { token ->
            if (candidates.size >= maxCandidates) {
                return@lookupReverse
            }
            candidates += Candidate().also { candidate ->
                candidate.key = token.key
                candidate.value = token.value
                candidate.contentKey = token.key
                candidate.contentValue = token.value
                candidate.lid = token.lid
                candidate.rid = token.rid
                candidate.wcost = token.cost
                candidate.cost = token.cost
            }
        }
        return candidates
    }

    fun reverseConvert(value: String, segments: Segments): Boolean {
        segments.clear()
        if (value.isEmpty()) {
            return false
        }
        segments.initForConvert(value)
        val mathKey = normalizeMathExpression(value)
        if (mathKey != null) {
            val candidate = segments.mutableConversionSegment(0).addCandidate()
            candidate.key = value
            candidate.value = mathKey
            return true
        }
        val converted = immutableConverter.convert(
            ConversionOptions(
                requestType = RequestType.REVERSE_CONVERSION,
                maxConversionCandidatesSize = 1,
            ),
            segments,
        )
        if (!converted || segments.segmentsSize() == 0) {
            return false
        }
        segments.all().forEach { segment ->
            if (segment.candidatesSize() == 0 || segment.candidate(0).value.isEmpty()) {
                segments.clear()
                return false
            }
        }
        return true
    }

    private fun normalizeMathExpression(value: String): String? {
        val out = StringBuilder(value.length)
        value.codePoints().toArray().forEach { codePoint ->
            when (codePoint) {
                in 0x0030..0x0039 -> out.appendCodePoint(codePoint)
                in 0xff10..0xff19 -> out.append(('0'.code + codePoint - 0xff10).toChar())
                0x002b, 0xff0b -> out.append('+')
                0x002d, 0x30fc -> out.append('-')
                0x002a, 0xff0a, 0x00d7 -> out.append('*')
                0x002f, 0xff0f, 0x30fb, 0x00f7 -> out.append('/')
                0x0028, 0xff08 -> out.append('(')
                0x0029, 0xff09 -> out.append(')')
                0x003d, 0xff1d -> out.append('=')
                else -> return null
            }
        }
        return out.toString()
    }

    private companion object {
        const val DefaultMaxCandidates: Int = 64
    }
}
