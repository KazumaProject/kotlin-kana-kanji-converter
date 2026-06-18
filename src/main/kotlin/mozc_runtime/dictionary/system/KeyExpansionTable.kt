package mozc_runtime.dictionary.system

// Ported from mozc/src/dictionary/system/key_expansion_table.h
class KeyExpansionTable private constructor(
    private val expansions: Map<Byte, ByteArray>,
) {
    fun expandKey(key: Byte): ByteArray = expansions[key] ?: byteArrayOf(key)

    companion object {
        fun default(): KeyExpansionTable = KeyExpansionTable(emptyMap())

        fun hiragana(codec: SystemDictionaryCodec): KeyExpansionTable {
            val map = LinkedHashMap<Byte, ByteArray>()
            HiraganaExpansionSource.forEach { source ->
                val encoded = codec.encodeKeyToBytes(source)
                if (encoded.size > 1) {
                    map[encoded[0]] = encoded.copyOfRange(1, encoded.size)
                }
            }
            return KeyExpansionTable(map)
        }

        private val HiraganaExpansionSource = listOf(
            "ああぁ", "いいぃ", "ううぅゔ", "ええぇ", "おおぉ", "かかが",
            "ききぎ", "くくぐ", "けけげ", "ここご", "ささざ", "ししじ",
            "すすず", "せせぜ", "そそぞ", "たただ", "ちちぢ", "つつっづ",
            "っっづ", "ててで", "ととど", "ははばぱ", "ひひびぴ", "ふふぶぷ",
            "へへべぺ", "ほほぼぽ", "ややゃ", "ゆゆゅ", "よよょ", "わわゎ",
        )
    }
}
