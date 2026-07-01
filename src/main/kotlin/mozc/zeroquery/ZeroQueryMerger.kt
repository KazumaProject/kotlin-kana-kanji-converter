package com.kazumaproject.mozc.zeroquery

object ZeroQueryMerger {
    fun mergeOfficial(
        ruleDict: Map<String, List<ZeroQueryEntry>>,
        emojiDict: Map<String, List<ZeroQueryEntry>>,
        emoticonDict: Map<String, List<ZeroQueryEntry>>,
        symbolDict: Map<String, List<ZeroQueryEntry>>,
    ): ZeroQueryEntryMap {
        val merged = ZeroQueryEntryMap()

        appendAll(merged, ruleDict)

        emojiDict.forEach { (key, entries) ->
            if (!isAsciiKey(key) && entries.size <= 3) {
                appendAll(merged, key, entries)
            }
        }

        emoticonDict.forEach { (key, entries) ->
            if (!isAsciiKey(key)) {
                appendAll(merged, key, entries.take(3))
            }
        }

        symbolDict.forEach { (key, entries) ->
            if (!isAsciiKey(key) && entries.size <= 3) {
                appendAll(merged, key, entries)
            }
        }

        return merged
    }

    fun mergeWithCustom(
        ruleDict: Map<String, List<ZeroQueryEntry>>,
        emojiDict: Map<String, List<ZeroQueryEntry>>,
        emoticonDict: Map<String, List<ZeroQueryEntry>>,
        symbolDict: Map<String, List<ZeroQueryEntry>>,
        customRuleDict: Map<String, List<ZeroQueryEntry>>,
    ): ZeroQueryEntryMap {
        val merged = mergeOfficial(ruleDict, emojiDict, emoticonDict, symbolDict)
        appendCustom(merged, customRuleDict)
        return merged
    }

    fun appendCustom(
        merged: ZeroQueryEntryMap,
        customRuleDict: Map<String, List<ZeroQueryEntry>>,
    ) {
        customRuleDict.forEach { (key, customEntries) ->
            val entries = merged.getOrPut(key) { mutableListOf() }
            val seenValues = entries.mapTo(linkedSetOf()) { it.value }
            customEntries.forEach { entry ->
                require(entry.key == key) {
                    "Custom zero query entry key does not match map key: map key='$key', entry key='${entry.key}'"
                }
                if (seenValues.add(entry.value)) {
                    entries += entry
                }
            }
        }
    }

    private fun appendAll(target: ZeroQueryEntryMap, source: Map<String, List<ZeroQueryEntry>>) {
        source.forEach { (key, entries) -> appendAll(target, key, entries) }
    }

    private fun appendAll(target: ZeroQueryEntryMap, key: String, entries: List<ZeroQueryEntry>) {
        if (entries.isEmpty()) {
            return
        }
        val targetEntries = target.getOrPut(key) { mutableListOf() }
        entries.forEach { entry ->
            require(entry.key == key) {
                "Zero query entry key does not match map key: map key='$key', entry key='${entry.key}'"
            }
            targetEntries += entry
        }
    }
}
