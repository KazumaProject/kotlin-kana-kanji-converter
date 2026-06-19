package mozc_runtime.converter

import mozc_runtime.dictionary.PosMatcher
import java.util.PriorityQueue
import kotlin.math.abs

enum class BoundaryCheckMode {
    STRICT,
    ONLY_MID,
    ONLY_EDGE,
}

enum class CandidateMode {
    FILL_INNER_SEGMENT_INFO,
    BUILD_FROM_ONLY_FIRST_INNER_SEGMENT,
}

data class NBestOptions(
    val boundaryCheckMode: BoundaryCheckMode = BoundaryCheckMode.STRICT,
    val candidateModes: Set<CandidateMode> = emptySet(),
)

data class GeneratedCandidate(
    val candidate: Candidate,
    val nodes: List<Node>,
    val topNodes: List<Node>,
)

// Ported from mozc/src/converter/nbest_generator.cc
// Ported from mozc/src/converter/nbest_generator.h
class NBestGenerator(
    private val segmenter: Segmenter,
    private val connector: Connector,
    private val posMatcher: PosMatcher,
    private val lattice: Lattice,
    private val filter: CandidateFilter = CandidateFilter(posMatcher),
) {
    private enum class BoundaryCheckResult {
        VALID,
        VALID_WEAK_CONNECTED,
        INVALID,
    }

    private data class QueueElement(
        val node: Node,
        val next: QueueElement?,
        val fx: Int,
        val gx: Int,
        val structureGx: Int,
        val wGx: Int,
        val order: Long,
    )

    private val agenda = PriorityQueue<QueueElement>(
        compareBy<QueueElement> { it.fx }.thenBy { it.order },
    )
    private val topNodes = ArrayList<Node>()
    private var beginNode: Node? = null
    private var endNode: Node? = null
    private var viterbiResultChecked = false
    private var options: NBestOptions = NBestOptions()
    private var nextOrder: Long = 0
    private var lastGeneratedNodes: List<Node> = emptyList()

    fun reset(beginNode: Node, endNode: Node, options: NBestOptions = NBestOptions()) {
        agenda.clear()
        topNodes.clear()
        filter.reset()
        viterbiResultChecked = false
        this.options = options
        this.beginNode = beginNode
        this.endNode = endNode
        nextOrder = 0
        lastGeneratedNodes = emptyList()

        lattice.beginNodes(endNode.beginPos).forEach { node ->
            if (node == endNode ||
                (
                    node.lid != endNode.lid &&
                        abs(node.cost - endNode.cost) <= CostDiff &&
                        node.prev != endNode.prev
                    )
            ) {
                agenda += createNewElement(node, null, node.cost, 0, 0, 0)
            }
        }
    }

    fun setCandidates(
        conversionOptions: ConversionOptions,
        originalKey: String,
        expandSize: Int,
        segment: Segment,
    ) {
        while (segment.candidatesSize() < expandSize) {
            val generated = next(conversionOptions, originalKey, applyFilter = true) ?: break
            val candidate = segment.pushBackCandidate()
            candidate.copyFrom(generated.candidate)
        }
    }

    fun collectCandidates(
        conversionOptions: ConversionOptions,
        originalKey: String,
        expandSize: Int,
        applyFilter: Boolean,
    ): List<GeneratedCandidate> {
        val result = ArrayList<GeneratedCandidate>()
        while (result.size < expandSize) {
            val generated = next(conversionOptions, originalKey, applyFilter) ?: break
            result += generated
        }
        return result
    }

    private fun next(
        conversionOptions: ConversionOptions,
        originalKey: String,
        applyFilter: Boolean,
    ): GeneratedCandidate? {
        if (!viterbiResultChecked) {
            viterbiResultChecked = true
            val candidate = Candidate()
            when (insertTopResult(conversionOptions, originalKey, candidate, applyFilter)) {
                CandidateFilter.ResultType.GOOD_CANDIDATE -> {
                    return GeneratedCandidate(copyCandidate(candidate), lastGeneratedNodes, topNodes.toList())
                }
                CandidateFilter.ResultType.STOP_ENUMERATION -> return null
                CandidateFilter.ResultType.BAD_CANDIDATE -> if (!applyFilter) {
                    return GeneratedCandidate(copyCandidate(candidate), lastGeneratedNodes, topNodes.toList())
                }
            }
        }

        var numTrials = 0
        while (agenda.isNotEmpty()) {
            val top = agenda.poll()
            val rnode = top.node
            if (numTrials++ > MaxTrial) {
                return null
            }

            val begin = beginNode ?: return null
            val end = endNode ?: return null
            if (rnode.endPos == begin.endPos) {
                val candidate = Candidate()
                val filterResult = makeCandidateFromElement(conversionOptions, originalKey, top, candidate, applyFilter)
                when (filterResult) {
                    CandidateFilter.ResultType.GOOD_CANDIDATE -> {
                        return GeneratedCandidate(copyCandidate(candidate), lastGeneratedNodes, topNodes.toList())
                    }
                    CandidateFilter.ResultType.STOP_ENUMERATION -> return null
                    CandidateFilter.ResultType.BAD_CANDIDATE -> if (!applyFilter) {
                        return GeneratedCandidate(copyCandidate(candidate), lastGeneratedNodes, topNodes.toList())
                    }
                }
                continue
            }

            var bestLeftElement: QueueElement? = null
            val isRightEdge = rnode.beginPos == end.beginPos
            val isLeftEdge = rnode.beginPos == begin.endPos
            val isEdge = isRightEdge || isLeftEdge

            lattice.endNodes(rnode.beginPos).forEach { lnode ->
                val validPosition = !(lnode.beginPos < begin.endPos && begin.endPos < lnode.endPos)
                if (!validPosition) {
                    return@forEach
                }
                val validCost = lnode.cost - begin.cost <= CostDiff
                if (isLeftEdge && !validCost) {
                    return@forEach
                }
                val canOmitSearch = lnode.rid == begin.rid && lnode != begin
                if (isLeftEdge && canOmitSearch) {
                    return@forEach
                }

                val boundaryResult = boundaryCheck(lnode, rnode, isEdge)
                if (boundaryResult == BoundaryCheckResult.INVALID) {
                    return@forEach
                }

                val transitionCost = getTransitionCost(lnode, rnode)
                var costDiff: Int
                var structureCostDiff: Int
                var wcostDiff: Int
                if (isRightEdge) {
                    costDiff = transitionCost + (rnode.cost - end.cost)
                    structureCostDiff = 0
                    wcostDiff = 0
                } else if (isLeftEdge) {
                    costDiff = transitionCost + rnode.wcost + (lnode.cost - begin.cost)
                    structureCostDiff = 0
                    wcostDiff = rnode.wcost
                } else {
                    costDiff = transitionCost + rnode.wcost
                    structureCostDiff = transitionCost
                    wcostDiff = transitionCost + rnode.wcost
                }

                if (boundaryResult == BoundaryCheckResult.VALID_WEAK_CONNECTED) {
                    costDiff += WeakConnectedPenalty
                    structureCostDiff += WeakConnectedPenalty / 2
                    wcostDiff += WeakConnectedPenalty / 2
                }

                val gx = costDiff + top.gx
                val fx = lnode.cost + gx
                val structureGx = structureCostDiff + top.structureGx
                val wGx = wcostDiff + top.wGx
                val element = createNewElement(lnode, top, fx, gx, structureGx, wGx)
                if (isLeftEdge) {
                    if (bestLeftElement == null || bestLeftElement!!.fx > fx) {
                        bestLeftElement = element
                    }
                } else {
                    agenda += element
                }
            }
            if (bestLeftElement != null) {
                agenda += bestLeftElement
            }
        }
        return null
    }

    private fun makeCandidateFromElement(
        conversionOptions: ConversionOptions,
        originalKey: String,
        element: QueueElement,
        candidate: Candidate,
        applyFilter: Boolean,
    ): CandidateFilter.ResultType {
        if (element.next == null) {
            return CandidateFilter.ResultType.BAD_CANDIDATE
        }
        val nodes = ArrayList<Node>()
        if (CandidateMode.BUILD_FROM_ONLY_FIRST_INNER_SEGMENT in options.candidateModes) {
            var elm = element.next
            while (elm != null) {
                val nextElement = elm.next ?: break
                nodes += elm.node
                if (isBetweenAlphabetKeys(elm.node, nextElement.node)) {
                    lastGeneratedNodes = nodes
                    return CandidateFilter.ResultType.BAD_CANDIDATE
                }
                if (segmenter.isBoundary(elm.node, nextElement.node, false)) {
                    break
                }
                elm = nextElement
            }
            if (elm == null) {
                lastGeneratedNodes = nodes
                return CandidateFilter.ResultType.BAD_CANDIDATE
            }
            val cost = element.gx - elm.gx
            val structureCost = element.structureGx - elm.structureGx
            val wcost = element.wGx - elm.wGx
            makeCandidate(candidate, cost, structureCost, wcost, nodes)
        } else {
            var elm = element.next
            while (elm?.next != null) {
                nodes += elm.node
                elm = elm.next
            }
            if (nodes.isEmpty()) {
                lastGeneratedNodes = nodes
                return CandidateFilter.ResultType.BAD_CANDIDATE
            }
            makeCandidate(candidate, element.gx, element.structureGx, element.wGx, nodes)
        }
        lastGeneratedNodes = nodes.toList()
        return if (applyFilter) {
            filter.filterCandidate(conversionOptions, originalKey, candidate, topNodes, nodes)
        } else {
            CandidateFilter.ResultType.GOOD_CANDIDATE
        }
    }

    private fun insertTopResult(
        conversionOptions: ConversionOptions,
        originalKey: String,
        candidate: Candidate,
        applyFilter: Boolean,
    ): CandidateFilter.ResultType {
        if (CandidateMode.BUILD_FROM_ONLY_FIRST_INNER_SEGMENT in options.candidateModes) {
            makePrefixCandidateFromBestPath(candidate)
        } else {
            if (!makeCandidateFromBestPath(candidate)) {
                return CandidateFilter.ResultType.STOP_ENUMERATION
            }
        }
        if (conversionOptions.requestType == RequestType.SUGGESTION) {
            candidate.attributes = candidate.attributes or Attribute.REALTIME_CONVERSION
        }
        lastGeneratedNodes = topNodes.toList()
        return if (applyFilter) {
            filter.filterCandidate(conversionOptions, originalKey, candidate, topNodes, topNodes)
        } else {
            CandidateFilter.ResultType.GOOD_CANDIDATE
        }
    }

    private fun makeCandidateFromBestPath(candidate: Candidate): Boolean {
        topNodes.clear()
        var totalWcost = 0
        val begin = beginNode ?: return false
        val end = endNode ?: return false
        var node = begin.next
        while (node != null && node != end) {
            if (node != begin.next) {
                if (isBetweenAlphabetKeys(topNodes.last(), node)) {
                    return false
                }
                totalWcost += node.wcost
            }
            topNodes += node
            node = node.next
        }
        if (topNodes.isEmpty()) {
            return false
        }
        val first = begin.next ?: return false
        val endPrev = end.prev ?: return false
        val cost = (end.cost - end.wcost) - begin.cost
        val structureCost = endPrev.cost - first.cost - totalWcost
        val wcost = endPrev.cost - first.cost + first.wcost
        makeCandidate(candidate, cost, structureCost, wcost, topNodes)
        return true
    }

    private fun makePrefixCandidateFromBestPath(candidate: Candidate) {
        topNodes.clear()
        var totalExtraWcost = 0
        val begin = beginNode ?: return
        val end = endNode ?: return
        var previousNode = begin
        var node = begin.next
        while (node != null && node != end) {
            if (previousNode != begin && segmenter.isBoundary(previousNode, node, false)) {
                break
            }
            topNodes += node
            if (node != begin.next) {
                totalExtraWcost += node.wcost
            }
            previousNode = node
            node = node.next
        }
        if (topNodes.isEmpty()) {
            return
        }
        val first = begin.next ?: return
        val last = topNodes.last()
        val cost = last.cost
        val structureCost = last.cost - first.cost - totalExtraWcost
        val wcost = last.cost - first.cost + first.wcost
        makeCandidate(candidate, cost, structureCost, wcost, topNodes)
    }

    private fun makeCandidate(
        candidate: Candidate,
        cost: Int,
        structureCost: Int,
        wcost: Int,
        nodes: List<Node>,
    ) {
        candidate.clear()
        candidate.lid = nodes.first().lid
        candidate.rid = nodes.last().rid
        candidate.cost = cost
        candidate.structureCost = structureCost
        candidate.wcost = wcost
        var isFunctional = false
        nodes.forEach { node ->
            if (!isFunctional && !posMatcher.isFunctional(node.lid)) {
                candidate.contentKey += node.key
                candidate.contentValue += node.value
            } else {
                isFunctional = true
            }
            candidate.key += node.key
            candidate.value += node.value
            if (node.constrainedPrev != null || node.next?.constrainedPrev == node) {
                candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
            }
            if (node.attributes and Node.Attributes.SPELLING_CORRECTION != 0) {
                candidate.attributes = candidate.attributes or Attribute.SPELLING_CORRECTION
            }
            if (node.attributes and Node.Attributes.NO_VARIANTS_EXPANSION != 0) {
                candidate.attributes = candidate.attributes or Attribute.NO_VARIANTS_EXPANSION
            }
            if (node.attributes and Node.Attributes.USER_DICTIONARY != 0) {
                candidate.attributes = candidate.attributes or Attribute.USER_DICTIONARY
            }
            if (node.attributes and Node.Attributes.SUFFIX_DICTIONARY != 0) {
                candidate.attributes = candidate.attributes or Attribute.SUFFIX_DICTIONARY
            }
            if (node.attributes and Node.Attributes.KEY_EXPANDED != 0) {
                candidate.attributes = candidate.attributes or Attribute.KEY_EXPANDED_IN_DICTIONARY
            }
        }
        if (candidate.contentKey.isEmpty() || candidate.contentValue.isEmpty()) {
            candidate.contentKey = candidate.key
            candidate.contentValue = candidate.value
        }
        candidate.innerSegments.clear()
        if (CandidateMode.FILL_INNER_SEGMENT_INFO in options.candidateModes) {
            fillInnerSegmentInfo(nodes, candidate)
        }
    }

    private fun fillInnerSegmentInfo(nodes: List<Node>, candidate: Candidate) {
        var keyLen = nodes[0].key.utf8Size()
        var valueLen = nodes[0].value.utf8Size()
        var contentKeyLen = keyLen
        var contentValueLen = valueLen
        var isContentBoundary = false
        if (posMatcher.isFunctional(nodes[0].rid)) {
            isContentBoundary = true
            contentKeyLen = 0
            contentValueLen = 0
        }

        val boundaries = ArrayList<InnerSegmentBoundary.Lengths>()
        for (index in 1 until nodes.size) {
            val lnode = nodes[index - 1]
            val rnode = nodes[index]
            if (segmenter.isBoundary(lnode, rnode, false)) {
                if (contentKeyLen == 0 || contentValueLen == 0) {
                    contentKeyLen = keyLen
                    contentValueLen = valueLen
                }
                boundaries += InnerSegmentBoundary.Lengths(keyLen, valueLen, contentKeyLen, contentValueLen)
                keyLen = 0
                valueLen = 0
                contentKeyLen = 0
                contentValueLen = 0
                isContentBoundary = false
            }
            keyLen += rnode.key.utf8Size()
            valueLen += rnode.value.utf8Size()
            if (isContentBoundary) {
                continue
            }
            if ((posMatcher.isContentNoun(lnode.rid) || posMatcher.isPronoun(lnode.rid)) &&
                posMatcher.isFunctional(rnode.lid)
            ) {
                isContentBoundary = true
            } else {
                contentKeyLen += rnode.key.utf8Size()
                contentValueLen += rnode.value.utf8Size()
            }
        }

        if (contentKeyLen == 0 || contentValueLen == 0) {
            contentKeyLen = keyLen
            contentValueLen = valueLen
        }
        boundaries += InnerSegmentBoundary.Lengths(keyLen, valueLen, contentKeyLen, contentValueLen)

        var keyOffset = 0
        var valueOffset = 0
        boundaries.forEach { boundary ->
            val key = candidate.key.utf8Substring(keyOffset, boundary.keyLength)
            val value = candidate.value.utf8Substring(valueOffset, boundary.valueLength)
            candidate.innerSegments += InnerSegment(
                key = key,
                value = value,
                contentKey = key.utf8Prefix(boundary.contentKeyLength),
                contentValue = value.utf8Prefix(boundary.contentValueLength),
            )
            keyOffset += boundary.keyLength
            valueOffset += boundary.valueLength
        }
    }

    private fun boundaryCheck(lnode: Node, rnode: Node, isEdge: Boolean): BoundaryCheckResult {
        if (rnode.nodeType == Node.NodeType.CON_NODE || lnode.nodeType == Node.NodeType.CON_NODE) {
            return BoundaryCheckResult.VALID
        }
        if (isBetweenAlphabetKeys(lnode, rnode)) {
            return BoundaryCheckResult.INVALID
        }
        return when (options.boundaryCheckMode) {
            BoundaryCheckMode.STRICT -> checkStrict(lnode, rnode, isEdge)
            BoundaryCheckMode.ONLY_MID -> checkOnlyMid(lnode, rnode, isEdge)
            BoundaryCheckMode.ONLY_EDGE -> checkOnlyEdge(lnode, rnode, isEdge)
        }
    }

    private fun checkStrict(lnode: Node, rnode: Node, isEdge: Boolean): BoundaryCheckResult {
        val isBoundary = lnode.nodeType == Node.NodeType.HIS_NODE || segmenter.isBoundary(lnode, rnode, false)
        return if (isEdge == isBoundary) BoundaryCheckResult.VALID else BoundaryCheckResult.INVALID
    }

    private fun checkOnlyMid(lnode: Node, rnode: Node, isEdge: Boolean): BoundaryCheckResult {
        val isBoundary = lnode.nodeType == Node.NodeType.HIS_NODE || segmenter.isBoundary(lnode, rnode, false)
        if (!isEdge && isBoundary) {
            return BoundaryCheckResult.INVALID
        }
        if (isEdge && !isBoundary) {
            return BoundaryCheckResult.VALID_WEAK_CONNECTED
        }
        return BoundaryCheckResult.VALID
    }

    private fun checkOnlyEdge(lnode: Node, rnode: Node, isEdge: Boolean): BoundaryCheckResult {
        val isBoundary = lnode.nodeType == Node.NodeType.HIS_NODE || segmenter.isBoundary(lnode, rnode, true)
        return if (isEdge == isBoundary) BoundaryCheckResult.VALID else BoundaryCheckResult.INVALID
    }

    private fun getTransitionCost(lnode: Node, rnode: Node): Int {
        val constrainedPrev = rnode.constrainedPrev
        if (constrainedPrev != null && lnode != constrainedPrev) {
            return InvalidPenaltyCost
        }
        return connector.cost(lnode.rid, rnode.lid)
    }

    private fun createNewElement(
        node: Node,
        next: QueueElement?,
        fx: Int,
        gx: Int,
        structureGx: Int,
        wGx: Int,
    ): QueueElement =
        QueueElement(node, next, fx, gx, structureGx, wGx, nextOrder++)

    private fun copyCandidate(source: Candidate): Candidate =
        Candidate().also { it.copyFrom(source) }

    private fun isBetweenAlphabetKeys(left: Node, right: Node): Boolean =
        left.key.isNotEmpty() &&
            right.key.isNotEmpty() &&
            left.key.last().isLetter() &&
            right.key.first().isLetter() &&
            left.key.last().code < 128 &&
            right.key.first().code < 128

    private companion object {
        const val CostDiff: Int = 3453
        const val WeakConnectedPenalty: Int = 3453
        const val MaxTrial: Int = 500
        const val InvalidPenaltyCost: Int = 100000
    }
}
