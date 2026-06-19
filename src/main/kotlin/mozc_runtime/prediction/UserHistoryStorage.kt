package mozc_runtime.prediction

// Ported from mozc/src/prediction/user_history_storage.h
// Ported from mozc/src/prediction/user_history_storage.cc
class UserHistoryStorage {
    private val entries = LinkedHashMap<Pair<String, String>, Result>()

    fun add(key: String, value: String): Boolean {
        val result = Result(
            key = key,
            value = value,
            contentKey = key,
            contentValue = value,
            attributes = PredictionTypes.Unigram or PredictionTypes.WeakUserHistoryPrediction,
        )
        entries[key to value] = result
        return true
    }

    fun lookupByPrefix(key: String, limit: Int): List<Result> {
        val results = ArrayList<Result>()
        entries.values.forEach { result ->
            if (results.size >= limit) return@forEach
            if (key.isEmpty() || result.key.startsWith(key)) {
                results += result.copy(attributes = result.attributes or PredictionTypes.WeakUserHistoryPrediction)
            }
        }
        return results
    }

    fun clear(): Boolean {
        entries.clear()
        return true
    }

    fun remove(key: String, value: String): Boolean = entries.remove(key to value) != null

    fun sync(): Boolean = true

    fun reload(): Boolean = true

    fun waitForSync(): Boolean = true
}
