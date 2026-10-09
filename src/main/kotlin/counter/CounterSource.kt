package com.kazumaproject.counter

import java.io.File

internal object CounterSourceParser {
    private fun rows(file: File, header: String): List<List<String>> {
        require(file.isFile) { "Missing source: ${file.path}" }
        val lines = file.readLines(Charsets.UTF_8)
        require(lines.firstOrNull() == header) { "Invalid header: ${file.path}; expected $header" }
        val width = header.split('\t').size
        return lines.drop(1).mapIndexedNotNull { index, line ->
            if (line.isBlank() || line.startsWith('#')) null else line.split('\t').also { columns ->
                require(columns.size == width) { "${file.path}:${index + 2}: expected $width columns" }
                require(columns.all { it == it.trim() }) { "${file.path}:${index + 2}: surrounding whitespace" }
            }
        }
    }

    fun parse(directory: File): CounterSource {
        val numbers = rows(directory.resolve("numbers.tsv"), "reading\tvalue\tkind\tplace").map { c ->
            val kind = when (c[2]) {
                "zero" -> 0; "part" -> 1; "scale" -> 2; "before_scale" -> 3; "before_k_scale" -> 4
                else -> error("Unknown number kind: ${c[2]}")
            }
            NumberPart(c[0], c[1].toLong(), kind, c[3].toLong()).also { require(validNumber(it)) { "Invalid number part: $c" } }
        }.sortedBy { it.reading }
        require(numbers.isNotEmpty() && numbers.map { it.reading }.distinct().size == numbers.size) { "Duplicate/empty number readings" }
        val rules = rows(directory.resolve("rules.tsv"), "profile\tterminal\tspoken_tail\trestored_tail\tsuffix_form\tmode").map { c ->
            val terminal = c[1].toInt()
            require(terminal in 0..9 || terminal in listOf(10, 100, 1000, 10000)) { "Unknown terminal: $terminal" }
            require(c[2].isNotEmpty() && c[3].isNotEmpty())
            require(c[4] in listOf("plain", "voiced", "semi") && c[5] in listOf("replace", "add"))
            require(numbers.any { it.reading.endsWith(c[3]) && (if (it.place == 1L) it.value.toInt() else it.place.toInt()) == terminal }) { "Unresolved numeric tail: $c" }
            TailRule(c[0], terminal, c[2], c[3], c[4], c[5] == "replace")
        }
        require(rules.distinct().size == rules.size) { "Duplicate tail rules" }
        val profiles = rules.groupBy { it.profile }
        val unitRows = rows(directory.resolve("counters.tsv"), "id\tsurface\tplain\tvoiced\tsemi\tprofile\tcategory\tmin\tmax\tpriority").sortedBy { it[0] }
        val endings = mutableListOf<CounterEnding>()
        val units = unitRows.mapIndexed { index, c ->
            require(c[0].matches(Regex("[a-z][a-z0-9_]*")) && c[1].isNotEmpty() && c[6].isNotEmpty()) { "Invalid unit: $c" }
            require(c[5] in profiles || c[5] in listOf("REGULAR", "EXCEPTION_ONLY")) { "Unknown profile: ${c[5]}" }
            val min = c[7].toLong(); val max = if (c[8] == "*") Long.MAX_VALUE else c[8].toLong(); val priority = c[9].toInt()
            require(min >= 0 && max >= min && priority >= 0)
            var blocked = if (c[5] == "EXCEPTION_ONLY") -1 else 0
            if (c[5] != "EXCEPTION_ONLY") {
                require(c[2].isNotEmpty())
                endings += CounterEnding(index, c[2], "", -1)
                profiles[c[5]].orEmpty().forEach { rule ->
                    val suffix = c[when (rule.form) { "plain" -> 2; "voiced" -> 3; else -> 4 }]
                    require(suffix.isNotEmpty()) { "Missing ${rule.form} form for ${c[0]}" }
                    endings += CounterEnding(index, rule.spoken + suffix, rule.restored, rule.terminal)
                    if (rule.replace) blocked = blocked or terminalBit(rule.terminal)
                }
            }
            CounterUnit(c[0], c[1], c[6], priority, min, max, blocked)
        }
        require(units.isNotEmpty() && units.map { it.id }.distinct().size == units.size) { "Duplicate/empty units" }
        val ids = units.mapIndexed { index, unit -> unit.id to index }.toMap()
        fun unitId(id: String): Int = requireNotNull(ids[id]) { "Unknown counter ID: $id" }
        val exceptions = rows(directory.resolve("exceptions.tsv"), "counter_id\tnumber\treading\tmode\toutput_unit").map { c ->
            val unit = unitId(c[0]); val number = c[1].toLong()
            require(number in units[unit].min..units[unit].max && c[2].isNotEmpty()) { "Invalid exception: $c" }
            require(c[3] in listOf("replace", "add"))
            val suffix = when (c[4]) { "@inherit" -> units[unit].surface; "@empty" -> ""; else -> c[4] }
            CounterException(unit, number, c[2], c[3] == "replace", suffix)
        }.sortedWith(compareBy({ it.unit }, { it.number }, { it.reading }))
        require(exceptions.distinct().size == exceptions.size) { "Duplicate exceptions" }
        require(exceptions.map { it.unit to it.reading }.distinct().size == exceptions.size) { "Conflicting exception readings" }
        require(exceptions.groupBy { it.unit to it.number }.values.all { group -> group.map { it.replace }.distinct().size == 1 }) { "Mixed exception policies for one quantity" }
        units.forEachIndexed { i, u -> require(u.blocked != -1 || exceptions.any { it.unit == i }) { "Missing exceptions for ${u.id}" } }
        val surfaces = rows(directory.resolve("surfaces.tsv"), "counter_id\tsurface\tpriority").map { c ->
            val priority = c[2].toInt()
            require(c[1].isNotEmpty() && priority > 0) { "Alias priorities must be positive: $c" }
            CounterSurface(unitId(c[0]), c[1], priority)
        }.sortedWith(compareBy({ it.unit }, { it.priority }, { it.surface }))
        require(surfaces.map { it.unit to it.surface }.distinct().size == surfaces.size) { "Duplicate surface aliases" }
        require(surfaces.none { it.surface == units[it.unit].surface }) { "Alias duplicates primary surface" }
        return CounterSource(numbers, units, endings.distinct().sortedWith(compareBy({ it.unit }, { it.reading }, { it.restored }, { it.terminal })), exceptions, surfaces)
    }
}
