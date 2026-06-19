package mozc_runtime.converter

import mozc_runtime.prediction.PredictionRequest
import mozc_runtime.prediction.Predictor
import mozc_runtime.prediction.Result
import mozc_runtime.rewriter.Rewriter
import mozc_runtime.rewriter.RewriterRequest
import kotlin.random.Random

// Ported from mozc/src/converter/converter.cc
// Ported from mozc/src/converter/converter.h
class Converter(
    private val immutableConverter: ImmutableConverter,
    private val predictor: Predictor,
    private val rewriter: Rewriter,
    private val historyReconstructor: HistoryReconstructor,
    private val reverseConverter: ReverseConverter,
) {
    fun startConversion(
        key: String,
        segments: Segments,
        context: String = "",
        maxCandidates: Int = DefaultMaxCandidates,
        options: ConversionOptions = ConversionOptions(
            requestType = RequestType.CONVERSION,
            maxConversionCandidatesSize = maxCandidates,
        ),
        rewriterRequest: RewriterRequest = RewriterRequest(
            key = key,
            requestType = RequestType.CONVERSION,
            rawText = key,
            compositionText = key,
        ),
    ): Boolean {
        if (key.isEmpty()) {
            return false
        }
        require(maxCandidates > 0) { "Conversion candidate size must be positive: $maxCandidates" }
        segments.clear()
        if (context.isNotEmpty()) {
            historyReconstructor.reconstructHistory(context, segments)
        }
        segments.initForConvert(key)
        immutableConverter.convert(
            options.copy(
                requestType = RequestType.CONVERSION,
                maxConversionCandidatesSize = maxCandidates,
            ),
            segments,
        )
        applyPostProcessing(rewriterRequest.copy(requestType = RequestType.CONVERSION), segments, maxCandidates)
        return isValidSegments(segments)
    }

    fun startPrediction(
        key: String,
        segments: Segments,
        context: String = "",
        requestType: RequestType = RequestType.PREDICTION,
        maxCandidates: Int = DefaultMaxCandidates,
        suggestionsSize: Int = DefaultSuggestionsSize,
        rewriterRequest: RewriterRequest = RewriterRequest(
            key = key,
            requestType = requestType,
            suggestionsSize = suggestionsSize,
            rawText = key,
            compositionText = key,
        ),
    ): Boolean {
        require(requestType == RequestType.PREDICTION || requestType == RequestType.SUGGESTION) {
            "Prediction path requires PREDICTION or SUGGESTION: $requestType"
        }
        require(maxCandidates > 0) { "Prediction candidate size must be positive: $maxCandidates" }
        segments.clear()
        if (context.isNotEmpty()) {
            historyReconstructor.reconstructHistory(context, segments)
        }
        segments.initForConvert(key)
        val history = makeHistoryResult(segments)
        appendPredictionResults(
            predictor.predict(
                PredictionRequest(
                    key = key,
                    requestType = requestType,
                    historyKey = history.key,
                    historyValue = history.value,
                    historyRid = history.rid,
                    historyCost = history.cost,
                    precedingText = context,
                    maxDictionaryPredictionCandidatesSize = maxCandidates,
                    suggestionsSize = suggestionsSize,
                ),
            ),
            segments.mutableConversionSegment(0),
        )
        applyPostProcessing(rewriterRequest.copy(requestType = requestType), segments, maxCandidates)
        return isValidSegments(segments)
    }

    fun startZeroQuery(
        context: String,
        segments: Segments,
        maxCandidates: Int = DefaultMaxCandidates,
        suggestionsSize: Int = DefaultSuggestionsSize,
        rewriterRequest: RewriterRequest = RewriterRequest(
            key = "",
            requestType = RequestType.PREDICTION,
            mixedConversion = true,
            zeroQuerySuggestion = true,
            suggestionsSize = suggestionsSize,
            rawText = "",
            compositionText = "",
        ),
    ): Boolean {
        if (context.isEmpty()) {
            return false
        }
        require(maxCandidates > 0) { "Zero query candidate size must be positive: $maxCandidates" }
        segments.clear()
        appendHistorySegment(segments, context, context, 0, 0)
        segments.initForConvert("")
        appendPredictionResults(
            predictor.predict(
                PredictionRequest(
                    key = "",
                    requestType = RequestType.PREDICTION,
                    mixedConversion = true,
                    zeroQuerySuggestion = true,
                    historyKey = context,
                    historyValue = context,
                    maxDictionaryPredictionCandidatesSize = PredictionSizeForMixedConversion,
                    maxUserHistoryPredictionCandidatesSize = 3,
                    maxUserHistoryPredictionCandidatesSizeForZeroQuery = 4,
                    suggestionsSize = suggestionsSize,
                ),
            ),
            segments.mutableConversionSegment(0),
        )
        applyPostProcessing(rewriterRequest, segments, maxCandidates)
        return isValidSegments(segments)
    }

    fun startReverseConversion(
        value: String,
        segments: Segments,
    ): Boolean = reverseConverter.reverseConvert(value, segments)

    fun reconstructHistory(segments: Segments, precedingText: String): Boolean {
        segments.clear()
        return historyReconstructor.reconstructHistory(precedingText, segments)
    }

    fun finishConversion(segments: Segments) {
        segments.all().forEach { segment ->
            if (segment.segmentType == Segment.SegmentType.SUBMITTED) {
                segment.segmentType = Segment.SegmentType.FIXED_VALUE
            }
            if (segment.candidatesSize() > 0) {
                val candidate = segment.mutableCandidate(0)
                if (candidate.contentKey.isEmpty()) {
                    candidate.contentKey = candidate.key
                }
                if (candidate.contentValue.isEmpty()) {
                    candidate.contentValue = candidate.value
                }
            }
        }
        segments.setRevertId(Random.nextLong(1, Long.MAX_VALUE))
        val startIndex = (segments.segmentsSize() - segments.maxHistorySegmentsSize()).coerceAtLeast(0)
        if (startIndex > 0) {
            segments.eraseSegments(0, startIndex)
        }
        segments.all().forEach { it.segmentType = Segment.SegmentType.HISTORY }
    }

    fun cancelConversion(segments: Segments) {
        segments.clearConversionSegments()
    }

    fun resetConversion(segments: Segments) {
        segments.clear()
    }

    fun commitContext(context: String): Boolean {
        if (context.isEmpty()) {
            return false
        }
        val segments = Segments()
        appendHistorySegment(segments, context, context, 0, 0)
        return segments.historySegmentsSize() == 1
    }

    private fun applyPostProcessing(
        request: RewriterRequest,
        segments: Segments,
        maxCandidates: Int,
    ) {
        rewriter.rewrite(request, segments)
        trimCandidates(segments, maxCandidates)
    }

    private fun appendPredictionResults(results: List<Result>, segment: Segment) {
        results.forEach { result ->
            val candidate = segment.addCandidate()
            candidate.key = result.key
            candidate.value = result.value
            if (result.innerSegments.isNotEmpty()) {
                candidate.contentKey = result.innerSegments.joinToString(separator = "") { it.contentKey }
                candidate.contentValue = result.innerSegments.joinToString(separator = "") { it.contentValue }
            } else {
                candidate.contentKey = result.contentKey
                candidate.contentValue = result.contentValue
            }
            candidate.description = result.description
            candidate.displayValue = result.displayValue
            candidate.lid = result.lid
            candidate.rid = result.rid
            candidate.wcost = result.wcost
            candidate.cost = result.cost
            candidate.structureCost = result.structureCost
            candidate.attributes = result.attributes
            candidate.consumedKeySize = result.consumedKeySize
            candidate.costBeforeRescoring = result.costBeforeRescoring
            candidate.innerSegments.clear()
            candidate.innerSegments += result.innerSegments
        }
    }

    private fun appendHistorySegment(
        segments: Segments,
        key: String,
        value: String,
        lid: Int,
        rid: Int,
    ) {
        val segment = segments.addSegment()
        segment.setKey(key)
        segment.segmentType = Segment.SegmentType.HISTORY
        val candidate = segment.addCandidate()
        candidate.key = key
        candidate.value = value
        candidate.contentKey = key
        candidate.contentValue = value
        candidate.lid = lid
        candidate.rid = rid
        candidate.attributes = Attribute.NO_LEARNING
    }

    private fun makeHistoryResult(segments: Segments): HistoryResult {
        if (segments.historySegmentsSize() == 0) {
            return HistoryResult()
        }
        val key = StringBuilder()
        val value = StringBuilder()
        var attributes = 0
        segments.historySegments().forEach { segment ->
            if (segment.candidatesSize() == 0) {
                return HistoryResult()
            }
            val candidate = segment.candidate(0)
            key.append(candidate.key)
            value.append(candidate.value)
            attributes = attributes or candidate.attributes
        }
        val first = segments.historySegment(0).candidate(0)
        val last = segments.historySegment(segments.historySegmentsSize() - 1).candidate(0)
        return HistoryResult(
            key = key.toString(),
            value = value.toString(),
            lid = first.lid,
            rid = last.rid,
            cost = last.cost,
            attributes = attributes,
        )
    }

    private fun trimCandidates(segments: Segments, maxCandidates: Int) {
        val limit = maxCandidates.coerceAtLeast(1)
        segments.conversionSegments().forEach { segment ->
            while (segment.candidatesSize() > limit) {
                segment.popBackCandidate()
            }
        }
    }

    private fun isValidSegments(segments: Segments): Boolean =
        segments.all().isNotEmpty() && segments.all().all { it.candidatesSize() > 0 }

    private data class HistoryResult(
        val key: String = "",
        val value: String = "",
        val lid: Int = 0,
        val rid: Int = 0,
        val cost: Int = 0,
        val attributes: Int = 0,
    )

    private companion object {
        const val DefaultMaxCandidates: Int = 20
        const val DefaultSuggestionsSize: Int = 3
        const val PredictionSizeForMixedConversion: Int = 200
    }
}
