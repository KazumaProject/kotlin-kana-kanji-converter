package mozc_runtime.engine

data class MozcEngineCandidate(
    val index: Int,
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
    val cost: Int,
    val wcost: Int,
    val structureCost: Int,
    val lid: Int,
    val rid: Int,
    val attributes: List<String>,
    val description: String,
    val category: String,
    val innerSegments: List<MozcEngineInnerSegment>,
    val source: String,
    val types: List<String>,
    val consumedKeySize: Int,
)

data class MozcEngineInnerSegment(
    val index: Int,
    val key: String,
    val value: String,
    val contentKey: String,
    val contentValue: String,
)
