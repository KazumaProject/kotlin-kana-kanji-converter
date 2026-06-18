package mozc_runtime.dictionary

import mozc_runtime.data.SerializedStringArray
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Ported from mozc/src/dictionary/user_pos.cc
// Ported from mozc/src/dictionary/user_pos.h
class UserPos(
    tokenArrayData: ByteBuffer,
    stringArrayData: ByteBuffer,
) {
    private val tokenArray: List<TokenArrayEntry>
    private val strings: SerializedStringArray = SerializedStringArray.from(stringArrayData)
    private val tokenIndexesByPos: Map<String, List<Int>>
    private val posList: List<String>
    private val defaultIndex: Int

    init {
        val tokens = tokenArrayData.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(tokens.remaining() % TokenArrayEntryByteSize == 0) {
            "User POS token array size must be divisible by 8: size=${tokens.remaining()}"
        }
        tokenArray = List(tokens.remaining() / TokenArrayEntryByteSize) { index ->
            val offset = index * TokenArrayEntryByteSize
            TokenArrayEntry(
                posIndex = tokens.getUnsignedShort(offset),
                valueSuffixIndex = tokens.getUnsignedShort(offset + 2),
                keySuffixIndex = tokens.getUnsignedShort(offset + 4),
                conjugationId = tokens.getUnsignedShort(offset + 6),
            )
        }
        tokenArray.forEachIndexed { index, entry ->
            require(entry.posIndex in 0 until strings.size()) {
                "User POS token has invalid POS string index: token=$index posIndex=${entry.posIndex} strings=${strings.size()}"
            }
            require(entry.valueSuffixIndex in 0 until strings.size()) {
                "User POS token has invalid value suffix index: token=$index valueSuffixIndex=${entry.valueSuffixIndex} strings=${strings.size()}"
            }
            require(entry.keySuffixIndex in 0 until strings.size()) {
                "User POS token has invalid key suffix index: token=$index keySuffixIndex=${entry.keySuffixIndex} strings=${strings.size()}"
            }
        }

        val mutablePosList = ArrayList<String>()
        val seen = HashSet<Int>()
        var mutableDefaultIndex = 0
        tokenArray.forEach { token ->
            if (seen.add(token.posIndex)) {
                val pos = strings[token.posIndex]
                if (pos == DefaultPosName) {
                    mutableDefaultIndex = mutablePosList.size
                }
                mutablePosList += pos
            }
        }
        posList = mutablePosList.toList()
        defaultIndex = mutableDefaultIndex

        val grouped = LinkedHashMap<String, MutableList<Int>>()
        tokenArray.forEachIndexed { index, token ->
            grouped.getOrPut(strings[token.posIndex]) { ArrayList() } += index
        }
        tokenIndexesByPos = grouped.mapValues { it.value.toList() }
    }

    fun getPosList(): List<String> = posList

    fun getPosListDefaultIndex(): Int = defaultIndex

    fun getPosIds(pos: String): Int? =
        tokenIndexesByPos[pos]?.firstOrNull()?.let { tokenArray[it].conjugationId }

    fun isValidPos(pos: String): Boolean = getPosIds(pos) != null

    fun getTokens(
        key: String,
        value: String,
        pos: String,
        locale: String = "",
    ): List<Token> {
        if (key.isEmpty() || value.isEmpty()) {
            return listOf()
        }
        val indexes = tokenIndexesByPos[pos] ?: return listOf()
        val attributes = if (locale.isNotEmpty() && !locale.startsWith("ja")) {
            UserPosTokenAttribute.NonJaLocale.bit
        } else {
            0
        }
        val first = tokenArray[indexes.first()]
        if (indexes.size == 1) {
            return listOf(
                Token(
                    key = key,
                    value = value,
                    id = first.conjugationId,
                    attributes = attributes,
                    pos = pos,
                ),
            )
        }

        val baseKeySuffix = strings[first.keySuffixIndex]
        val baseValueSuffix = strings[first.valueSuffixIndex]
        val keyStem: String
        val valueStem: String
        if (
            baseKeySuffix.length < key.length &&
            baseValueSuffix.length < value.length &&
            key.endsWith(baseKeySuffix) &&
            value.endsWith(baseValueSuffix)
        ) {
            keyStem = key.dropLast(baseKeySuffix.length)
            valueStem = value.dropLast(baseValueSuffix.length)
        } else {
            keyStem = key
            valueStem = value
        }

        return indexes.map { index ->
            val entry = tokenArray[index]
            Token(
                key = keyStem + strings[entry.keySuffixIndex],
                value = valueStem + strings[entry.valueSuffixIndex],
                id = entry.conjugationId,
                attributes = attributes,
                pos = pos,
            )
        }
    }

    data class Token(
        val key: String,
        val value: String,
        val id: Int,
        val attributes: Int,
        val pos: String,
    ) {
        fun hasAttribute(attribute: UserPosTokenAttribute): Boolean =
            attributes and attribute.bit != 0
    }

    private data class TokenArrayEntry(
        val posIndex: Int,
        val valueSuffixIndex: Int,
        val keySuffixIndex: Int,
        val conjugationId: Int,
    )

    private companion object {
        const val TokenArrayEntryByteSize: Int = 8
        const val DefaultPosName: String = "名詞"
    }
}

enum class UserPosTokenAttribute(val bit: Int) {
    NonJaLocale(1),
}

private fun ByteBuffer.getUnsignedShort(offset: Int): Int =
    getShort(offset).toInt() and 0xffff
