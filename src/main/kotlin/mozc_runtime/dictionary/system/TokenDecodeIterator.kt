package mozc_runtime.dictionary.system

import mozc_runtime.dictionary.Token
import mozc_runtime.storage.louds.LoudsTrie
import java.nio.ByteBuffer

// Ported from mozc/src/dictionary/system/token_decode_iterator.h
internal class TokenDecodeIterator(
    private val codec: SystemDictionaryCodec,
    private val valueTrie: LoudsTrie,
    private val frequentPos: IntArray,
    key: String,
    tokens: ByteBuffer,
) : Iterator<TokenInfo> {
    private enum class State {
        HasNext,
        LastToken,
        Done,
    }

    private val buffer = tokens.asReadOnlyBuffer()
    private val mutableToken = MutableToken(key = key)
    private val tokenInfo = TokenInfo()
    private var state = State.HasNext
    private var offset = 0
    private var current: TokenInfo? = null
    private var keyKatakana: String = ""

    init {
        tokenInfo.token = mutableToken
        readNextToken()
    }

    override fun hasNext(): Boolean = state != State.Done && current != null

    override fun next(): TokenInfo {
        val result = current ?: error("TokenDecodeIterator has no current token")
        if (state == State.LastToken) {
            state = State.Done
            current = null
        } else {
            readNextToken()
        }
        return result
    }

    private fun readNextToken() {
        val previousValueTrieId = tokenInfo.idInValueTrie
        tokenInfo.clear()
        tokenInfo.token = mutableToken
        mutableToken.attributes = Token.Attributes.None
        val decoded = codec.decodeToken(buffer, offset, tokenInfo)
        if (!decoded.continues) {
            state = State.LastToken
        }
        offset += decoded.readBytes
        when (tokenInfo.valueType) {
            TokenInfo.ValueType.Default -> {
                mutableToken.value = codec.decodeValue(valueTrie.restoreKeyBytes(tokenInfo.idInValueTrie))
            }
            TokenInfo.ValueType.SameAsPrevious -> {
                require(previousValueTrieId >= 0) { "Token references previous value before any normal value" }
                tokenInfo.idInValueTrie = previousValueTrieId
            }
            TokenInfo.ValueType.AsIsHiragana -> {
                mutableToken.value = mutableToken.key
            }
            TokenInfo.ValueType.AsIsKatakana -> {
                if (mutableToken.key.isNotEmpty() && keyKatakana.isEmpty()) {
                    keyKatakana = mutableToken.key.hiraganaToKatakana()
                }
                mutableToken.value = keyKatakana
            }
        }
        if (tokenInfo.posType == TokenInfo.PosType.Frequent) {
            require(tokenInfo.idInFrequentPosMap in frequentPos.indices) {
                "Frequent POS index is out of range: index=${tokenInfo.idInFrequentPosMap} size=${frequentPos.size}"
            }
            val pos = frequentPos[tokenInfo.idInFrequentPosMap]
            mutableToken.lid = pos ushr 16
            mutableToken.rid = pos and 0xffff
        }
        val snapshot = TokenInfo()
        snapshot.idInValueTrie = tokenInfo.idInValueTrie
        snapshot.idInFrequentPosMap = tokenInfo.idInFrequentPosMap
        snapshot.posType = tokenInfo.posType
        snapshot.valueType = tokenInfo.valueType
        snapshot.token = MutableToken(
            key = mutableToken.key,
            value = mutableToken.value,
            lid = mutableToken.lid,
            rid = mutableToken.rid,
            cost = mutableToken.cost,
            attributes = mutableToken.attributes,
        )
        current = snapshot
    }
}

internal fun MutableToken.toToken(): Token =
    Token(
        key = key,
        value = value,
        lid = lid,
        rid = rid,
        cost = cost,
        attributes = attributes,
    )

internal fun String.hiraganaToKatakana(): String {
    val out = StringBuilder()
    codePoints().forEachOrdered { codePoint ->
        val converted = if (codePoint in 0x3041..0x3096) codePoint + 0x60 else codePoint
        out.appendCodePoint(converted)
    }
    return out.toString()
}

internal fun String.katakanaToHiragana(): String {
    val out = StringBuilder()
    codePoints().forEachOrdered { codePoint ->
        val converted = if (codePoint in 0x30a1..0x30f6) codePoint - 0x60 else codePoint
        out.appendCodePoint(converted)
    }
    return out.toString()
}
