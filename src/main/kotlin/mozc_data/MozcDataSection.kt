package mozc_data

import java.nio.ByteBuffer

data class MozcDataSection(
    val name: String,
    val offset: Long,
    val size: Long,
    val data: ByteBuffer,
)
