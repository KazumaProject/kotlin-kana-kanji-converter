package mozc_data

object MozcDataVersion {
    val Magic: ByteArray = byteArrayOf(0xEF.toByte(), 0x4D, 0x4F, 0x5A, 0x43, 0x0D, 0x0A)
    const val MagicHex: String = "EF4D4F5A430D0A"
    const val FormatName: String = "mozc.data"
    const val SupportedEngineVersion: String = "24.11.oss"
    const val FooterSize: Int = 36
    const val StoredSha1Size: Int = 20
    const val OfficialSectionAlignmentBytes: Long = 4
}
