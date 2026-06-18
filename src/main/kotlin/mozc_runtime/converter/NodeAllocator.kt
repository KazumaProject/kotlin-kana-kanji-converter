package mozc_runtime.converter

// Ported from mozc/src/converter/node_allocator.h
class NodeAllocator {
    private val nodes = ArrayList<Node>(1024)

    fun newNode(): Node {
        val node = Node()
        node.init()
        nodes += node
        return node
    }

    fun free() {
        nodes.clear()
    }
}
