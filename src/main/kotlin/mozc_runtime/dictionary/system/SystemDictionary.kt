package mozc_runtime.dictionary.system

import mozc_data.MozcDataManager
import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.Token
import mozc_runtime.dictionary.file.DictionaryFile
import mozc_runtime.storage.louds.BitVectorBasedArray
import mozc_runtime.storage.louds.LoudsTrie
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.ArrayDeque
import java.util.TreeSet

// Ported from mozc/src/dictionary/system/system_dictionary.*
class SystemDictionary(
    dictionaryFile: DictionaryFile,
    private val codec: SystemDictionaryCodec = SystemDictionaryCodec(),
) : DictionaryInterface {
    private val keyTrie = LoudsTrie(dictionaryFile.requireSection(codec.sectionNameForKey()))
    private val valueTrie = LoudsTrie(dictionaryFile.requireSection(codec.sectionNameForValue()))
    private val tokenArray = BitVectorBasedArray(dictionaryFile.requireSection(codec.sectionNameForTokens()))
    private val frequentPos = readFrequentPos(dictionaryFile.requireSection(codec.sectionNameForPos()))
    private var reverseLookupCache: Map<Int, List<ReverseLookupResult>>? = null

    override fun hasKey(key: String): Boolean = keyTrie.hasKey(codec.encodeKeyToBytes(key))

    override fun hasValue(value: String): Boolean {
        if (valueTrie.hasKey(codec.encodeValueToBytes(value))) {
            return true
        }
        val key = value.katakanaToHiragana()
        val keyId = keyTrie.exactSearch(codec.encodeKeyToBytes(key))
        if (keyId < 0) {
            return false
        }
        var found = false
        decodeTokens(key, tokenArray.get(keyId)) { info ->
            if (info.token.value == value) {
                found = true
            }
        }
        return found
    }

    override fun lookupPrefix(key: String, callback: (Token) -> Unit) {
        val encodedKey = codec.encodeKeyToBytes(key)
        keyTrie.prefixSearch(encodedKey) { prefixLength, node ->
            val prefix = codec.decodeKey(encodedKey.copyOfRange(0, prefixLength))
            val keyId = keyTrie.keyIdOfTerminalNode(node)
            decodeTokens(prefix, tokenArray.get(keyId)) { info ->
                callback(info.token.toToken())
            }
        }
    }

    override fun lookupExact(key: String, callback: (Token) -> Unit) {
        val keyId = keyTrie.exactSearch(codec.encodeKeyToBytes(key))
        if (keyId < 0) {
            return
        }
        decodeTokens(key, tokenArray.get(keyId)) { info ->
            callback(info.token.toToken())
        }
    }

    override fun lookupPredictive(key: String, callback: (Token) -> Unit) {
        if (key.isEmpty()) {
            return
        }
        val encodedKey = codec.encodeKeyToBytes(key)
        require(encodedKey.size <= LoudsTrieMaxDepth) {
            "Encoded predictive key is longer than Mozc LOUDS trie depth: size=${encodedKey.size}"
        }
        val states = collectPredictiveNodesInBreadthFirstOrder(encodedKey, KeyExpansionTable.default(), LookupLimit)
        states.forEach { state ->
            val encodedActualKey = keyTrie.restoreKeyBytes(state.node)
            val suffix = encodedActualKey.copyOfRange(encodedKey.size, encodedActualKey.size)
            val decodedKey = key + codec.decodeKey(suffix)
            val actualKey = if (state.numExpanded > 0) codec.decodeKey(encodedActualKey) else decodedKey
            val keyId = keyTrie.keyIdOfTerminalNode(state.node)
            decodeTokens(actualKey, tokenArray.get(keyId)) { info ->
                val token = info.token.toToken()
                callback(if (token.key == actualKey) token.copy(key = decodedKey) else token)
            }
        }
    }

    override fun lookupReverse(value: String, callback: (Token) -> Unit) {
        val swappedCallback: (Token) -> Unit = { token ->
            callback(token.copy(key = token.value, value = token.key))
        }
        registerReverseLookupTokensForT13N(value, swappedCallback)
        registerReverseLookupTokensForValue(value, swappedCallback)
    }

    override fun lookupComment(key: String, value: String): String? = null

    override fun populateReverseLookupCache() {
        val allIds = TreeSet<Int>()
        for (id in 0 until valueTrieTerminalCount()) {
            allIds.add(id)
        }
        reverseLookupCache = scanTokens(allIds)
    }

    override fun clearReverseLookupCache() {
        reverseLookupCache = null
    }

    fun valueTrie(): LoudsTrie = valueTrie

    fun keyTrie(): LoudsTrie = keyTrie

    private fun collectPredictiveNodesInBreadthFirstOrder(
        encodedKey: ByteArray,
        table: KeyExpansionTable,
        limit: Int,
    ): List<PredictiveLookupSearchState> {
        val result = ArrayList<PredictiveLookupSearchState>(limit)
        val queue = ArrayDeque<PredictiveLookupSearchState>()
        queue.add(PredictiveLookupSearchState(LoudsTrie.Node(), 0, 0))
        while (!queue.isEmpty()) {
            var state = queue.removeFirst()
            if (state.keyPos < encodedKey.size) {
                val target = encodedKey[state.keyPos]
                val expanded = table.expandKey(target).toSet()
                var child = keyTrie.moveToFirstChild(state.node)
                while (keyTrie.isValidNode(child)) {
                    val label = keyTrie.edgeLabelToParentNode(child)
                    if (label in expanded) {
                        queue.add(
                            PredictiveLookupSearchState(
                                child,
                                state.keyPos + 1,
                                state.numExpanded + if (label == target) 0 else 1,
                            ),
                        )
                    }
                    child = keyTrie.moveToNextSibling(child)
                }
                continue
            }

            if (keyTrie.isTerminalNode(state.node)) {
                result += state
            }

            if (result.size > limit) {
                val maxKeyLength = state.keyPos
                while (!queue.isEmpty()) {
                    state = queue.removeFirst()
                    if (state.keyPos > maxKeyLength) {
                        break
                    }
                    if (keyTrie.isTerminalNode(state.node)) {
                        result += state
                    }
                }
                break
            }

            var child = keyTrie.moveToFirstChild(state.node)
            while (keyTrie.isValidNode(child)) {
                queue.add(PredictiveLookupSearchState(child, state.keyPos + 1, state.numExpanded))
                child = keyTrie.moveToNextSibling(child)
            }
        }
        return result
    }

    private fun registerReverseLookupTokensForT13N(value: String, callback: (Token) -> Unit) {
        val hiraganaValue = value.katakanaToHiragana()
        val encodedKey = codec.encodeKeyToBytes(hiraganaValue)
        runCallbackOnEachPrefix(hiraganaValue, encodedKey, callback) { info ->
            val token = info.token
            if ((token.attributes and Token.Attributes.SpellingCorrection) != 0) {
                return@runCallbackOnEachPrefix false
            }
            if (info.valueType != TokenInfo.ValueType.AsIsHiragana && info.valueType != TokenInfo.ValueType.AsIsKatakana) {
                if (token.key != token.value.katakanaToHiragana()) {
                    return@runCallbackOnEachPrefix false
                }
            }
            true
        }
    }

    private fun registerReverseLookupTokensForValue(value: String, callback: (Token) -> Unit) {
        val lookupKey = codec.encodeValueToBytes(value)
        val idSet = TreeSet<Int>()
        valueTrie.prefixSearch(lookupKey) { _, node ->
            idSet.add(valueTrie.keyIdOfTerminalNode(node))
        }
        val cached = reverseLookupCache
        val results = if (cached != null && idSet.all { cached.containsKey(it) }) cached else scanTokens(idSet)
        registerReverseLookupResults(idSet, results, callback)
    }

    private fun runCallbackOnEachPrefix(
        key: String,
        encodedKey: ByteArray,
        callback: (Token) -> Unit,
        tokenFilter: (TokenInfo) -> Boolean,
    ) {
        keyTrie.prefixSearch(encodedKey) { prefixLength, node ->
            val prefix = codec.decodeKey(encodedKey.copyOfRange(0, prefixLength))
            val keyId = keyTrie.keyIdOfTerminalNode(node)
            decodeTokens(prefix, tokenArray.get(keyId)) { info ->
                if (tokenFilter(info)) {
                    callback(info.token.toToken())
                }
            }
        }
    }

    private fun scanTokens(idSet: Set<Int>): Map<Int, List<ReverseLookupResult>> {
        if (idSet.isEmpty()) {
            return emptyMap()
        }
        val results = LinkedHashMap<Int, MutableList<ReverseLookupResult>>()
        val raw = tokenArray.rawData()
        var offset = 0
        var tokensOffset = 0
        var keyIndex = 0
        val termination = codec.tokensTerminationFlag()
        while (offset < raw.limit() && (raw.get(offset).toInt() and 0xff) != termination) {
            val read = codec.readTokenForReverseLookup(raw, offset)
            if (read.valueId >= 0 && read.valueId in idSet) {
                results.getOrPut(read.valueId) { ArrayList() } += ReverseLookupResult(
                    tokensOffset = tokensOffset,
                    idInKeyTrie = keyIndex,
                )
            }
            if (read.continues) {
                offset += read.readBytes
            } else {
                val tokensSize = maxOf(offset + read.readBytes - tokensOffset, MinTokenArrayBlobSize)
                tokensOffset += tokensSize
                offset = tokensOffset
                keyIndex += 1
            }
        }
        require(offset < raw.limit() && (raw.get(offset).toInt() and 0xff) == termination) {
            "System dictionary token array termination marker was not found"
        }
        return results
    }

    private fun registerReverseLookupResults(
        idSet: Set<Int>,
        results: Map<Int, List<ReverseLookupResult>>,
        callback: (Token) -> Unit,
    ) {
        idSet.forEach { valueId ->
            results[valueId].orEmpty().forEach { reverseResult ->
                val encodedKey = keyTrie.restoreKeyBytes(reverseResult.idInKeyTrie)
                val tokensKey = codec.decodeKey(encodedKey)
                decodeTokens(tokensKey, tokenArray.rawDataFrom(reverseResult.tokensOffset)) { info ->
                    val token = info.token
                    if ((token.attributes and Token.Attributes.SpellingCorrection) == 0 && info.idInValueTrie == valueId) {
                        callback(token.toToken())
                    }
                }
            }
        }
    }

    private fun decodeTokens(key: String, tokens: ByteBuffer, callback: (TokenInfo) -> Unit) {
        val iterator = TokenDecodeIterator(codec, valueTrie, frequentPos, key, tokens)
        while (iterator.hasNext()) {
            callback(iterator.next())
        }
    }

    private fun valueTrieTerminalCount(): Int {
        var count = 0
        val queue = ArrayDeque<LoudsTrie.Node>()
        queue.add(LoudsTrie.Node())
        while (!queue.isEmpty()) {
            val node = queue.removeFirst()
            if (valueTrie.isTerminalNode(node)) {
                count += 1
            }
            var child = valueTrie.moveToFirstChild(node)
            while (valueTrie.isValidNode(child)) {
                queue.add(child)
                child = valueTrie.moveToNextSibling(child)
            }
        }
        return count
    }

    private data class PredictiveLookupSearchState(
        val node: LoudsTrie.Node,
        val keyPos: Int,
        val numExpanded: Int,
    )

    private data class ReverseLookupResult(
        val tokensOffset: Int,
        val idInKeyTrie: Int,
    )

    companion object {
        private const val MinTokenArrayBlobSize: Int = 4
        private const val LookupLimit: Int = 64
        private const val LoudsTrieMaxDepth: Int = 256

        fun fromMozcDataManager(dataManager: MozcDataManager): SystemDictionary =
            SystemDictionary(DictionaryFile(dataManager.section("dict")))

        private fun readFrequentPos(buffer: ByteBuffer): IntArray {
            val data = buffer.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
            require(data.remaining() % Int.SIZE_BYTES == 0) {
                "Frequent POS section size must be divisible by 4: size=${data.remaining()}"
            }
            return IntArray(data.remaining() / Int.SIZE_BYTES) { index ->
                data.getInt(index * Int.SIZE_BYTES)
            }
        }
    }
}
