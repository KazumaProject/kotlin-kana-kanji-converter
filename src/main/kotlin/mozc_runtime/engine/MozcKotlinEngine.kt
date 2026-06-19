package mozc_runtime.engine

// Ported from mozc/src/engine/engine.cc
// Ported from mozc/src/engine/engine.h
class MozcKotlinEngine(
    private val modules: MozcModules,
    private val config: MozcEngineConfig = MozcEngineConfig(),
) {
    private val converter = MozcKotlinEngineConverter(modules, config)

    fun evaluate(request: MozcConversionRequest): MozcEngineResult =
        converter.evaluate(
            request.copy(
                maxCandidates = if (request.maxCandidates > 0) request.maxCandidates else config.maxCandidates,
                suggestionsSize = request.suggestionsSize.coerceIn(1, 9),
                enableA11yDescription = request.enableA11yDescription || config.enableA11yDescription,
            ),
        )
}
