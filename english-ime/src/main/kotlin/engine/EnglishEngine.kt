package engine

import louds.LOUDS
import louds.louds_with_term_id.LOUDSWithTermId
import result.Result
import succinctBitVector.SuccinctBitVector
import tokenArray.TokenArray

class EnglishEngine(
    private val readingLOUDS: LOUDSWithTermId,
    private val wordLOUDS: LOUDS,
    private val tokenArray: TokenArray,
    private val succinctBitVectorLBSReading: SuccinctBitVector,
    private val succinctBitVectorLBSWord: SuccinctBitVector,
    private val succinctBitVectorReadingIsLeaf: SuccinctBitVector,
    private val succinctBitVectorTokenArray: SuccinctBitVector
) {

    fun getPrediction(
        input: String,
        ): List<Result> {
        val predictions = mutableListOf<Result>()
        // 検索対象となる読みの共通プレフィックスを取得
        val commonPrefixReading = readingLOUDS.predictiveSearch(
            input,
            succinctBitVectorLBSReading
        )

        println("commonPrefixReading: $commonPrefixReading")

        for (readingStr in commonPrefixReading) {
            val nodeIndex = readingLOUDS.getNodeIndex(
                readingStr,
                succinctBitVector = succinctBitVectorLBSReading
            )
            if (nodeIndex > 0) {
                val termId = readingLOUDS.getTermId(
                    nodeIndex = nodeIndex,
                    succinctBitVector = succinctBitVectorReadingIsLeaf
                )
                // termId に対応する単語リストを取得
                val listToken = tokenArray.getListDictionaryByYomiTermId(
                    termId,
                    succinctBitVectorTokenArray
                )
                // Result オブジェクトのリストを作成
                val tangoList = listToken.map {
                    Result(
                        reading = readingStr,
                        word = when (it.nodeId) {
                            -1 -> readingStr
                            else -> wordLOUDS.getLetter(
                                it.nodeId,
                                succinctBitVector = succinctBitVectorLBSWord
                            )
                        },
                        score = it.wordCost
                    )
                }
                // 全体の予測リストに追加
                predictions.addAll(tangoList)
            }
        }
        return predictions.sortedBy { it.score }
    }
}
