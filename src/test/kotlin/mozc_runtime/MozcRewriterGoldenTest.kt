package mozc_runtime

import kotlin.test.Test

class MozcRewriterGoldenTest {
    @Test
    fun rewrittenCandidatesMatchOfficialMozc() {
        MozcGoldenTestSupport.officialData()
        MozcGoldenTestSupport.fixture("rewriter/rewriter_chain.json")
        MozcGoldenTestSupport.runtimeClass("mozc_runtime.rewriter.Rewriter")
    }
}
