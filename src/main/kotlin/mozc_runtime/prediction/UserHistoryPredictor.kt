package mozc_runtime.prediction

// Ported from mozc/src/prediction/user_history_predictor.h
// Ported from mozc/src/prediction/user_history_predictor.cc
class UserHistoryPredictor(
    private val storage: UserHistoryStorage,
) {
    fun predict(request: PredictionRequest): List<Result> {
        val limit = if (request.isZeroQuerySuggestion()) {
            request.maxUserHistoryPredictionCandidatesSizeForZeroQuery
        } else {
            request.maxUserHistoryPredictionCandidatesSize
        }
        if (limit <= 0) {
            return listOf()
        }
        return storage.lookupByPrefix(request.key, limit)
    }

    fun finish(request: PredictionRequest, results: List<Result>, revertId: Int) {
        results.firstOrNull()?.let { storage.add(it.key, it.value) }
    }

    fun commitContext(request: PredictionRequest) {
        if (request.historyKey.isNotEmpty() || request.historyValue.isNotEmpty()) {
            storage.add(request.historyKey, request.historyValue)
        }
    }

    fun revert(revertId: Int) {
        Unit
    }

    fun clearAllHistory(): Boolean = storage.clear()

    fun clearUnusedHistory(): Boolean = true

    fun clearHistoryEntry(key: String, value: String): Boolean = storage.remove(key, value)

    fun addHistoryEntry(key: String, value: String): Boolean = storage.add(key, value)

    fun sync(): Boolean = storage.sync()

    fun reload(): Boolean = storage.reload()

    fun waitForSync(): Boolean = storage.waitForSync()
}
