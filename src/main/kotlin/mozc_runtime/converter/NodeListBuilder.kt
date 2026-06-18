package mozc_runtime.converter

import mozc_runtime.dictionary.Token

// Ported from mozc/src/converter/node_list_builder.h
open class BaseNodeListBuilder(
    private val allocator: NodeAllocator,
    private val limit: Int,
) {
    private val result = ArrayList<Node>(64)
    private var penalty: Int = 0

    fun onActualKey(numExpanded: Int) {
        penalty = getSpatialCostPenalty(numExpanded)
    }

    open fun onToken(token: Token): Boolean {
        val newNode = newNodeFromToken(token)
        appendToResult(newNode)
        return result.size <= limit
    }

    fun newNodeFromToken(token: Token): Node {
        val newNode = allocator.newNode()
        newNode.initFromToken(token)
        newNode.wcost += penalty
        if (penalty > 0) {
            newNode.attributes = newNode.attributes or Node.Attributes.KEY_EXPANDED
        }
        return newNode
    }

    fun appendToResult(node: Node) {
        result += node
    }

    fun result(): List<Node> = result.toList()

    companion object {
        private const val PerExpansionSpatialCostPenalty: Int = 2500

        fun getSpatialCostPenalty(numExpanded: Int): Int =
            numExpanded * PerExpansionSpatialCostPenalty
    }
}

// Ported from mozc/src/converter/node_list_builder.h
class NodeListBuilderForLookupPrefix(
    allocator: NodeAllocator,
    limit: Int,
    private val minKeyLength: Int,
) : BaseNodeListBuilder(allocator, limit) {
    fun acceptsKey(key: String): Boolean = key.utf8Size() >= minKeyLength
}
