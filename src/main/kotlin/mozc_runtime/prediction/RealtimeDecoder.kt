package mozc_runtime.prediction

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.ConversionOptions
import mozc_runtime.converter.ImmutableConverter
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segments
import mozc_runtime.converter.charsLen

// Ported from mozc/src/prediction/realtime_decoder.h
// Ported from mozc/src/prediction/realtime_decoder.cc
class RealtimeDecoder(
    private val immutableConverter: ImmutableConverter,
) {
    fun decode(
        key: String,
        requestType: RequestType,
        maxCandidatesSize: Int,
        createPartialCandidates: Boolean = false,
        kanaModifierInsensitiveConversion: Boolean = false,
    ): List<Result> {
        if (key.isEmpty() || maxCandidatesSize == 0) {
            return listOf()
        }
        val segments = Segments()
        segments.initForConvert(key)
        val converted = immutableConverter.convert(
            ConversionOptions(
                requestType = requestType,
                maxConversionCandidatesSize = maxCandidatesSize,
                createPartialCandidates = createPartialCandidates,
                kanaModifierInsensitiveConversion = kanaModifierInsensitiveConversion,
            ),
            segments,
        )
        if (!converted || segments.conversionSegmentsSize() != 1) {
            return listOf()
        }
        val segment = segments.conversionSegment(0)
        return segment.candidates().map { candidate ->
            var attributes = PredictionTypes.Realtime or Attribute.NO_VARIANTS_EXPANSION or candidate.attributes
            var consumedKeySize = 0
            if (candidate.key.toByteArray(Charsets.UTF_8).size < segment.key().toByteArray(Charsets.UTF_8).size) {
                attributes = attributes or PredictionTypes.Prefix
                consumedKeySize = candidate.key.charsLen()
            }
            if (candidate.attributes and Attribute.KEY_EXPANDED_IN_DICTIONARY != 0) {
                attributes = attributes or PredictionTypes.KeyExpandedInDictionary
            }
            Result(
                key = candidate.key,
                value = candidate.value,
                contentKey = candidate.key,
                contentValue = candidate.value,
                attributes = attributes,
                wcost = candidate.wcost,
                cost = candidate.cost,
                structureCost = 0,
                lid = candidate.lid,
                rid = candidate.rid,
                consumedKeySize = consumedKeySize,
            )
        }
    }

    fun decodeSuffix(key: String, prefixRid: Int): Result? {
        if (key.isEmpty()) {
            return null
        }
        val segments = Segments()
        segments.initForConvert(key)
        val converted = immutableConverter.convert(
            ConversionOptions(
                requestType = RequestType.PREDICTION,
                maxConversionCandidatesSize = 1,
                kanaModifierInsensitiveConversion = false,
                bosId = prefixRid,
                disablePrefixPenalty = prefixRid != 0,
            ),
            segments,
        )
        if (!converted || segments.conversionSegmentsSize() != 1 || segments.conversionSegment(0).candidatesSize() == 0) {
            return null
        }
        val candidate = segments.conversionSegment(0).candidate(0)
        return Result(
            key = candidate.key,
            value = candidate.value,
            contentKey = candidate.key,
            contentValue = candidate.value,
            attributes = PredictionTypes.Realtime or candidate.attributes,
            wcost = candidate.wcost,
            cost = candidate.cost,
            structureCost = 0,
            lid = candidate.lid,
            rid = candidate.rid,
        )
    }
}
