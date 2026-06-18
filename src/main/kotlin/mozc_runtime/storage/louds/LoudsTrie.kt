package mozc_runtime.storage.louds

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.ArrayDeque

// Ported from mozc/src/storage/louds/louds_trie.*
class LoudsTrie(image: ByteBuffer) {
    data class Node internal constructor(
        internal var edgeIndex: Int = 0,
        internal var nodeId: Int = 1,
    )

    private val louds: Louds
    private val terminalBitVector = SimpleSuccinctBitVectorIndex()
    private val edgeCharacters: ByteBuffer

    init {
        val buffer = image.asReadOnlyBuffer().slice().order(ByteOrder.LITTLE_ENDIAN)
        require(buffer.remaining() >= 16) { "LOUDS trie header is missing: size=${buffer.remaining()}" }
        val loudsSize = buffer.getInt()
        val terminalSize = buffer.getInt()
        val characterBits = buffer.getInt()
        val edgeCharacterSize = buffer.getInt()
        require(loudsSize >= 0) { "LOUDS trie size is negative: $loudsSize" }
        require(terminalSize >= 0) { "LOUDS terminal size is negative: $terminalSize" }
        require(characterBits == 8) { "LOUDS trie supports 8-bit edge labels only: actual=$characterBits" }
        require(edgeCharacterSize > 0) { "LOUDS edge character image must be non-empty" }
        require(buffer.remaining() >= loudsSize + terminalSize + edgeCharacterSize) {
            "LOUDS trie image is truncated: louds=$loudsSize terminal=$terminalSize edge=$edgeCharacterSize remaining=${buffer.remaining()}"
        }
        val loudsImage = buffer.slice().order(ByteOrder.LITTLE_ENDIAN)
        loudsImage.limit(loudsSize)
        buffer.position(buffer.position() + loudsSize)
        val terminalImage = buffer.slice().order(ByteOrder.LITTLE_ENDIAN)
        terminalImage.limit(terminalSize)
        buffer.position(buffer.position() + terminalSize)
        val edgeImage = buffer.slice().order(ByteOrder.LITTLE_ENDIAN)
        edgeImage.limit(edgeCharacterSize)
        louds = Louds(loudsImage)
        terminalBitVector.init(terminalImage, terminalSize)
        edgeCharacters = edgeImage.asReadOnlyBuffer()
    }

    fun isValidNode(node: Node): Boolean = louds.isValidNode(node)

    fun isTerminalNode(node: Node): Boolean = terminalBitVector.get(node.nodeId - 1) != 0

    fun edgeLabelToParentNode(node: Node): Byte = edgeCharacters.get(node.nodeId - 1)

    fun keyIdOfTerminalNode(node: Node): Int = terminalBitVector.rank1(node.nodeId - 1)

    fun terminalNodeFromKeyId(keyId: Int): Node {
        require(keyId >= 0) { "LOUDS key id is negative: $keyId" }
        val nodeId = terminalBitVector.select1(keyId + 1) + 1
        return louds.nodeFromNodeId(nodeId)
    }

    fun restoreKeyBytes(keyId: Int): ByteArray = restoreKeyBytes(terminalNodeFromKeyId(keyId))

    fun restoreKeyBytes(start: Node): ByteArray {
        var node = start.copy()
        val reversed = ByteArrayOutputStream()
        while (!louds.isRoot(node)) {
            reversed.write(edgeLabelToParentNode(node).toInt())
            node = louds.moveToParent(node)
        }
        return reversed.toByteArray().reversedArray()
    }

    fun moveToFirstChild(node: Node): Node = louds.moveToFirstChild(node)

    fun moveToNextSibling(node: Node): Node = Node(node.edgeIndex + 1, node.nodeId + 1)

    fun moveToChildByLabel(label: Byte, node: Node): Node? {
        var child = moveToFirstChild(node)
        while (isValidNode(child)) {
            if (edgeLabelToParentNode(child) == label) {
                return child
            }
            child = moveToNextSibling(child)
        }
        return null
    }

    fun traverse(key: ByteArray, start: Node = Node()): Node? {
        var node = start
        key.forEach { label ->
            node = moveToChildByLabel(label, node) ?: return null
        }
        return node
    }

    fun hasKey(key: ByteArray): Boolean = traverse(key)?.let(::isTerminalNode) == true

    fun exactSearch(key: ByteArray): Int = traverse(key)?.takeIf(::isTerminalNode)?.let(::keyIdOfTerminalNode) ?: -1

    fun prefixSearch(key: ByteArray, callback: (prefixLength: Int, node: Node) -> Unit) {
        var node = Node()
        key.indices.forEach { index ->
            node = moveToChildByLabel(key[index], node) ?: return
            if (isTerminalNode(node)) {
                callback(index + 1, node)
            }
        }
    }

    fun terminalNodesInBreadthFirstOrder(start: Node, limit: Int): List<Node> {
        require(limit >= 0) { "LOUDS traversal limit is negative: $limit" }
        val result = ArrayList<Node>()
        val queue = ArrayDeque<Node>()
        queue.add(start)
        while (!queue.isEmpty()) {
            val node = queue.removeFirst()
            if (isTerminalNode(node)) {
                result += node
                if (result.size >= limit) {
                    break
                }
            }
            var child = moveToFirstChild(node)
            while (isValidNode(child)) {
                queue.add(child)
                child = moveToNextSibling(child)
            }
        }
        return result
    }

    private class Louds(image: ByteBuffer) {
        private val index = SimpleSuccinctBitVectorIndex()

        init {
            index.init(image, image.remaining())
        }

        fun nodeFromNodeId(nodeId: Int): Node = Node(index.select1(nodeId), nodeId)

        fun isRoot(node: Node): Boolean = node.nodeId == 1

        fun moveToFirstChild(node: Node): Node {
            val edgeIndex = index.select0(node.nodeId) + 1
            return Node(edgeIndex, edgeIndex - node.nodeId + 1)
        }

        fun moveToParent(node: Node): Node {
            val nodeId = node.edgeIndex - node.nodeId + 1
            return Node(index.select1(nodeId), nodeId)
        }

        fun isValidNode(node: Node): Boolean =
            node.edgeIndex >= 0 &&
                node.edgeIndex < index.num0Bits() + index.num1Bits() &&
                index.get(node.edgeIndex) != 0
    }
}
