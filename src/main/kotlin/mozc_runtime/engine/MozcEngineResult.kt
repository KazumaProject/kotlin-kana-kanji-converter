package mozc_runtime.engine

data class MozcEngineResult(
    val requestType: MozcRequestType,
    val input: String,
    val context: String,
    val segments: List<MozcEngineSegment>,
    val dataVersion: String,
)
