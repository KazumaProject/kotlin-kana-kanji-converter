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

    @Test
    fun splitDictionaryArtifactsUseJapaneseKeyboardLayout() {
        mapOf(
            "main_dictionaries.zip" to AssetBundleTestSupport.mainDictionaryEntries,
            "mozc_ut_dictionaries.zip" to AssetBundleTestSupport.mozcUTDictionaryEntries,
            "wiki_dictionary.zip" to AssetBundleTestSupport.wikiDictionaryEntries,
            "neologd_dictionary.zip" to AssetBundleTestSupport.neologdDictionaryEntries,
            "web_dictionary.zip" to AssetBundleTestSupport.webDictionaryEntries,
        ).forEach { (zipName, expectedEntries) ->
            AssetBundleTestSupport.assertExactEntries(zipName, expectedEntries)
            AssetBundleTestSupport.assertDatZipEntriesAreReal(zipName)
        }
    }
}
