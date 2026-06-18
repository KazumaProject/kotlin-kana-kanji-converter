package mozc_runtime.converter

import mozc_runtime.dictionary.DictionaryInterface
import mozc_runtime.dictionary.PosGroup
import mozc_runtime.dictionary.PosMatcher
import kotlin.math.abs

enum class RequestType {
    CONVERSION,
    REVERSE_CONVERSION,
    PREDICTION,
    SUGGESTION,
    PARTIAL_PREDICTION,
    PARTIAL_SUGGESTION,
}

data class ConversionOptions(
    val requestType: RequestType = RequestType.CONVERSION,
    val maxConversionCandidatesSize: Int = 200,
    val createPartialCandidates: Boolean = false,
    val kanaModifierInsensitiveConversion: Boolean = true,
    val inputMode: KeyCorrector.InputMode = KeyCorrector.InputMode.ROMAN,
    val useSpellingCorrection: Boolean = true,
    val useZipCodeConversion: Boolean = true,
    val useT13NConversion: Boolean = true,
    val incognitoMode: Boolean = false,
    val bosId: Int = 0,
    val disablePrefixPenalty: Boolean = false,
)

// Ported from mozc/src/converter/immutable_converter.h
// Ported from mozc/src/converter/immutable_converter.cc
class ImmutableConverter(
    private val dictionary: DictionaryInterface,
    private val connector: Connector,
    private val segmenter: Segmenter,
    private val posMatcher: PosMatcher,
    private val posGroup: PosGroup,
    private val suffixDictionary: DictionaryInterface? = null,
    private val userDictionary: DictionaryInterface? = null,
) {
    private val firstNameId: Int = posMatcher.getFirstNameId()
    private val lastNameId: Int = posMatcher.getLastNameId()
    private val numberId: Int = posMatcher.getNumberId()
    private val unknownId: Int = posMatcher.getUnknownId()
    private val lastToFirstNameTransitionCost: Int = connector.cost(lastNameId, firstNameId)

    fun convert(options: ConversionOptions, segments: Segments, lattice: Lattice = Lattice()): Boolean {
        val isPrediction = options.requestType == RequestType.PREDICTION ||
            options.requestType == RequestType.SUGGESTION
        if (!makeLattice(options, segments, lattice)) {
            return false
        }
        val pathReady = if (isPrediction) predictionViterbi(segments, lattice) else viterbi(segments, lattice)
        if (!pathReady) {
            return false
        }
        return makeSegments(options, lattice, segments)
    }

    fun makeLattice(options: ConversionOptions, segments: Segments, lattice: Lattice): Boolean {
        if (segments.segmentsSize() >= MaxSegmentsSize) {
            return false
        }

        normalizeHistorySegments(segments)
        val isReverse = options.requestType == RequestType.REVERSE_CONVERSION
        val isPrediction = options.requestType == RequestType.SUGGESTION ||
            options.requestType == RequestType.PREDICTION
        if (isReverse || isPrediction) {
            val conversionSegments = segments.conversionSegments()
            if (conversionSegments.size != 1 || conversionSegments.first().segmentType != Segment.SegmentType.FREE) {
                return false
            }
        }

        val conversionKey = buildString {
            segments.conversionSegments().forEach { segment ->
                if (segment.key().isEmpty()) {
                    return false
                }
                append(segment.key())
            }
        }
        val maxCharLength = if (isReverse) MaxCharLengthForReverseConversion else MaxCharLength
        if (conversionKey.isEmpty() || conversionKey.utf8Size() >= maxCharLength) {
            return false
        }

        var historyKey = buildString {
            segments.historySegments().forEach { segment ->
                if (segment.key().isEmpty()) {
                    return false
                }
                append(segment.key())
            }
        }
        if (historyKey.utf8Size() + conversionKey.utf8Size() >= maxCharLength) {
            segments.clearHistorySegments()
            historyKey = ""
        }

        lattice.setKey(historyKey + conversionKey, options.bosId)

        var isValidLattice = true
        if (!makeLatticeNodesForHistorySegments(segments, options, lattice) ||
            lattice.endNodes(historyKey.utf8Size()).isEmpty()
        ) {
            isValidLattice = false
        }
        if (isValidLattice) {
            makeLatticeNodesForConversionSegments(segments, options, historyKey, lattice)
        }
        if (!isValidLattice) {
            return false
        }
        if (lattice.endNodes(lattice.keyByteSize()).isEmpty()) {
            return false
        }

        applyPrefixSuffixPenalty(options, conversionKey, lattice)
        if (options.requestType == RequestType.CONVERSION) {
            resegment(segments, historyKey, conversionKey, lattice)
        }
        return true
    }

    fun makeLatticeNodesForHistorySegments(
        segments: Segments,
        options: ConversionOptions,
        lattice: Lattice,
    ): Boolean {
        val isReverse = options.requestType == RequestType.REVERSE_CONVERSION
        val historySize = segments.historySegmentsSize()
        var segmentsPos = 0
        for (index in 0 until historySize) {
            val segment = segments.segment(index)
            if (segment.segmentType != Segment.SegmentType.HISTORY &&
                segment.segmentType != Segment.SegmentType.SUBMITTED
            ) {
                return false
            }
            if (segment.key().isEmpty() || segment.candidatesSize() == 0) {
                return false
            }
            val candidate = segment.candidate(0)
            val rnode = lattice.newNode()
            rnode.lid = candidate.lid
            rnode.rid = candidate.rid
            rnode.wcost = 0
            rnode.value = candidate.value
            rnode.key = segment.key()
            rnode.nodeType = Node.NodeType.HIS_NODE
            lattice.insert(segmentsPos, rnode)

            if (index + 1 == historySize && candidate.rid != 0) {
                val eosRidNode = lattice.newNode()
                eosRidNode.lid = candidate.lid
                eosRidNode.rid = 0
                eosRidNode.wcost = 0
                eosRidNode.value = candidate.value
                eosRidNode.key = segment.key()
                eosRidNode.nodeType = Node.NodeType.HIS_NODE
                lattice.insert(segmentsPos, eosRidNode)
            }

            val isPrediction = options.requestType == RequestType.SUGGESTION ||
                options.requestType == RequestType.PREDICTION
            if (!isPrediction && index + 1 == historySize) {
                lookup(segmentsPos, options, isReverse, lattice).forEach { compoundNode ->
                    if (compoundNode.key.utf8Size() <= rnode.key.utf8Size() ||
                        compoundNode.value.utf8Size() <= rnode.value.utf8Size() ||
                        !compoundNode.key.startsWith(rnode.key) ||
                        !compoundNode.value.startsWith(rnode.value)
                    ) {
                        return@forEach
                    }
                    if (posGroup.getPosGroup(candidate.lid) != posGroup.getPosGroup(compoundNode.lid)) {
                        return@forEach
                    }
                    val newNode = lattice.newNode()
                    newNode.key = compoundNode.key.utf8Substring(
                        rnode.key.utf8Size(),
                        compoundNode.key.utf8Size() - rnode.key.utf8Size(),
                    )
                    newNode.value = compoundNode.value.utf8Substring(
                        rnode.value.utf8Size(),
                        compoundNode.value.utf8Size() - rnode.value.utf8Size(),
                    )
                    newNode.rid = compoundNode.rid
                    newNode.lid = compoundNode.lid
                    newNode.nodeType = Node.NodeType.NOR_NODE
                    newNode.attributes = newNode.attributes or Attribute.CONTEXT_SENSITIVE
                    newNode.wcost =
                        compoundNode.wcost * candidate.value.utf8Size() / compoundNode.value.utf8Size() -
                        connector.cost(candidate.rid, newNode.lid)
                    newNode.constrainedPrev = rnode
                    lattice.insert(segmentsPos + rnode.key.utf8Size(), newNode)
                }
            }
            segmentsPos += rnode.key.utf8Size()
        }
        return true
    }

    fun makeLatticeNodesForConversionSegments(
        segments: Segments,
        options: ConversionOptions,
        historyKey: String,
        lattice: Lattice,
    ) {
        val key = lattice.key()
        val isConversion = options.requestType == RequestType.CONVERSION
        val keyCorrector = if (isConversion && !segments.resized()) {
            KeyCorrector(key, options.inputMode, historyKey.utf8Size())
        } else {
            null
        }
        val isReverse = options.requestType == RequestType.REVERSE_CONVERSION
        for (pos in historyKey.utf8Size() until key.utf8Size()) {
            if (lattice.endNodes(pos).isEmpty()) {
                continue
            }
            val rnodes = lookup(pos, options, isReverse, lattice)
            if (historyKey.isNotEmpty() && pos == historyKey.utf8Size()) {
                rnodes.forEach { node ->
                    if (posMatcher.isAcceptableParticleAtBeginOfSegment(node.lid) && node.lid == node.rid) {
                        node.attributes = node.attributes or Node.Attributes.STARTS_WITH_PARTICLE
                    }
                }
            }
            lattice.insert(pos, rnodes)
            insertCorrectedNodes(pos, key, keyCorrector, dictionary, lattice)
        }
    }

    fun lookup(beginPos: Int, options: ConversionOptions, isReverse: Boolean, lattice: Lattice): List<Node> {
        val keySubstr = lattice.key().utf8Substring(minOf(beginPos, lattice.keyByteSize()))
        val builder = BaseNodeListBuilder(lattice.nodeAllocator(), MaxNodesSize)
        val callback: (mozc_runtime.dictionary.Token) -> Unit = { token ->
            builder.onToken(token)
        }
        if (isReverse) {
            dictionary.lookupReverse(keySubstr, callback)
        } else {
            dictionary.lookupPrefix(keySubstr, callback)
        }
        addCharacterTypeBasedNodes(keySubstr, lattice, builder)
        return builder.result()
    }

    fun addCharacterTypeBasedNodes(keySubstr: String, lattice: Lattice, builder: BaseNodeListBuilder) {
        val chars = keySubstr.utf8Chars()
        if (chars.isEmpty()) {
            return
        }
        val first = chars.first()
        val firstScriptType = getScriptType(first.codePoint)
        val firstFormType = getFormType(first.codePoint)
        val singleNode = lattice.newNode()
        if (firstScriptType == ScriptType.NUMBER) {
            singleNode.lid = numberId
            singleNode.rid = numberId
        } else {
            singleNode.lid = unknownId
            singleNode.rid = unknownId
        }
        singleNode.wcost = MaxCost
        singleNode.value = first.text
        singleNode.key = first.text
        singleNode.nodeType = Node.NodeType.NOR_NODE
        builder.appendToResult(singleNode)
        if (firstScriptType == ScriptType.NUMBER) {
            singleNode.wcost = DefaultNumberCost
            return
        }
        if (firstScriptType != ScriptType.ALPHABET && firstScriptType != ScriptType.KATAKANA) {
            return
        }

        var numChars = 1
        while (numChars < chars.size) {
            val next = chars[numChars]
            if (firstScriptType != getScriptType(next.codePoint) || firstFormType != getFormType(next.codePoint)) {
                break
            }
            numChars += 1
        }
        if (numChars > 1) {
            val groupedNode = lattice.newNode()
            groupedNode.lid = unknownId
            groupedNode.rid = unknownId
            groupedNode.wcost = MaxCost / 2
            val endByte = chars.take(numChars).sumOf { it.byteSize }
            groupedNode.value = keySubstr.utf8Prefix(endByte)
            groupedNode.key = groupedNode.value
            groupedNode.nodeType = Node.NodeType.NOR_NODE
            builder.appendToResult(groupedNode)
        }
    }

    fun insertCorrectedNodes(
        pos: Int,
        key: String,
        keyCorrector: KeyCorrector?,
        dictionary: DictionaryInterface,
        lattice: Lattice,
    ) {
        keyCorrector ?: return
        val prefix = keyCorrector.getCorrectedPrefix(pos)
        if (prefix.isEmpty()) {
            return
        }
        val builder = BaseNodeListBuilder(lattice.nodeAllocator(), MaxNodesSize)
        dictionary.lookupPrefix(prefix) { token ->
            val offset = keyCorrector.getOriginalOffset(pos, token.key.utf8Size())
            if (KeyCorrector.isValidPosition(offset) && offset != 0) {
                val node = builder.newNodeFromToken(token)
                node.key = key.utf8Substring(pos, offset)
                node.wcost += KeyCorrector.getCorrectedCostPenalty(node.key)
                builder.appendToResult(node)
            }
        }
        lattice.insert(pos, builder.result())
    }

    fun applyPrefixSuffixPenalty(options: ConversionOptions, conversionKey: String, lattice: Lattice) {
        val keySize = lattice.keyByteSize()
        val conversionSize = conversionKey.utf8Size()
        if (!options.disablePrefixPenalty) {
            lattice.beginNodes(keySize - conversionSize).forEach { node ->
                node.wcost += segmenter.getPrefixPenalty(node.lid)
            }
        }
        lattice.endNodes(keySize).forEach { node ->
            node.wcost += segmenter.getSuffixPenalty(node.rid)
        }
    }

    fun resegment(segments: Segments, historyKey: String, conversionKey: String, lattice: Lattice) {
        val begin = historyKey.utf8Size()
        val end = begin + conversionKey.utf8Size()
        for (pos in begin until end) {
            applyResegmentRules(pos, lattice)
        }
        var segmentsPos = 0
        segments.all().forEach { segment ->
            if (segment.segmentType == Segment.SegmentType.FIXED_VALUE && segment.candidatesSize() > 0) {
                val candidate = segment.candidate(0)
                val rnode = lattice.newNode()
                rnode.lid = candidate.lid
                rnode.rid = candidate.rid
                rnode.wcost = MinCost
                rnode.value = candidate.value
                rnode.key = segment.key()
                rnode.nodeType = Node.NodeType.CON_NODE
                lattice.insert(segmentsPos, rnode)
            }
            segmentsPos += segment.key().utf8Size()
        }
    }

    fun applyResegmentRules(pos: Int, lattice: Lattice) {
        if (resegmentArabicNumberAndSuffix(pos, lattice)) {
            return
        }
        if (resegmentPrefixAndArabicNumber(pos, lattice)) {
            return
        }
        resegmentPersonalName(pos, lattice)
    }

    fun resegmentArabicNumberAndSuffix(pos: Int, lattice: Lattice): Boolean {
        val inserter = ScopedLatticeNodeInserter(lattice)
        lattice.beginNodes(pos).toList().forEach { compoundNode ->
            if (compoundNode.value.isNotEmpty() &&
                compoundNode.key.isNotEmpty() &&
                posMatcher.isNumber(compoundNode.lid) &&
                !posMatcher.isNumber(compoundNode.rid) &&
                compoundNode.value.first().isAsciiDigit() &&
                compoundNode.key.first().isAsciiDigit()
            ) {
                val (numberValue, suffixValue) = decomposeNumberAndSuffix(compoundNode.value)
                val (numberKey, suffixKey) = decomposeNumberAndSuffix(compoundNode.key)
                if (suffixValue.isEmpty() || suffixKey.isEmpty() || numberValue != numberKey) {
                    return@forEach
                }
                val wcost = maxOf(compoundNode.wcost / 2 - 1, 0)
                val numberNode = lattice.newNode()
                numberNode.key = numberKey
                numberNode.value = numberValue
                numberNode.lid = compoundNode.lid
                numberNode.rid = 0
                numberNode.wcost = wcost
                numberNode.nodeType = Node.NodeType.NOR_NODE
                inserter.insert(pos, numberNode)

                val suffixNode = lattice.newNode()
                suffixNode.key = suffixKey
                suffixNode.value = suffixValue
                suffixNode.lid = 0
                suffixNode.rid = compoundNode.rid
                suffixNode.wcost = wcost
                suffixNode.nodeType = Node.NodeType.NOR_NODE
                suffixNode.constrainedPrev = numberNode
                inserter.insert(pos + numberNode.key.utf8Size(), suffixNode)
            }
        }
        val inserted = inserter.isInserted()
        inserter.flush()
        return inserted
    }

    fun resegmentPrefixAndArabicNumber(pos: Int, lattice: Lattice): Boolean {
        val inserter = ScopedLatticeNodeInserter(lattice)
        lattice.beginNodes(pos).toList().forEach { compoundNode ->
            if (compoundNode.value.utf8Size() > 1 &&
                compoundNode.key.utf8Size() > 1 &&
                !compoundNode.value.first().isAsciiDigit() &&
                !compoundNode.key.first().isAsciiDigit() &&
                compoundNode.value.last().isAsciiDigit() &&
                compoundNode.key.last().isAsciiDigit()
            ) {
                val (prefixValue, numberValue) = decomposePrefixAndNumber(compoundNode.value)
                val (prefixKey, numberKey) = decomposePrefixAndNumber(compoundNode.key)
                if (prefixValue.isEmpty() || prefixKey.isEmpty() || numberValue != numberKey) {
                    return@forEach
                }
                val wcost = maxOf(compoundNode.wcost / 2 - 1, 0)
                val prefixNode = lattice.newNode()
                prefixNode.key = prefixKey
                prefixNode.value = prefixValue
                prefixNode.lid = compoundNode.lid
                prefixNode.rid = 0
                prefixNode.wcost = wcost
                prefixNode.nodeType = Node.NodeType.NOR_NODE
                inserter.insert(pos, prefixNode)

                val numberNode = lattice.newNode()
                numberNode.key = numberKey
                numberNode.value = numberValue
                numberNode.lid = 0
                numberNode.rid = compoundNode.rid
                numberNode.wcost = wcost
                numberNode.nodeType = Node.NodeType.NOR_NODE
                numberNode.constrainedPrev = prefixNode
                inserter.insert(pos + prefixNode.key.utf8Size(), numberNode)
            }
        }
        val inserted = inserter.isInserted()
        inserter.flush()
        return inserted
    }

    fun resegmentPersonalName(pos: Int, lattice: Lattice): Boolean {
        val inserter = ScopedLatticeNodeInserter(lattice)
        lattice.beginNodes(pos).toList().forEach { compoundNode ->
            if (compoundNode.lid != lastNameId || compoundNode.rid != firstNameId) {
                return@forEach
            }
            val len = compoundNode.value.charsLen()
            if (len <= 2 || getScriptType(compoundNode.value) == ScriptType.KATAKANA) {
                return@forEach
            }
            var bestLastNameNode: Node? = null
            var bestFirstNameNode: Node? = null
            var bestCost = Int.MAX_VALUE
            lattice.beginNodes(pos).forEach { leftNode ->
                if (compoundNode.value.utf8Size() > leftNode.value.utf8Size() &&
                    compoundNode.key.utf8Size() > leftNode.key.utf8Size() &&
                    compoundNode.value.startsWith(leftNode.value)
                ) {
                    lattice.beginNodes(pos + leftNode.key.utf8Size()).forEach { rightNode ->
                        if (leftNode.value + rightNode.value == compoundNode.value &&
                            leftNode.value.utf8Size() + rightNode.value.utf8Size() == compoundNode.value.utf8Size() &&
                            segmenter.isBoundary(leftNode, rightNode, false)
                        ) {
                            val cost = leftNode.wcost + getCost(leftNode, rightNode)
                            if (cost < bestCost) {
                                bestLastNameNode = leftNode
                                bestFirstNameNode = rightNode
                                bestCost = cost
                            }
                        }
                    }
                }
            }
            val lastNode = bestLastNameNode ?: return@forEach
            val firstNode = bestFirstNameNode ?: return@forEach
            if (len >= 4 && lastNode.lid != lastNameId && firstNode.rid != firstNameId) {
                return@forEach
            }
            if (len == 3 && (lastNode.lid != lastNameId || firstNode.rid != firstNameId)) {
                return@forEach
            }
            val wcost = maxOf((compoundNode.wcost - lastToFirstNameTransitionCost) / 2 - 1, 0)
            val lastNameNode = lattice.newNode()
            lastNameNode.key = lastNode.key
            lastNameNode.value = lastNode.value
            lastNameNode.lid = compoundNode.lid
            lastNameNode.rid = lastNameId
            lastNameNode.wcost = wcost
            lastNameNode.nodeType = Node.NodeType.NOR_NODE
            inserter.insert(pos, lastNameNode)

            val firstNameNode = lattice.newNode()
            firstNameNode.key = firstNode.key
            firstNameNode.value = firstNode.value
            firstNameNode.lid = firstNameId
            firstNameNode.rid = compoundNode.rid
            firstNameNode.wcost = wcost
            firstNameNode.nodeType = Node.NodeType.NOR_NODE
            firstNameNode.constrainedPrev = lastNameNode
            inserter.insert(pos + lastNameNode.key.utf8Size(), firstNameNode)
        }
        val inserted = inserter.isInserted()
        inserter.flush()
        return inserted
    }

    fun viterbi(segments: Segments, lattice: Lattice): Boolean {
        val allSegments = segments.all()
        if (allSegments.isEmpty()) {
            return false
        }
        val bosNode = lattice.bosNode()
        var rightBoundary = allSegments[0].key().utf8Size()
        lattice.beginNodes(0).forEach { rnode ->
            if (rnode.endPos <= rightBoundary) {
                rnode.prev = bosNode
                rnode.cost = bosNode.cost + connector.cost(bosNode.rid, rnode.lid) + rnode.wcost
            }
        }

        var leftBoundary = 0
        rightBoundary = leftBoundary + allSegments[0].key().utf8Size()
        for (pos in leftBoundary + 1 until rightBoundary) {
            viterbiInternal(pos, rightBoundary, lattice)
        }
        leftBoundary = rightBoundary

        allSegments.drop(1).forEach { segment ->
            rightBoundary = leftBoundary + segment.key().utf8Size()
            for (pos in leftBoundary until rightBoundary) {
                viterbiInternal(pos, rightBoundary, lattice)
            }
            leftBoundary = rightBoundary
        }

        val eosNode = lattice.eosNode()
        var bestCost = VeryBigCost
        var bestNode: Node? = null
        lattice.endNodes(lattice.keyByteSize()).forEach { lnode ->
            if (lnode.prev != null) {
                val cost = lnode.cost + connector.cost(lnode.rid, eosNode.lid)
                if (cost < bestCost) {
                    bestCost = cost
                    bestNode = lnode
                }
            }
        }
        eosNode.prev = bestNode
        eosNode.cost = bestCost + eosNode.wcost

        var node: Node? = eosNode
        var previous: Node? = null
        while (node?.prev != null) {
            previous = node.prev
            previous?.next = node
            node = previous
        }
        return lattice.bosNode() == previous
    }

    fun predictionViterbi(segments: Segments, lattice: Lattice): Boolean {
        var historyLength = 0
        segments.historySegments().forEach { historyLength += it.key().utf8Size() }
        predictionViterbiInternal(0, historyLength, lattice)
        predictionViterbiInternal(historyLength, lattice.keyByteSize(), lattice)
        var node: Node? = lattice.eosNode()
        var previous: Node? = null
        while (node?.prev != null) {
            previous = node.prev
            previous?.next = node
            node = previous
        }
        return lattice.bosNode() == previous
    }

    fun predictionViterbiInternal(calcBeginPos: Int, calcEndPos: Int, lattice: Lattice) {
        val invalid: Pair<Int, Node?> = Int.MAX_VALUE to null
        for (pos in calcBeginPos..calcEndPos) {
            val leftBest = bestById(lattice.endNodes(pos), useRid = true)
            if (leftBest.isEmpty()) {
                continue
            }
            val rightIds = lattice.beginNodes(pos)
                .filter { it.endPos <= calcEndPos }
                .map { it.lid }
                .distinct()
            if (rightIds.isEmpty()) {
                continue
            }
            val rightBest = rightIds.associateWith { invalid }.toMutableMap()
            leftBest.forEach { (rid, pair) ->
                rightIds.forEach { lid ->
                    val cost = pair.first + connector.cost(rid, lid)
                    val current = rightBest.getValue(lid)
                    if (cost < current.first) {
                        rightBest[lid] = cost to pair.second
                    }
                }
            }
            lattice.beginNodes(pos).forEach { rnode ->
                if (rnode.endPos <= calcEndPos) {
                    val best = rightBest[rnode.lid]
                    if (best != null && best.second != null) {
                        rnode.cost = best.first + rnode.wcost
                        rnode.prev = best.second
                    }
                }
            }
        }
    }

    fun makeSegments(options: ConversionOptions, lattice: Lattice, segments: Segments): Boolean {
        val group = makeGroup(segments)
        return if (options.requestType == RequestType.CONVERSION ||
            options.requestType == RequestType.REVERSE_CONVERSION
        ) {
            insertCandidatesForConversion(options, lattice, group, segments)
            true
        } else {
            insertCandidatesForPrediction(options, lattice, group, segments)
            true
        }
    }

    fun insertCandidatesForConversion(
        options: ConversionOptions,
        lattice: Lattice,
        group: List<Int>,
        segments: Segments,
    ) {
        val maxCandidatesSize = if (options.requestType == RequestType.REVERSE_CONVERSION) {
            1
        } else {
            options.maxConversionCandidatesSize
        }
        val oldConversionSegmentsSize = segments.conversionSegmentsSize()
        val newSegments = buildBestPathSegments(options, lattice, group, segments, maxCandidatesSize, false)
        if (oldConversionSegmentsSize >= 0) {
            segments.replaceConversionSegments(newSegments)
        }
    }

    fun insertCandidatesForPrediction(
        options: ConversionOptions,
        lattice: Lattice,
        group: List<Int>,
        segments: Segments,
    ) {
        val newSegments = buildBestPathSegments(options, lattice, group, segments, options.maxConversionCandidatesSize, true)
        segments.replaceConversionSegments(newSegments)
    }

    fun insertCandidatesForRealtimeWithCandidateChecker(
        options: ConversionOptions,
        lattice: Lattice,
        group: List<Int>,
        segments: Segments,
    ) {
        insertCandidatesForPrediction(options, lattice, group, segments)
    }

    private fun buildBestPathSegments(
        options: ConversionOptions,
        lattice: Lattice,
        group: List<Int>,
        segments: Segments,
        maxCandidatesSize: Int,
        isSingleSegment: Boolean,
    ): List<Segment> {
        val result = ArrayList<Segment>()
        var prev = lattice.bosNode()
        var node = lattice.bosNode().next
        while (node != null && node.next != null && node.nodeType == Node.NodeType.HIS_NODE) {
            prev = node
            node = node.next
        }
        var beginPos: Int? = null
        while (node != null && node.next != null) {
            if (beginPos == null) {
                beginPos = node.beginPos
            }
            if (!isSegmentEndNode(options, segments, node, group, isSingleSegment)) {
                node = node.next
                continue
            }
            val segment = Segment()
            segment.setKey(lattice.key().utf8Substring(beginPos, node.endPos - beginPos))
            val oldSegmentIndex = group.getOrElse(node.beginPos) { segments.segmentsSize() - 1 }
            if (oldSegmentIndex in 0 until segments.segmentsSize()) {
                segment.segmentType = segments.segment(oldSegmentIndex).segmentType
            }
            val candidate = segment.addCandidate()
            makeCandidateFromBestPath(prev, node.next ?: lattice.eosNode(), candidate)
            if (options.requestType == RequestType.SUGGESTION) {
                candidate.attributes = candidate.attributes or Attribute.REALTIME_CONVERSION
            }
            if (node.nodeType == Node.NodeType.CON_NODE) {
                segment.segmentType = Segment.SegmentType.FIXED_VALUE
            }
            result += segment
            if (maxCandidatesSize > 1) {
                insertDummyCandidates(segment, maxCandidatesSize)
            }
            beginPos = null
            prev = node
            node = node.next
        }
        return result
    }

    private fun insertDummyCandidates(segment: Segment, expandSize: Int) {
        val lastCandidate = if (segment.candidatesSize() > 0) segment.candidate(segment.candidatesSize() - 1) else null
        if (segment.candidatesSize() == 0 ||
            (segment.candidatesSize() < expandSize && getScriptType(segment.key()) == ScriptType.HIRAGANA)
        ) {
            val candidate = segment.addCandidate()
            if (lastCandidate != null) {
                candidate.copyFrom(lastCandidate)
            }
            candidate.key = segment.key()
            candidate.value = segment.key()
            candidate.contentKey = segment.key()
            candidate.contentValue = segment.key()
            if (lastCandidate != null) {
                candidate.cost = lastCandidate.cost + 1
                candidate.wcost = lastCandidate.wcost + 1
                candidate.structureCost = lastCandidate.structureCost + 1
            }
            candidate.attributes = 0
            if (candidate.key.charsLen() <= 1) {
                candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
            }
        }
        val katakanaValue = hiraganaToKatakana(segment.key())
        if (segment.candidatesSize() > 0 &&
            segment.candidatesSize() < expandSize &&
            getScriptType(katakanaValue) == ScriptType.KATAKANA
        ) {
            val reference = segment.candidate(segment.candidatesSize() - 1)
            val candidate = segment.addCandidate()
            candidate.key = segment.key()
            candidate.value = katakanaValue
            candidate.contentKey = segment.key()
            candidate.contentValue = katakanaValue
            candidate.cost = reference.cost + 1
            candidate.wcost = reference.wcost + 1
            candidate.structureCost = reference.structureCost + 1
            candidate.lid = reference.lid
            candidate.rid = reference.rid
            if (candidate.key.charsLen() <= 1) {
                candidate.attributes = candidate.attributes or Attribute.CONTEXT_SENSITIVE
            }
        }
    }

    private fun isSegmentEndNode(
        options: ConversionOptions,
        segments: Segments,
        node: Node,
        group: List<Int>,
        isSingleSegment: Boolean,
    ): Boolean {
        val next = node.next ?: return true
        if (next.nodeType == Node.NodeType.EOS_NODE) {
            return true
        }
        if (options.requestType == RequestType.REVERSE_CONVERSION) {
            val thisNodeIsWhitespace = containsWhiteSpacesOnly(node.key)
            val nextNodeIsWhitespace = containsWhiteSpacesOnly(next.key)
            if (thisNodeIsWhitespace) {
                return !nextNodeIsWhitespace
            }
            if (nextNodeIsWhitespace) {
                return true
            }
        }
        val oldSegment = segments.segment(group[node.beginPos])
        if (group[node.beginPos] == group[next.beginPos] &&
            oldSegment.segmentType == Segment.SegmentType.FIXED_BOUNDARY
        ) {
            return false
        }
        if (group[node.beginPos] != group[next.beginPos]) {
            return true
        }
        if (node.nodeType == Node.NodeType.CON_NODE) {
            return true
        }
        return segmenter.isBoundary(node, next, isSingleSegment)
    }

    private fun makeCandidateFromBestPath(beginNode: Node, endNode: Node, candidate: Candidate): Boolean {
        val nodes = ArrayList<Node>()
        var totalWcost = 0
        var node = beginNode.next
        while (node != null && node != endNode) {
            if (node != beginNode.next) {
                val previous = nodes.last()
                if (isBetweenAlphabetKeys(previous, node)) {
                    return false
                }
                totalWcost += node.wcost
            }
            nodes += node
            node = node.next
        }
        if (nodes.isEmpty()) {
            return false
        }
        val first = beginNode.next ?: return false
        val endPrev = endNode.prev ?: return false
        val cost = (endNode.cost - endNode.wcost) - beginNode.cost
        val structureCost = endPrev.cost - first.cost - totalWcost
        val wcost = endPrev.cost - first.cost + first.wcost
        makeCandidate(candidate, cost, structureCost, wcost, nodes)
        return true
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
    }

    private fun makeGroup(segments: Segments): List<Int> {
        val group = ArrayList<Int>()
        for (index in 0 until segments.segmentsSize()) {
            repeat(segments.segment(index).key().utf8Size()) {
                group += index
            }
        }
        group += segments.segmentsSize()
        return group
    }

    private fun viterbiInternal(pos: Int, rightBoundary: Int, lattice: Lattice) {
        lattice.beginNodes(pos).forEach { rnode ->
            if (rnode.endPos > rightBoundary) {
                rnode.prev = null
                return@forEach
            }
            val constrainedPrev = rnode.constrainedPrev
            if (constrainedPrev != null) {
                if (constrainedPrev.prev == null) {
                    rnode.prev = null
                } else {
                    rnode.prev = constrainedPrev
                    rnode.cost = constrainedPrev.cost + rnode.wcost + connector.cost(constrainedPrev.rid, rnode.lid)
                }
                return@forEach
            }

            var bestCost = VeryBigCost
            var bestNode: Node? = null
            lattice.endNodes(pos).forEach { lnode ->
                if (lnode.prev != null) {
                    val cost = lnode.cost + connector.cost(lnode.rid, rnode.lid)
                    if (cost < bestCost) {
                        bestCost = cost
                        bestNode = lnode
                    }
                }
            }
            rnode.prev = bestNode
            rnode.cost = bestCost + rnode.wcost
        }
    }

    private fun getCost(leftNode: Node, rightNode: Node): Int {
        val constrainedPrev = rightNode.constrainedPrev
        if (constrainedPrev != null && leftNode != constrainedPrev) {
            return InvalidPenaltyCost
        }
        return connector.cost(leftNode.rid, rightNode.lid) + rightNode.wcost
    }

    private fun bestById(nodes: List<Node>, useRid: Boolean): Map<Int, Pair<Int, Node?>> {
        val result = LinkedHashMap<Int, Pair<Int, Node?>>()
        nodes.forEach { node ->
            val id = if (useRid) node.rid else node.lid
            val current = result[id]
            if (current == null || node.cost < current.first) {
                result[id] = node.cost to node
            }
        }
        return result
    }

    private fun normalizeHistorySegments(segments: Segments) {
        segments.historySegments().forEach { segment ->
            if (segment.candidatesSize() == 0) {
                return@forEach
            }
            val candidate = segment.mutableCandidate(0)
            val historyKey = if (candidate.key.utf8Size() > segment.key().utf8Size()) candidate.key else segment.key()
            val key = fullWidthAsciiToHalfWidthAscii(historyKey)
            candidate.value = fullWidthAsciiToHalfWidthAscii(candidate.value)
            candidate.contentValue = fullWidthAsciiToHalfWidthAscii(candidate.contentValue)
            candidate.contentKey = fullWidthAsciiToHalfWidthAscii(candidate.contentKey)
            candidate.key = key
            segment.setKey(key)
            if (
                key.utf8Size() > 1 &&
                key == candidate.value &&
                key == candidate.contentValue &&
                key == candidate.key &&
                key == candidate.contentKey &&
                getScriptType(key) == ScriptType.NUMBER &&
                key.last().isAsciiDigit()
            ) {
                val lastDigit = key.last().toString()
                segment.setKey(lastDigit)
                candidate.value = lastDigit
                candidate.contentValue = lastDigit
                candidate.contentKey = lastDigit
                candidate.key = lastDigit
            }
        }
    }

    private fun containsWhiteSpacesOnly(value: String): Boolean {
        if (value.isEmpty()) {
            return false
        }
        var result = true
        value.codePoints().forEachOrdered { codePoint ->
            if (codePoint != 0x09 && codePoint != 0x20 && codePoint != 0x3000) {
                result = false
            }
        }
        return result
    }

    private fun decomposeNumberAndSuffix(input: String): Pair<String, String> {
        val index = input.indexOfFirst { !it.isAsciiDigit() }
        return if (index < 0) input to "" else input.substring(0, index) to input.substring(index)
    }

    private fun decomposePrefixAndNumber(input: String): Pair<String, String> {
        val index = input.indexOfLast { !it.isAsciiDigit() }
        return if (index < 0) "" to input else input.substring(0, index + 1) to input.substring(index + 1)
    }

    private fun isBetweenAlphabetKeys(left: Node, right: Node): Boolean =
        left.key.isNotEmpty() &&
            right.key.isNotEmpty() &&
            left.key.last().isLetter() &&
            right.key.first().isLetter() &&
            left.key.last().code < 128 &&
            right.key.first().code < 128

    private fun Char.isAsciiDigit(): Boolean = this in '0'..'9'

    private companion object {
        const val MaxSegmentsSize: Int = 256
        const val MaxCharLength: Int = 1024
        const val MaxCharLengthForReverseConversion: Int = 600
        const val MaxCost: Int = 32767
        const val MinCost: Int = -32767
        const val DefaultNumberCost: Int = 3000
        const val MaxNodesSize: Int = 8192
        const val VeryBigCost: Int = Int.MAX_VALUE shr 2
        const val InvalidPenaltyCost: Int = 100000
    }
}
