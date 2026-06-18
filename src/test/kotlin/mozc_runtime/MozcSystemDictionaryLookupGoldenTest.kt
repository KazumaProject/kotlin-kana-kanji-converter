package mozc_runtime

import kotlin.test.Test
import kotlin.test.assertEquals

class MozcSystemDictionaryLookupGoldenTest {
    @Test
    fun lookupPrefixExactPredictiveAndReverseMatchOfficialMozc() {
        val fixturePath = MozcGoldenTestSupport.fixture("dictionary/system_dictionary_lookup.json")
        val fixture = MozcDictionaryGoldenSupport.readLookupFixture(fixturePath)
        assertEquals("24.11.oss", fixture.engineDataVersion)
        val dictionary = MozcDictionaryGoldenSupport.systemDictionary()

        fixture.queries.forEach { query ->
            MozcDictionaryGoldenSupport.assertTokenListEquals(
                query.lookupPrefix,
                MozcDictionaryGoldenSupport.collect { callback -> dictionary.lookupPrefix(query.query, callback) },
                "lookupPrefix query=${query.query}",
            )
            MozcDictionaryGoldenSupport.assertTokenListEquals(
                query.lookupExact,
                MozcDictionaryGoldenSupport.collect { callback -> dictionary.lookupExact(query.query, callback) },
                "lookupExact query=${query.query}",
            )
            MozcDictionaryGoldenSupport.assertTokenListEquals(
                query.lookupPredictive,
                MozcDictionaryGoldenSupport.collect { callback -> dictionary.lookupPredictive(query.query, callback) },
                "lookupPredictive query=${query.query}",
            )
            MozcDictionaryGoldenSupport.assertTokenListEquals(
                query.lookupReverse,
                MozcDictionaryGoldenSupport.collect { callback -> dictionary.lookupReverse(query.query, callback) },
                "lookupReverse query=${query.query}",
            )
        }
    }
}
