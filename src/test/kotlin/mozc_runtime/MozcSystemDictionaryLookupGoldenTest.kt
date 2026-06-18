package mozc_runtime

import kotlin.test.Test

class MozcSystemDictionaryLookupGoldenTest {
    @Test
    fun lookupPrefixExactPredictiveAndReverseMatchOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("dictionary/system_dictionary_lookup.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.dictionary.system.SystemDictionary")
    }
}
