package mozc_runtime.rewriter

import mozc_data.MozcDataManager
import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.converter.utf8Size
import mozc_runtime.data.SerializedStringArray
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/rewriter/emoji_rewriter.cc
// Ported from mozc/src/rewriter/emoji_rewriter.h
class EmojiRewriter(
    private val dictionary: SerializedEmojiDictionary,
) : Rewriter {
    override fun capability(request: RewriterRequest): Int = request.emojiRewriterCapability

    override fun rewrite(request: RewriterRequest, segments: Segments): Boolean {
        if (!request.useEmojiConversion) {
            return false
        }
        var updated = false
        segments.conversionSegments().forEach { segment ->
            val key = toHalfWidthAscii(segment.key())
            val entries = if (key == EmojiKey) dictionary.allEmojiSorted() else dictionary.lookup(key)
            if (entries.isNotEmpty()) {
                val cost = segment.baseCandidate()?.cost ?: 0
                val candidates = entries.map { entry ->
                    Candidate().also { candidate ->
                        candidate.setKeyValue(key, entry.value)
                        candidate.lid = 0
                        candidate.rid = 0
                        candidate.cost = cost
                        candidate.description = if (entry.description.isEmpty()) EmojiDescription else "$EmojiDescription ${entry.description}"
                        candidate.attributes = candidate.attributes or
                            Attribute.NO_VARIANTS_EXPANSION or
                            Attribute.CONTEXT_SENSITIVE
                        candidate.category = Candidate.Category.SYMBOL
                    }
                }
                segment.insertCandidates(calculateInsertPosition(segment, DefaultInsertPosition), candidates)
                updated = true
            }
        }
        return updated
    }

    companion object {
        private const val EmojiKey: String = "えもじ"
        private const val EmojiDescription: String = "絵文字"
        private const val DefaultInsertPosition: Int = 6

        fun fromMozcDataManager(dataManager: MozcDataManager): EmojiRewriter =
            EmojiRewriter(
                SerializedEmojiDictionary(
                    dataManager.section("emoji_token"),
                    dataManager.section("emoji_string"),
                ),
            )
    }
}

data class SerializedEmojiEntry(
    val key: String,
    val value: String,
    val unicodeVersion: Int,
    val description: String,
)

class SerializedEmojiDictionary(
    tokenArray: ByteBuffer,
    stringArrayData: ByteBuffer,
) {
    private val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
    private val strings = SerializedStringArray.from(stringArrayData)
    private val tokenCount: Int

    init {
        tokenCount = verifyData(tokens.asReadOnlyBuffer(), strings)
    }

    fun lookup(key: String): List<SerializedEmojiEntry> {
        val first = lowerBound(key)
        val result = ArrayList<SerializedEmojiEntry>()
        var index = first
        while (index < tokenCount) {
            val entry = entryAt(index)
            if (entry.key != key) {
                break
            }
            if (entry.value.isNotEmpty()) {
                result += entry
            }
            index += 1
        }
        return result
    }

    fun allEmojiSorted(): List<SerializedEmojiEntry> =
        (0 until tokenCount)
            .map { entryAt(it) }
            .filter { it.value.isNotEmpty() }
            .sortedWith(compareBy<SerializedEmojiEntry> { it.value }.thenBy { it.description })

    fun valuesByUnicodeVersion(versions: IntRange): Map<Int, List<String>> =
        (0 until tokenCount)
            .map { entryAt(it) }
            .filter { it.value.isNotEmpty() && it.unicodeVersion in versions }
            .groupBy({ it.unicodeVersion }, { it.value })
            .mapValues { (_, values) -> values.distinct() }

    fun entryAt(index: Int): SerializedEmojiEntry {
        require(index in 0 until tokenCount) { "Emoji token index out of range: index=$index size=$tokenCount" }
        val offset = index * TokenByteLength
        return SerializedEmojiEntry(
            key = strings[tokens.getInt(offset)],
            value = strings[tokens.getInt(offset + 4)],
            unicodeVersion = tokens.getInt(offset + 8),
            description = strings[tokens.getInt(offset + 12)],
        )
    }

    private fun lowerBound(key: String): Int {
        var low = 0
        var high = tokenCount
        while (low < high) {
            val mid = (low + high) ushr 1
            if (keyAt(mid) < key) {
                low = mid + 1
            } else {
                high = mid
            }
        }
        return low
    }

    private fun keyAt(index: Int): String = strings[tokens.getInt(index * TokenByteLength)]

    companion object {
        private const val TokenByteLength: Int = 28

        fun verifyData(tokenArray: ByteBuffer, strings: SerializedStringArray): Int {
            val tokens = tokenArray.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(tokens.remaining() % TokenByteLength == 0) {
                "Emoji token array size must be divisible by $TokenByteLength: actual=${tokens.remaining()}"
            }
            val count = tokens.remaining() / TokenByteLength
            repeat(count) { index ->
                val offset = index * TokenByteLength
                repeat(4) { field ->
                    val stringIndex = tokens.getInt(offset + field * Int.SIZE_BYTES)
                    if (field != 2) {
                        require(stringIndex in 0 until strings.size()) {
                            "Emoji string index out of range: token=$index field=$field stringIndex=$stringIndex stringCount=${strings.size()}"
                        }
                    }
                }
                repeat(3) { unused ->
                    require(tokens.getInt(offset + 16 + unused * Int.SIZE_BYTES) == 0) {
                        "Emoji token unused field must be zero: token=$index field=$unused"
                    }
                }
            }
            return count
        }
    }
}

private fun toHalfWidthAscii(value: String): String =
    buildString {
        value.codePoints().forEachOrdered { codePoint ->
            appendCodePoint(if (codePoint in 0xff01..0xff5e) codePoint - 0xfee0 else codePoint)
        }
    }
