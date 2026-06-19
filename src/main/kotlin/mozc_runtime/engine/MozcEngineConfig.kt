package mozc_runtime.engine

import mozc_runtime.rewriter.Rewriter
import java.time.Instant

data class MozcEngineConfig(
    val maxCandidates: Int = 20,
    val suggestionsSize: Int = 3,
    val fixedTime: Instant = Instant.parse(Rewriter.DefaultFixedInstant),
    val enableA11yDescription: Boolean = false,
    val useKanaModifierInsensitiveConversion: Boolean = false,
)
