package mozc_runtime.dictionary

// Ported from mozc/src/dictionary/pos_group.*
class PosGroup(
    groups: Map<String, Set<Int>>,
) {
    private val groups: Map<String, Set<Int>> = groups.mapValues { it.value.toSet() }

    fun contains(groupName: String, posId: Int): Boolean = groups[groupName]?.contains(posId) == true

    fun ids(groupName: String): Set<Int> = groups[groupName]?.toSet() ?: setOf()
}
