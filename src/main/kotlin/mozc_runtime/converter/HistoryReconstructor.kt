package mozc_runtime.converter

import mozc_runtime.dictionary.PosMatcher

// Ported from mozc/src/converter/history_reconstructor.cc
// Ported from mozc/src/converter/history_reconstructor.h
class HistoryReconstructor(
    private val posMatcher: PosMatcher,
) {
    fun reconstructHistory(precedingText: String, segments: Segments): Boolean {
        val part = getLastConnectivePart(precedingText) ?: return false
        val segment = segments.addSegment()
        segment.setKey(part.key)
        segment.segmentType = Segment.SegmentType.HISTORY
        val candidate = segment.addCandidate()
        candidate.key = part.key
        candidate.value = part.value
        candidate.contentKey = part.key
        candidate.contentValue = part.value
        candidate.lid = part.id
        candidate.rid = part.id
        candidate.attributes = Attribute.NO_LEARNING
        return true
    }

    fun getLastConnectivePart(precedingText: String): ConnectivePart? {
        val token = extractLastTokenWithScriptType(precedingText) ?: return null
        return when (token.scriptType) {
            ScriptType.NUMBER -> ConnectivePart(
                key = fullWidthAsciiToHalfWidthAscii(token.text),
                value = token.text,
                id = posMatcher.getNumberId(),
            )
            ScriptType.ALPHABET -> ConnectivePart(
                key = fullWidthAsciiToHalfWidthAscii(token.text),
                value = token.text,
                id = posMatcher.getUniqueNounId(),
            )
            else -> null
        }
    }

    data class ConnectivePart(
        val key: String,
        val value: String,
        val id: Int,
    )

    private data class LastToken(
        val text: String,
        val scriptType: ScriptType,
    )

    private fun extractLastTokenWithScriptType(text: String): LastToken? {
        val chars = text.utf8Chars()
        if (chars.isEmpty()) {
            return null
        }
        var index = chars.lastIndex
        if (chars[index].codePoint == SpaceCodePoint) {
            index -= 1
            if (index < 0 || chars[index].codePoint == SpaceCodePoint) {
                return null
            }
        }

        val lastScriptType = getScriptType(chars[index].codePoint)
        val reversed = ArrayList<String>()
        while (index >= 0) {
            val char = chars[index]
            if (char.codePoint == SpaceCodePoint || getScriptType(char.codePoint) != lastScriptType) {
                break
            }
            reversed += char.text
            index -= 1
        }
        if (reversed.isEmpty()) {
            return null
        }
        return LastToken(reversed.asReversed().joinToString(separator = ""), lastScriptType)
    }

    private companion object {
        const val SpaceCodePoint: Int = 0x20
    }
}
