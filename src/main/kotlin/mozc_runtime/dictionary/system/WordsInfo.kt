package mozc_runtime.dictionary.system

// Ported from mozc/src/dictionary/system/words_info.h
internal class TokenInfo {
    enum class PosType {
        Default,
        Frequent,
        SameAsPrevious,
    }

    enum class ValueType {
        Default,
        SameAsPrevious,
        AsIsHiragana,
        AsIsKatakana,
    }

    var token: MutableToken = MutableToken()
    var idInValueTrie: Int = -1
    var idInFrequentPosMap: Int = -1
    var posType: PosType = PosType.Default
    var valueType: ValueType = ValueType.Default

    fun clear() {
        idInValueTrie = -1
        idInFrequentPosMap = -1
        posType = PosType.Default
        valueType = ValueType.Default
    }
}

internal class MutableToken(
    var key: String = "",
    var value: String = "",
    var lid: Int = 0,
    var rid: Int = 0,
    var cost: Int = 0,
    var attributes: Int = 0,
)
