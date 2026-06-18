package mozc_runtime

import kotlin.test.Test

class MozcImmutableConverterGoldenTest {
    @Test
    fun conversionResultMatchesOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("conversion/startconversion.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.converter.ImmutableConverter")
    }
}
