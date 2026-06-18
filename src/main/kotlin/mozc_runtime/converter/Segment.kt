package mozc_runtime.converter

// Ported from mozc/src/converter/segments.h
// Ported from mozc/src/converter/segments.cc
class Segment {
    enum class SegmentType {
        FREE,
        FIXED_BOUNDARY,
        FIXED_VALUE,
        SUBMITTED,
        HISTORY,
    }

    private var keyValue: String = ""
    private var keyLength: Int = 0
    private val candidateList = ArrayList<Candidate>()
    private val metaCandidateList = ArrayList<Candidate>()

    var segmentType: SegmentType = SegmentType.FREE

    fun key(): String = keyValue

    fun keyLen(): Int = keyLength

    fun setKey(key: String) {
        keyValue = key
        keyLength = key.charsLen()
    }

    fun candidatesSize(): Int = candidateList.size

    fun candidate(index: Int): Candidate =
        if (index < 0) metaCandidateList[-index - 1] else candidateList[index]

    fun mutableCandidate(index: Int): Candidate = candidate(index)

    fun addCandidate(): Candidate = pushBackCandidate()

    fun pushBackCandidate(): Candidate {
        val candidate = Candidate()
        candidateList += candidate
        return candidate
    }

    fun pushFrontCandidate(): Candidate {
        val candidate = Candidate()
        candidateList.add(0, candidate)
        return candidate
    }

    fun insertCandidate(index: Int): Candidate {
        val candidate = Candidate()
        candidateList.add(index.coerceIn(0, candidateList.size), candidate)
        return candidate
    }

    fun popBackCandidate() {
        if (candidateList.isNotEmpty()) {
            candidateList.removeAt(candidateList.lastIndex)
        }
    }

    fun eraseCandidate(index: Int) {
        if (index in candidateList.indices) {
            candidateList.removeAt(index)
        }
    }

    fun clearCandidates() {
        candidateList.clear()
    }

    fun candidates(): List<Candidate> = candidateList

    fun addMetaCandidate(): Candidate {
        val candidate = Candidate()
        metaCandidateList += candidate
        return candidate
    }

    fun clear() {
        clearCandidates()
        metaCandidateList.clear()
        keyValue = ""
        keyLength = 0
        segmentType = SegmentType.FREE
    }

    fun copyFrom(other: Segment) {
        clear()
        keyValue = other.keyValue
        keyLength = other.keyLength
        segmentType = other.segmentType
        other.candidateList.forEach {
            val candidate = addCandidate()
            candidate.copyFrom(it)
        }
        other.metaCandidateList.forEach {
            val candidate = addMetaCandidate()
            candidate.copyFrom(it)
        }
    }
}
