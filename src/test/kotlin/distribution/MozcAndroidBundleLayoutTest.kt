package distribution

import kotlin.test.Test

class MozcAndroidBundleLayoutTest {
    @Test
    fun mozcAndroidBundleContainsRuntimeArtifactsAtRoot() {
        AssetBundleTestSupport.assertExactEntries(
            "mozc_android_bundle.zip",
            listOf("mozc.data", "mozc_data_manifest.json", "mozc-runtime.jar"),
        )
    }

    @Test
    fun mozcDataBundleContainsOnlyDataAndManifest() {
        AssetBundleTestSupport.assertExactEntries(
            "mozc_data_bundle.zip",
            listOf("mozc.data", "mozc_data_manifest.json"),
        )
    }

    @Test
    fun japaneseKeyboardMozcAssetsUseMozcDirectory() {
        AssetBundleTestSupport.assertExactEntries(
            "japanese_keyboard_mozc_assets.zip",
            AssetBundleTestSupport.japaneseKeyboardMozcEntries,
        )
    }
}
