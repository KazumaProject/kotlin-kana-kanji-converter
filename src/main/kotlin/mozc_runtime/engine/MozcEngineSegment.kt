package mozc_runtime.engine

data class MozcEngineSegment(
    val index: Int,
    val key: String,
    val candidates: List<MozcEngineCandidate>,
)
