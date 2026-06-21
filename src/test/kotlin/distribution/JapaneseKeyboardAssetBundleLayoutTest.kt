package distribution

import kotlin.test.Test

class JapaneseKeyboardAssetBundleLayoutTest {
    @Test
    fun japaneseKeyboardDictionaryAssetsCanBeExpandedIntoAssetsRoot() {
        AssetBundleTestSupport.assertExactEntries(
            "japanese_keyboard_dictionary_assets.zip",
            AssetBundleTestSupport.japaneseKeyboardDictionaryEntries,
        )
        AssetBundleTestSupport.assertNoEnglishAssets("japanese_keyboard_dictionary_assets.zip")
        AssetBundleTestSupport.assertDatZipEntriesAreReal("japanese_keyboard_dictionary_assets.zip")
    }
}
