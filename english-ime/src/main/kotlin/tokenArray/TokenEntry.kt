package tokenArray

import java.io.Serializable

data class TokenEntry(
    val wordCost: Short,
    val nodeId: Int,
) : Serializable
