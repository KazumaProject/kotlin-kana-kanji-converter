package mozc_data

import java.nio.file.Files
import java.nio.file.Path

data class MozcDataVerificationReport(
    val fileSize: Long,
    val metadataSize: Long,
    val sectionCount: Int,
    val version: String,
)

class MozcDataVerifier(
    private val reader: MozcDataSetReader = MozcDataSetReader(),
) {
    fun verify(path: Path, expectedVersion: String? = null): MozcDataVerificationReport {
        val dataSet = reader.read(path)
        val dataManager = MozcDataManager(dataSet.sections, expectedVersion)
        require(Files.size(path) == dataSet.fileSize) {
            "mozc.data file size changed while verifying: path=$path"
        }
        return MozcDataVerificationReport(
            fileSize = dataSet.fileSize,
            metadataSize = dataSet.metadataSize,
            sectionCount = dataSet.sections.size,
            version = dataManager.version(),
        )
    }
}
