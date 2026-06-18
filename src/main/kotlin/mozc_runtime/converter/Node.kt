package mozc_runtime.converter

import mozc_runtime.dictionary.Token

// Ported from mozc/src/converter/node.h
class Node {
    enum class NodeType {
        NOR_NODE,
        BOS_NODE,
        EOS_NODE,
        CON_NODE,
        HIS_NODE,
    }

    object Attributes {
        const val DEFAULT_ATTRIBUTE: Int = 0
        const val SYSTEM_DICTIONARY: Int = 1 shl 0
        const val USER_DICTIONARY: Int = 1 shl 1
        const val NO_VARIANTS_EXPANSION: Int = 1 shl 2
        const val STARTS_WITH_PARTICLE: Int = 1 shl 4
        const val SPELLING_CORRECTION: Int = 1 shl 5
        const val PARTIALLY_KEY_CONSUMED: Int = 1 shl 7
        const val SUFFIX_DICTIONARY: Int = 1 shl 8
        const val KEY_EXPANDED: Int = 1 shl 9
    }

    var prev: Node? = null
    var next: Node? = null
    var constrainedPrev: Node? = null
    var rid: Int = 0
    var lid: Int = 0
    var beginPos: Int = 0
    var endPos: Int = 0
    var wcost: Int = 0
    var cost: Int = 0
    var nodeType: NodeType = NodeType.NOR_NODE
    var attributes: Int = Attributes.DEFAULT_ATTRIBUTE
    var key: String = ""
    var value: String = ""

    fun init() {
        prev = null
        next = null
        constrainedPrev = null
        rid = 0
        lid = 0
        beginPos = 0
        endPos = 0
        wcost = 0
        cost = 0
        nodeType = NodeType.NOR_NODE
        attributes = Attributes.DEFAULT_ATTRIBUTE
        key = ""
        value = ""
    }

    fun initFromToken(token: Token) {
        init()
        rid = token.rid
        lid = token.lid
        wcost = token.cost
        key = token.key
        value = token.value
        if (token.attributes and Token.Attributes.SpellingCorrection != 0) {
            attributes = attributes or Attributes.SPELLING_CORRECTION
        }
        if (token.attributes and Token.Attributes.SuffixDictionary != 0) {
            attributes = attributes or Attributes.SUFFIX_DICTIONARY
        }
        if (token.attributes and Token.Attributes.UserDictionary != 0) {
            attributes = attributes or Attributes.USER_DICTIONARY or Attributes.NO_VARIANTS_EXPANSION
        }
    }
}
