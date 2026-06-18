package mozc_runtime.converter

// Ported from mozc/src/converter/segments.h
// Ported from mozc/src/converter/segments.cc
class Segments {
    private val segments = ArrayList<Segment>()
    private var maxHistorySegmentsSizeValue: Int = 0
    private var resizedValue: Boolean = false
    private var revertIdValue: Long = 0

    fun all(): List<Segment> = segments

    fun segment(index: Int): Segment = segments[index]

    fun mutableSegment(index: Int): Segment = segments[index]

    fun historySegments(): List<Segment> = segments.take(historySegmentsSize())

    fun conversionSegments(): List<Segment> = segments.drop(historySegmentsSize())

    fun conversionSegment(index: Int): Segment = segments[index + historySegmentsSize()]

    fun mutableConversionSegment(index: Int): Segment = conversionSegment(index)

    fun historySegment(index: Int): Segment = segments[index]

    fun pushBackSegment(): Segment {
        val segment = Segment()
        segments += segment
        return segment
    }

    fun addSegment(): Segment = pushBackSegment()

    fun insertSegment(index: Int): Segment {
        val segment = Segment()
        segments.add(index, segment)
        return segment
    }

    fun segmentsSize(): Int = segments.size

    fun historySegmentsSize(): Int {
        var count = 0
        for (segment in segments) {
            if (segment.segmentType != Segment.SegmentType.HISTORY &&
                segment.segmentType != Segment.SegmentType.SUBMITTED
            ) {
                break
            }
            count += 1
        }
        return count
    }

    fun conversionSegmentsSize(): Int = segments.size - historySegmentsSize()

    fun eraseSegments(index: Int, size: Int) {
        if (index !in 0..segments.size || size < 0 || index > segments.size - size) {
            return
        }
        repeat(size) {
            segments.removeAt(index)
        }
    }

    fun clearHistorySegments() {
        while (segments.isNotEmpty()) {
            val segment = segments.first()
            if (segment.segmentType != Segment.SegmentType.HISTORY &&
                segment.segmentType != Segment.SegmentType.SUBMITTED
            ) {
                break
            }
            segments.removeAt(0)
        }
    }

    fun clearConversionSegments() {
        resizedValue = false
        eraseSegments(historySegmentsSize(), conversionSegmentsSize())
    }

    fun clearSegments() {
        segments.clear()
        resizedValue = false
    }

    fun clear() {
        clearSegments()
        revertIdValue = 0
    }

    fun setMaxHistorySegmentsSize(size: Int) {
        maxHistorySegmentsSizeValue = size.coerceIn(0, MaxHistorySize)
    }

    fun maxHistorySegmentsSize(): Int = maxHistorySegmentsSizeValue

    fun resized(): Boolean = resizedValue

    fun setResized(resized: Boolean) {
        resizedValue = resized
    }

    fun historyKey(size: Int = -1): String {
        val history = historySegments()
        val target = if (size >= 0) history.takeLast(size) else history
        return buildString {
            target.forEach { segment ->
                if (segment.candidatesSize() > 0) {
                    append(segment.candidate(0).key)
                }
            }
        }
    }

    fun historyValue(size: Int = -1): String {
        val history = historySegments()
        val target = if (size >= 0) history.takeLast(size) else history
        return buildString {
            target.forEach { segment ->
                if (segment.candidatesSize() > 0) {
                    append(segment.candidate(0).value)
                }
            }
        }
    }

    fun initForConvert(key: String) {
        setMaxHistorySegmentsSize(4)
        clearConversionSegments()
        val segment = addSegment()
        segment.setKey(key)
        segment.segmentType = Segment.SegmentType.FREE
    }

    fun initForCommit(key: String, value: String) {
        clearConversionSegments()
        val segment = addSegment()
        segment.setKey(key)
        segment.segmentType = Segment.SegmentType.FIXED_VALUE
        val candidate = segment.addCandidate()
        candidate.key = key
        candidate.contentKey = key
        candidate.value = value
        candidate.contentValue = value
    }

    fun replaceConversionSegments(newSegments: List<Segment>) {
        val historySize = historySegmentsSize()
        eraseSegments(historySize, conversionSegmentsSize())
        newSegments.forEach { source ->
            val target = addSegment()
            target.copyFrom(source)
        }
    }

    fun setRevertId(revertId: Long) {
        revertIdValue = revertId
    }

    fun revertId(): Long = revertIdValue

    private companion object {
        const val MaxHistorySize: Int = 32
    }
}
