package distribution

import kotlin.test.Test

class NoNativeFilesInBundlesTest {
    @Test
    fun finalBundlesDoNotContainNativeLibraryFiles() {
        AssetBundleTestSupport.finalArtifactNames.forEach { zipName ->
            AssetBundleTestSupport.assertNoNativeFiles(zipName)
        }
    }
}
