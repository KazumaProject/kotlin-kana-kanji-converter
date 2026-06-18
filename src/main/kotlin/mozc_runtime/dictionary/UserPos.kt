package mozc_runtime.dictionary

// Ported from mozc/src/dictionary/user_pos.*
data class UserPos(
    val key: String,
    val value: String,
    val lid: Int,
    val rid: Int,
    val cost: Int,
)
