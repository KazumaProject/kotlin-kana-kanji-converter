package mozc_runtime.converter

// Ported from mozc/src/converter/lattice.h
// Ported from mozc/src/converter/lattice.cc
class Lattice {
    private val nodeAllocator = NodeAllocator()
    private var keyValue: String = ""
    private val beginNodeLists = ArrayList<MutableList<Node>>()
    private val endNodeLists = ArrayList<MutableList<Node>>()

    fun nodeAllocator(): NodeAllocator = nodeAllocator

    fun key(): String = keyValue

    fun keyByteSize(): Int = keyValue.utf8Size()

    fun setKey(key: String, bosId: Int = 0) {
        clear()
        keyValue = key
        val size = key.utf8Size() + 1
        repeat(size) {
            beginNodeLists += ArrayList<Node>(32)
            endNodeLists += ArrayList<Node>(32)
        }
        val bosNode = initBosNode(nodeAllocator.newNode(), 0, bosId)
        val eosNode = initEosNode(nodeAllocator.newNode(), key.utf8Size())
        endNodeLists[0] += bosNode
        beginNodeLists[key.utf8Size()] += eosNode
    }

    fun newNode(): Node = nodeAllocator.newNode()

    fun beginNodes(pos: Int): List<Node> {
        require(pos in beginNodeLists.indices) {
            "Lattice begin position is out of range: pos=$pos size=${beginNodeLists.size}"
        }
        return beginNodeLists[pos]
    }

    fun endNodes(pos: Int): List<Node> {
        require(pos in endNodeLists.indices) {
            "Lattice end position is out of range: pos=$pos size=${endNodeLists.size}"
        }
        return endNodeLists[pos]
    }

    fun bosNode(): Node {
        require(endNodeLists.isNotEmpty() && endNodeLists[0].size == 1) {
            "Lattice BOS node is missing"
        }
        return endNodeLists[0][0]
    }

    fun eosNode(): Node {
        val keySize = keyValue.utf8Size()
        require(beginNodeLists.isNotEmpty() && beginNodeLists[keySize].size == 1) {
            "Lattice EOS node is missing"
        }
        return beginNodeLists[keySize][0]
    }

    fun insert(pos: Int, node: Node) {
        require(pos in beginNodeLists.indices) {
            "Lattice insert position is out of range: pos=$pos size=${beginNodeLists.size}"
        }
        val endPos = minOf(node.key.utf8Size() + pos, keyValue.utf8Size())
        node.beginPos = pos
        node.endPos = endPos
        node.prev = null
        node.next = null
        node.cost = 0
        beginNodeLists[pos] += node
        endNodeLists[endPos] += node
    }

    fun insert(pos: Int, nodes: List<Node>) {
        nodes.forEach { insert(pos, it) }
    }

    fun hasLattice(): Boolean = beginNodeLists.isNotEmpty()

    fun debugString(): String {
        if (!hasLattice()) {
            return ""
        }
        val nodes = ArrayList<Node>()
        var node: Node? = eosNode()
        while (node != null) {
            nodes += node
            node = node.prev
        }
        val out = StringBuilder()
        var previous: Node? = null
        nodes.asReversed().forEach { current ->
            out.append("[con:")
            out.append(current.cost - (previous?.cost ?: 0) - current.wcost)
            out.append("][lid:")
            out.append(current.lid)
            out.append("]\"")
            out.append(current.value)
            out.append("\"[wcost:")
            out.append(current.wcost)
            out.append("][cost:")
            out.append(current.cost)
            out.append("][rid:")
            out.append(current.rid)
            out.append("]")
            previous = current
        }
        return out.toString()
    }

    private fun clear() {
        keyValue = ""
        beginNodeLists.clear()
        endNodeLists.clear()
        nodeAllocator.free()
    }

    private fun initBosNode(node: Node, position: Int, bosId: Int): Node {
        node.rid = bosId
        node.lid = 0
        node.key = ""
        node.value = "BOS"
        node.nodeType = Node.NodeType.BOS_NODE
        node.wcost = 0
        node.cost = 0
        node.beginPos = position
        node.endPos = position
        return node
    }

    private fun initEosNode(node: Node, position: Int): Node {
        node.rid = 0
        node.lid = 0
        node.key = ""
        node.value = "EOS"
        node.nodeType = Node.NodeType.EOS_NODE
        node.wcost = 0
        node.cost = 0
        node.beginPos = position
        node.endPos = position
        return node
    }
}

// Ported from mozc/src/converter/lattice.h
class ScopedLatticeNodeInserter(
    private val lattice: Lattice,
) {
    private val inserted = ArrayList<Pair<Int, Node>>()

    fun isInserted(): Boolean = inserted.isNotEmpty()

    fun insert(pos: Int, node: Node) {
        inserted += pos to node
    }

    fun flush() {
        inserted.forEach { (pos, node) -> lattice.insert(pos, node) }
        inserted.clear()
    }
}
