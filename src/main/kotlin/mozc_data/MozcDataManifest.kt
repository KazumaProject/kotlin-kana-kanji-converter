package mozc_data

data class MozcDataManifest(
    val format: String,
    val magic: String,
    val engineVersion: String,
    val version: String,
    val sha1: String,
    val sha256: String,
    val fileSize: Long,
    val sections: List<Section>,
) {
    data class Section(
        val name: String,
        val offset: Long,
        val size: Long,
    )
}
