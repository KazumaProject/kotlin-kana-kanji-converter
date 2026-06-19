package mozc_runtime.engine

import mozc_runtime.converter.Attribute
import mozc_runtime.converter.Candidate
import mozc_runtime.converter.ConversionOptions
import mozc_runtime.converter.InnerSegment
import mozc_runtime.converter.RequestType
import mozc_runtime.converter.Segment
import mozc_runtime.converter.Segments
import mozc_runtime.prediction.PredictionTypes
import mozc_runtime.rewriter.RewriterRequest

// Ported from mozc/src/converter/converter.cc
// Ported from mozc/src/prediction/predictor.cc
// Ported from mozc/src/rewriter/rewriter.cc
class MozcKotlinEngineConverter(
    private val modules: MozcModules,
    private val config: MozcEngineConfig,
) {
    fun evaluate(request: MozcConversionRequest): MozcEngineResult {
        val maxCandidates = if (request.maxCandidates > 0) request.maxCandidates else config.maxCandidates
        val suggestionsSize = request.suggestionsSize.coerceIn(1, 9)
        val segments = Segments()
        val success = when (request.requestType) {
            MozcRequestType.CONVERSION -> modules.converter.startConversion(
                key = request.input,
                segments = segments,
                context = request.context,
                maxCandidates = maxCandidates,
                options = conversionOptions(request, maxCandidates),
                rewriterRequest = rewriterRequest(request, RequestType.CONVERSION, suggestionsSize),
            )
            MozcRequestType.PREDICTION -> modules.converter.startPrediction(
                key = request.input,
                segments = segments,
                context = request.context,
                requestType = RequestType.PREDICTION,
                maxCandidates = maxCandidates,
                suggestionsSize = suggestionsSize,
                rewriterRequest = rewriterRequest(request, RequestType.PREDICTION, suggestionsSize),
            )
            MozcRequestType.SUGGESTION -> modules.converter.startPrediction(
                key = request.input,
                segments = segments,
                context = request.context,
                requestType = RequestType.SUGGESTION,
                maxCandidates = maxCandidates,
                suggestionsSize = suggestionsSize,
                rewriterRequest = rewriterRequest(request, RequestType.SUGGESTION, suggestionsSize),
            )
            MozcRequestType.ZERO_QUERY -> {
                val context = request.context.ifEmpty { request.input }
                modules.converter.startZeroQuery(
                    context = context,
                    segments = segments,
                    maxCandidates = maxCandidates,
                    suggestionsSize = suggestionsSize,
                    rewriterRequest = rewriterRequest(
                        request.copy(input = "", context = context, mixedConversion = true, zeroQuerySuggestion = true),
                        RequestType.PREDICTION,
                        suggestionsSize,
                    ),
                )
            }
            MozcRequestType.REVERSE -> modules.converter.startReverseConversion(request.input, segments)
        }
        check(success) {
            "Mozc engine evaluation failed: requestType=${request.requestType} input=${request.input} context=${request.context}"
        }
        return MozcEngineResult(
            requestType = request.requestType,
            input = request.input,
            context = request.context,
            segments = segments.conversionSegments().mapIndexed { index, segment -> toEngineSegment(index, segment) },
            dataVersion = modules.dataManager.version(),
        )
    }

    private fun conversionOptions(request: MozcConversionRequest, maxCandidates: Int): ConversionOptions =
        ConversionOptions(
            requestType = RequestType.CONVERSION,
            maxConversionCandidatesSize = maxCandidates,
            kanaModifierInsensitiveConversion = request.kanaModifierInsensitiveConversion &&
                config.useKanaModifierInsensitiveConversion,
            useSpellingCorrection = request.useSpellingCorrection,
            useZipCodeConversion = request.useZipCodeConversion,
            useT13NConversion = request.useT13NConversion,
            incognitoMode = request.incognitoMode,
        )

    private fun rewriterRequest(
        request: MozcConversionRequest,
        requestType: RequestType,
        suggestionsSize: Int,
    ): RewriterRequest =
        RewriterRequest(
            key = request.input,
            requestType = requestType,
            mixedConversion = request.mixedConversion,
            useSingleKanjiConversion = request.useSingleKanjiConversion,
            useSymbolConversion = request.useSymbolConversion,
            useNumberConversion = request.useNumberConversion,
            useEmoticonConversion = request.useEmoticonConversion,
            useEmojiConversion = request.useEmojiConversion,
            useZipCodeConversion = request.useZipCodeConversion,
            useT13nConversion = request.useT13NConversion,
            useSpellingCorrection = request.useSpellingCorrection,
            incognitoMode = request.incognitoMode,
            suggestionsSize = suggestionsSize,
            enableA11yDescription = request.enableA11yDescription || config.enableA11yDescription,
            zeroQuerySuggestion = request.zeroQuerySuggestion,
            rawText = request.input,
            compositionText = request.input,
        )

    private fun toEngineSegment(index: Int, segment: Segment): MozcEngineSegment =
        MozcEngineSegment(
            index = index,
            key = segment.key(),
            candidates = segment.candidates().mapIndexed { candidateIndex, candidate ->
                toEngineCandidate(candidateIndex, candidate)
            },
        )

    private fun toEngineCandidate(index: Int, candidate: Candidate): MozcEngineCandidate {
        val predictionBits = candidate.attributes and PredictionTypes.MaskForTesting
        val converterBits = candidate.attributes and PredictionTypes.MaskForTesting.inv()
        return MozcEngineCandidate(
            index = index,
            key = candidate.key,
            value = candidate.value,
            contentKey = candidate.contentKey,
            contentValue = candidate.contentValue,
            cost = candidate.cost,
            wcost = candidate.wcost,
            structureCost = candidate.structureCost,
            lid = candidate.lid,
            rid = candidate.rid,
            attributes = Attribute.namesOf(converterBits),
            description = candidate.description,
            category = candidate.category.name,
            innerSegments = candidate.innerSegments.mapIndexed { innerIndex, inner ->
                toEngineInnerSegment(innerIndex, inner)
            },
            source = "",
            types = PredictionTypes.namesOf(predictionBits),
            consumedKeySize = candidate.consumedKeySize,
        )
    }

    private fun toEngineInnerSegment(index: Int, innerSegment: InnerSegment): MozcEngineInnerSegment =
        MozcEngineInnerSegment(
            index = index,
            key = innerSegment.key,
            value = innerSegment.value,
            contentKey = innerSegment.contentKey,
            contentValue = innerSegment.contentValue,
        )
}
