package com.kazumaproject.cli

import com.kazumaproject.dictionary.DictionaryMatch
import com.kazumaproject.dictionary.LoadedDictionary
import com.kazumaproject.engine.KanaKanjiEngine
import com.kazumaproject.quality.*
import kotlinx.serialization.json.*
import java.io.File
import java.io.PrintWriter
import java.sql.DriverManager
import java.util.zip.GZIPInputStream
import kotlin.system.exitProcess

fun main(args: Array<String>) { exitProcess(DictionaryCli.run(args, PrintWriter(System.out, true), PrintWriter(System.err, true))) }

object DictionaryCli {
    private val flags = setOf("offline", "online", "prefix", "no-system", "enforce", "candidate")
    private val common = setOf("dict-dir", "base-dir", "categories", "exclude-categories", "no-system", "format")
    private val allowed = mapOf(
        "build" to setOf("source-dir", "base-dir", "dict-dir", "reports", "metadata-db", "cache", "cache-limit-mib", "api-budget", "offline", "overrides", "snapshot", "lock", "confirmed", "input-manifest", "candidate"),
        "lookup" to common + setOf("reading", "surface", "prefix", "limit"),
        "convert" to common + setOf("input", "nbest"),
        "test" to common + setOf("cases", "nbest"),
        "compare" to setOf("before", "after", "output"),
        "evaluate" to common + setOf("words", "sentences", "output", "baseline", "enforce", "evaluation-lock", "extra-words", "extra-sentences", "extra-lock"),
        "metadata" to setOf("metadata-db", "postal-zip", "source-dir", "base-dir", "output", "snapshot", "lock", "archive", "confirmed", "api-budget", "minutes", "jmdict"),
        "explain" to setOf("reading", "surface", "reports", "format", "snapshot"),
        "package" to setOf("dict-dir", "output", "notices"),
        "verify-package" to setOf("output"),
        "cache" to setOf("cache", "cache-limit-mib"),
        "research" to setOf("ledger", "config", "source-dir", "base-dir", "audit", "snapshot", "documents", "jmnedict", "jmdict", "postal-zip", "mozc-commit", "id", "surface", "reason", "after-id", "gold", "input", "output", "source-staging", "batch-size", "pilot-size", "max-batches", "acceptance", "candidate", "online"),
    )
    private class Arguments(val command: String, val values: Map<String, String>) {
        fun value(name: String, default: String): String = values[name] ?: default
        fun required(name: String) = values[name] ?: throw IllegalArgumentException("Missing --$name")
        fun file(name: String, default: String) = File(value(name, default))
        fun flag(name: String) = values[name] == "true"
        fun number(name: String, default: Int, range: IntRange): Int = value(name, default.toString()).toIntOrNull()?.takeIf { it in range }
            ?: throw IllegalArgumentException("--$name must be in $range")
        fun selected(): List<String> {
            val specified = value("categories", "all")
            val root = file("dict-dir", "build/dictionaries/categories")
            val available = if (File(root, "manifest.json").isFile) CategoryRegistry.active(Json.parseToJsonElement(File(root, "manifest.json").readText()).jsonObject) else publishedCategories
            val selected = if (specified == "all") available else if (specified == "none") emptyList() else specified.split(',').distinct()
            val excluded = values["exclude-categories"]?.split(',').orEmpty()
            require((selected + excluded).all { it in available }) { "Unknown category; choose ${available.joinToString(",")}" }
            return selected.filter { it !in excluded }
        }
        fun withCategories(categories: String) = Arguments(command, values + ("categories" to categories))
    }

    private fun parse(args: Array<String>): Arguments {
        require(args.isNotEmpty() && args[0] in allowed) { "Unknown command" }
        val values = linkedMapOf<String, String>()
        var index = 1
        if (args[0] == "metadata") {
            require(args.getOrNull(index) in setOf("export", "refresh", "verify", "fetch", "import-lexicon")) { "metadata requires export, refresh, verify or fetch" }
            values["action"] = args[index++]
        }
        if (args[0] == "research") {
            require(args.getOrNull(index) in setOf("prepare", "bulk", "pilot", "run", "status", "explain", "review-export", "import-review", "complete-source-search", "select-gold", "freeze-gold", "accept", "finalize", "export")) { "research requires a valid action" }
            values["action"] = args[index++]
        }
        if (args[0] == "cache") {
            require(args.getOrNull(index) in setOf("prune", "clear")) { "cache requires prune or clear" }
            values["action"] = args[index++]
        }
        while (index < args.size) {
            val token = args[index++]
            require(token.startsWith("--")) { "Expected an option, got: $token" }
            val name = token.removePrefix("--")
            require(name in allowed.getValue(args[0]) && name !in values) { "Unknown or repeated option: --$name" }
            if (name in flags) values[name] = "true"
            else {
                val value = args.getOrNull(index++)
                require(value != null && !value.startsWith("--")) { "Missing value for --$name" }
                values[name] = value
            }
        }
        values["format"]?.let { require(it in setOf("table", "json")) { "--format must be table or json" } }
        return Arguments(args[0], values)
    }

    fun run(args: Array<String>, out: PrintWriter, err: PrintWriter): Int {
        if (args.isEmpty() || args[0] in setOf("--help", "-h", "help") || args.drop(1).any { it in setOf("--help", "-h") }) { out.println(help); return 0 }
        return try {
            val options = parse(args)
            val result = when (options.command) {
                "build" -> {
                    require(options.number("api-budget", 0, 0..100000) == 0) { "Build is offline; use metadata refresh for external acquisition" }
                    val snapshot = if (options.values.containsKey("metadata-db")) null else options.file("snapshot", "build/dictionary-metadata/snapshot.sqlite")
                    val lock = options.values["lock"]?.let(::File) ?: File("src/main/dictionary-quality/snapshot.lock.json").takeIf { it.isFile && !options.values.containsKey("snapshot") }
                    if (snapshot != null) {
                        if (lock != null) MetadataSnapshot.fetch(lock, snapshot)
                        MetadataSnapshot.verify(snapshot, lock, allowCandidate = options.flag("candidate"))
                    }
                    CategoryDictionaryBuilder().build(CategoryDictionaryBuilder.Options(
                        source = options.file("source-dir", "src/main/bin"), base = options.file("base-dir", "src/main/resources"),
                        output = options.file("dict-dir", "build/dictionaries/categories"), reports = options.file("reports", "build/reports/dictionary-quality"),
                        reference = options.values["metadata-db"]?.let(::File), cache = options.file("cache", "build/dictionary-metadata/cache.sqlite"),
                        cacheLimitMiB = options.number("cache-limit-mib", 512, 2..65536), apiBudget = 0,
                        offline = true, snapshot = snapshot, confirmed = options.values["confirmed"]?.let(::File) ?: File("src/main/dictionary-quality/confirmed.tsv").takeIf { it.isFile }, inputManifest = options.values["input-manifest"]?.let(::File), candidate = options.flag("candidate"), overrides = options.values["overrides"]?.let(::File) ?: File("src/main/dictionary-quality/overrides.tsv").takeIf { it.isFile },
                    )); 0
                }
                "lookup" -> { printMatches(lookup(options, load(options)), options, out); 0 }
                "convert" -> {
                    val input = options.required("input"); require(input.isNotEmpty()) { "Input cannot be empty" }
                    val engine = engine(options, load(options))
                    val detailed = engine.convertDetailed(input)
                    val candidates = engine.nBestPath(input, options.number("nbest", 10, 1..1000))
                    if (options.value("format", "table") == "json") out.println(buildJsonObject {
                        put("input", input); put("value", detailed.result.value); put("matched", detailed.result.bestPath.isNotEmpty())
                        put("candidates", buildJsonArray { candidates.forEach { add(it) } })
                        put("path", buildJsonArray { detailed.result.bestPath.forEachIndexed { index, node -> add(buildJsonObject {
                            put("reading", node.key); put("surface", node.value); put("dictionary", detailed.dictionaries[index])
                            put("leftId", node.lid); put("rightId", node.rid); put("wordCost", node.wcost); put("cost", node.cost); put("start", node.start); put("end", node.end)
                        }) } })
                    }) else {
                        out.println("best\t${detailed.result.value}")
                        candidates.forEachIndexed { index, value -> out.println("${index + 1}\t$value") }
                        detailed.result.bestPath.forEachIndexed { index, node -> out.println("path\t${node.key}\t${node.value}\t${detailed.dictionaries[index]}\t${node.lid}\t${node.rid}\t${node.wcost}") }
                    }
                    if (detailed.result.bestPath.isEmpty()) { err.println("No complete conversion path for: $input"); 1 } else 0
                }
                "test" -> regression(options, out)
                "compare" -> { out.println(DictionaryComparison.compare(File(options.required("before")),File(options.required("after")),options.file("output","build/reports/dictionary-quality/comparison")));0 }
                "evaluate" -> { val dictionaries=load(options);out.println(DictionaryEvaluation.evaluate(dictionaries,engine(options,dictionaries),options.file("words","src/main/dictionary-quality/evaluation-words.tsv"),options.file("sentences","src/main/dictionary-quality/evaluation-sentences.tsv"),options.file("output","build/reports/dictionary-quality/evaluation.json"),options.values["baseline"]?.let(::File),options.flag("enforce"),options.file("evaluation-lock","src/main/dictionary-quality/evaluation.lock.json"),options.values["extra-words"]?.let(::File),options.values["extra-sentences"]?.let(::File),options.values["extra-lock"]?.let(::File)));0 }
                "metadata" -> { metadata(options, out); 0 }
                "explain" -> { explain(options, out); 0 }
                "package" -> { CategoryPackage.write(options.file("dict-dir", "build/dictionaries/categories"), options.file("output", "build/category-release/categorized-dictionaries.zip"), options.file("notices", "src/main/dictionary-quality/NOTICES.md")); 0 }
                "verify-package" -> { CategoryPackage.verify(options.file("output", "build/category-release/categorized-dictionaries.zip")); 0 }
                "cache" -> { manageCache(options, out); 0 }
                "research" -> ResearchRunner.run(options.values, out, err)
                else -> error("Unknown command")
            }
            out.flush(); result
        } catch (e: Exception) {
            err.println("dictionary-cli: ${e.message ?: e.javaClass.simpleName}"); err.flush(); 2
        }
    }

    private fun load(options: Arguments): List<LoadedDictionary> {
        val dictionaries = mutableListOf<LoadedDictionary>()
        if (!options.flag("no-system")) dictionaries.add(LoadedDictionary.load("system", options.file("base-dir", "src/main/resources")))
        val root = options.file("dict-dir", "build/dictionaries/categories")
        val selected = options.selected()
        if (selected.isNotEmpty()) {
            val manifest = Json.parseToJsonElement(File(root, "manifest.json").readText()).jsonObject
            require(manifest["format"]?.jsonPrimitive?.content == "legacy-louds-triplets-v1") { "Unsupported dictionary manifest" }
            val hashes = manifest.getValue("artifacts").jsonObject
            (listOf("pos_table.dat") + selected.flatMap { category -> listOf("yomi.dat", "tango.dat", "token.dat").map { "$category/$it" } }).forEach { name ->
                val expected = hashes[name]?.jsonPrimitive?.content ?: error("Missing artifact in manifest: $name")
                require(sha256(File(root, name)) == expected) { "Dictionary checksum mismatch: $name" }
            }
            selected.forEach { category -> dictionaries.add(LoadedDictionary.load(category, File(root, category), File(root, "pos_table.dat"))) }
        }
        require(dictionaries.isNotEmpty()) { "No dictionaries selected" }
        return dictionaries
    }

    private fun engine(options: Arguments, dictionaries: List<LoadedDictionary>): KanaKanjiEngine {
        val base = options.file("base-dir", "src/main/resources")
        if (options.selected().isNotEmpty()) {
            val manifest = Json.parseToJsonElement(File(options.file("dict-dir", "build/dictionaries/categories"), "manifest.json").readText()).jsonObject
            val expected = manifest["sources"]?.jsonObject?.get("id.def")?.jsonPrimitive?.content
                ?: error("Missing id.def compatibility hash in category manifest")
            require(sha256(File(base, "id.def")) == expected) { "Category dictionaries and system id.def are incompatible" }
        }
        return KanaKanjiEngine().apply { loadDictionaries(dictionaries, File(base, "connectionId.dat")) }
    }

    private fun lookup(options: Arguments, dictionaries: List<LoadedDictionary>): List<DictionaryMatch> {
        val reading = options.values["reading"]
        val surface = options.values["surface"]
        require((reading == null) != (surface == null)) { "Specify exactly one of --reading or --surface" }
        require(!(options.flag("prefix") && surface != null)) { "--prefix requires --reading" }
        require((reading ?: surface).orEmpty().isNotEmpty()) { "Query cannot be empty" }
        val limit = options.number("limit", 50, 1..100000)
        val matches = dictionaries.asSequence().flatMap { dictionary ->
            if (reading != null && !options.flag("prefix")) dictionary.lookup(reading).asSequence()
            else dictionary.readings().filter { reading == null || it.startsWith(reading) }.flatMap { dictionary.lookup(it).asSequence() }.filter { surface == null || it.surface == surface }
        }
        return matches.sortedWith(compareBy({ it.cost }, { it.reading }, { it.surface }, { it.leftId }, { it.rightId }, { it.dictionary })).take(limit).toList()
    }

    private fun printMatches(matches: List<DictionaryMatch>, options: Arguments, out: PrintWriter) {
        if (options.value("format", "table") == "json") out.println(buildJsonArray { matches.forEach { match -> add(buildJsonObject {
            put("dictionary", match.dictionary); put("reading", match.reading); put("surface", match.surface)
            put("leftId", match.leftId); put("rightId", match.rightId); put("cost", match.cost)
        }) } }) else {
            out.println("dictionary\treading\tsurface\tleftId\trightId\tcost")
            matches.forEach { out.println("${it.dictionary}\t${it.reading}\t${it.surface}\t${it.leftId}\t${it.rightId}\t${it.cost}") }
        }
    }

    private fun regression(options: Arguments, out: PrintWriter): Int {
        val loaded = hashMapOf<String, List<LoadedDictionary>>()
        val engines = hashMapOf<String, KanaKanjiEngine>()
        var failures = 0; var count = 0
        options.file("cases", options.required("cases")).forEachLine { line ->
            if (line.isBlank() || line.startsWith("#") || line.startsWith("operation\t")) return@forEachLine
            val fields = line.split('\t')
            require(fields.size == 5) { "Case ${count + 1}: expected 5 TSV fields" }
            val (operation, input, assertion, expected, categories) = fields
            require(input.isNotEmpty()) { "Empty test input" }
            require(operation in setOf("lookup", "surface", "convert")) { "Unknown case operation: $operation" }
            require(assertion in if (operation == "convert") setOf("equals", "contains", "excludes") else setOf("contains", "excludes")) { "Invalid assertion: $assertion" }
            val selected = if (categories.isBlank()) options else options.withCategories(categories)
            val key = selected.selected().joinToString(",")
            val dictionaries = loaded.getOrPut(key) { load(selected) }
            val actual = if (operation == "convert") {
                val engine = engines.getOrPut(key) { engine(selected, dictionaries) }
                if (assertion == "equals") listOf(engine.convert(input).value) else engine.nBestPath(input, options.number("nbest", 64, 1..1000))
            } else dictionaries.flatMap { dictionary ->
                if (operation == "lookup") dictionary.lookup(input).map { it.surface }
                else dictionary.readings().flatMap { dictionary.lookup(it).asSequence() }.filter { it.surface == input }.map { it.surface }.toList()
            }
            val passed = when (assertion) { "equals" -> actual.singleOrNull() == expected; "contains" -> expected in actual; else -> expected !in actual }
            count++; if (!passed) failures++
            out.println("${if (passed) "PASS" else "FAIL"}\t$count\t$operation\t$input\t$assertion\t$expected")
        }
        require(count > 0) { "Case file is empty" }
        out.println("cases=$count failures=$failures")
        return if (failures == 0) 0 else 1
    }

    private fun metadata(options: Arguments, out: PrintWriter) {
        val snapshot = options.file("snapshot", "build/dictionary-metadata/snapshot.sqlite")
        val action = options.required("action")
        val output = options.file("output", if (action in setOf("refresh", "import-lexicon")) "build/metadata-candidate/snapshot.sqlite.gz" else "build/dictionary-metadata/snapshot.sqlite.gz")
        val lock = options.values["lock"]?.let(::File) ?: if (action in setOf("refresh", "import-lexicon")) File(output.absoluteFile.parentFile, "snapshot.lock.json") else File("src/main/dictionary-quality/snapshot.lock.json")
        when (options.required("action")) {
            "fetch" -> MetadataSnapshot.fetch(lock, snapshot, options.values["archive"]?.let(::File))
            "verify" -> out.println(MetadataSnapshot.verify(snapshot, options.values["lock"]?.let(::File)))
            "export" -> MetadataSnapshot.export(File(options.required("metadata-db")), File(options.required("postal-zip")), options.file("source-dir", "src/main/bin"), options.file("base-dir", "src/main/resources"), options.file("output", "build/dictionary-metadata/snapshot.sqlite.gz"), lock, options.values["confirmed"]?.let(::File) ?: File("src/main/dictionary-quality/confirmed.tsv").takeIf { it.isFile })
            "import-lexicon" -> MetadataSnapshot.importLexicon(snapshot, File(options.required("jmdict")), options.file("source-dir","src/main/bin"), options.file("base-dir","src/main/resources"), output, lock, options.values["metadata-db"]?.let(::File))
            "refresh" -> MetadataSnapshot.refresh(snapshot, options.values["postal-zip"]?.let(::File), output, lock, options.number("api-budget", 200, 0..100000), options.number("minutes", 30, 1..30))
        }
    }

    private fun explain(options: Arguments, out: PrintWriter) {
        val reading = options.values["reading"]; val surface = options.values["surface"]
        require(reading != null || surface != null) { "Specify --reading and/or --surface" }
        val report = File(options.file("reports", "build/reports/dictionary-quality"), "audit.tsv.gz")
        val records = mutableListOf<JsonObject>()
        GZIPInputStream(report.inputStream()).bufferedReader().use { input ->
            val columns = input.readLine().split('\t')
            input.lineSequence().forEach { line ->
                val f = columns.zip(line.split('\t')).toMap()
                if ((reading == null || reading == f["reading"] || reading == f["output_reading"]) && (surface == null || surface == f["surface"] || surface == f["output_surface"])) {
                    records.add(buildJsonObject { f.forEach { (k,v) -> put(k,v) } })
                }
            }
        }
        val snapshot=options.file("snapshot","build/dictionary-metadata/snapshot.sqlite")
        val explained=if(snapshot.isFile) DriverManager.getConnection("jdbc:sqlite:${snapshot.toURI()}?mode=ro").use { c ->
            val snapshotHash=sha256(snapshot)
            val hasDetails=c.createStatement().use { q ->q.executeQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='lexical_details'").use { it.next() } }
            val resolved=c.createStatement().use { q ->q.executeQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='resolutions'").use { it.next() } }
            records.map { record ->
                if(resolved) {
                    val facts=mutableListOf<JsonElement>()
                    val decisions=mutableListOf<JsonElement>()
                    c.prepareStatement("SELECT * FROM resolutions WHERE reading=? AND surface=? AND left_id=? AND right_id=?").use { q ->
                        q.setString(1,record.getValue("reading").jsonPrimitive.content);q.setString(2,record.getValue("surface").jsonPrimitive.content)
                        q.setInt(3,record.getValue("left_id").jsonPrimitive.int);q.setInt(4,record.getValue("right_id").jsonPrimitive.int)
                        q.executeQuery().use { r -> while(r.next()) {
                            decisions.add(buildJsonObject { put("id",r.getString("id"));put("status",r.getString("status"));put("reason",r.getString("reason"));put("roles",Json.parseToJsonElement(r.getString("roles"))) })
                            val references=listOf("reading_facts" to Json.parseToJsonElement(r.getString("reading_ids")).jsonArray,"semantic_facts" to Json.parseToJsonElement(r.getString("roles")).jsonArray.flatMap { it.jsonObject.getValue("evidenceIds").jsonArray },"quality_facts" to (Json.parseToJsonElement(r.getString("normalization_ids")).jsonArray+Json.parseToJsonElement(r.getString("exclusion_ids")).jsonArray))
                            for((table,refs) in references) c.prepareStatement("SELECT * FROM $table WHERE id=?").use { f -> refs.distinct().forEach { ref ->
                                f.setString(1,ref.jsonPrimitive.content);f.executeQuery().use { x -> if(x.next()) {
                                    val body=if(table=="reading_facts") x.getString("body") else GZIPInputStream(x.getBytes("body").inputStream()).bufferedReader().use { it.readText() }
                                    facts.add(buildJsonObject { put("id",x.getString("id"));put("kind",if(table=="reading_facts") "reading" else x.getString("kind"));put("target",x.getString("target"));put("url",x.getString("url"));put("revision",x.getString("revision"));put("sha256",x.getString("sha256"));put("body",Json.parseToJsonElement(body)) })
                                } }
                            } }
                        } }
                    }
                    return@map buildJsonObject { record.forEach { (k,v)->put(k,v) };put("resolutions",JsonArray(decisions));put("referenceFacts",JsonArray(facts));put("factsSnapshotSha256",snapshotHash) }
                }
                val names=listOf(record.getValue("surface").jsonPrimitive.content,record.getValue("output_surface").jsonPrimitive.content).filter { it.isNotEmpty() }.distinct()
                val ids=linkedSetOf<String>()
                c.prepareStatement("SELECT ids FROM lookup WHERE surface=?").use { q -> names.forEach { name -> q.setString(1,name);q.executeQuery().use { r -> if(r.next()) ids.addAll(Json.parseToJsonElement(r.getString(1)).jsonArray.map { it.jsonPrimitive.content }) } } }
                val entities=mutableListOf<JsonElement>()
                c.prepareStatement("SELECT body FROM entities WHERE id=?").use { q -> ids.forEach { id -> q.setString(1,id);q.executeQuery().use { r -> if(r.next()) entities.add(Json.parseToJsonElement(r.getString(1))) } } }
                val facts=mutableListOf<JsonElement>()
                if(hasDetails) c.prepareStatement("SELECT body FROM lexical_details WHERE reading=? AND surface=?").use { q ->
                    q.setString(1,record.getValue("output_reading").jsonPrimitive.content.ifEmpty { record.getValue("reading").jsonPrimitive.content })
                    q.setString(2,record.getValue("output_surface").jsonPrimitive.content.ifEmpty { record.getValue("surface").jsonPrimitive.content })
                    q.executeQuery().use { r -> while(r.next()) facts.add(Json.parseToJsonElement(r.getString(1))) }
                }
                buildJsonObject { record.forEach { (k,v)->put(k,v) };put("referenceFacts",JsonArray(entities));put("lexicalSenseFacts",JsonArray(facts));put("factsSnapshotSha256",snapshotHash) }
            }
        } else records.map { r -> buildJsonObject { r.forEach { (k,v)->put(k,v) };put("referenceFactsUnavailable",true) } }
        if (options.value("format", "table") == "json") out.println(JsonArray(explained)) else {
            explained.forEach { record -> out.println(record.entries.joinToString("\t") { "${it.key}=${if(it.value is JsonPrimitive) it.value.jsonPrimitive.content else it.value.toString()}" }) }
            out.println("records=${records.size}")
        }
    }

    private fun manageCache(options: Arguments, out: PrintWriter) {
        val file = options.file("cache", "build/dictionary-metadata/cache.sqlite")
        if (!file.exists()) { out.println("Cache absent"); return }
        DriverManager.getConnection("jdbc:sqlite:${file.toURI()}?mode=ro").use { connection ->
            val tables = connection.createStatement().use { statement -> statement.executeQuery("SELECT name FROM sqlite_master WHERE type='table'").use { result -> buildSet { while (result.next()) add(result.getString(1)) } } }
            require("lookup" in tables && "entities" in tables && "titles" !in tables) { "Refusing to modify an external reference catalog" }
        }
        if (options.required("action") == "clear") check(file.delete()) { "Could not delete cache" }
        else DriverManager.getConnection("jdbc:sqlite:${file.absolutePath}").use { connection ->
            val cap = options.number("cache-limit-mib", 512, 2..65536).toLong() * 1024 * 1024
            connection.createStatement().use { statement ->
                if (file.length() > cap) { statement.execute("DELETE FROM lookup"); statement.execute("DELETE FROM entities") }
                statement.execute("VACUUM")
            }
        }
        out.println("Cache bytes=${file.length()}")
    }

    private val help = """
        dictionary-cli <command> [options]
          build    --source-dir DIR --base-dir DIR --dict-dir DIR
                   [--snapshot FILE] [--lock FILE] [--confirmed TSV] [--overrides TSV] [--reports DIR]
          metadata export --metadata-db FILE --postal-zip ZIP [--output ARCHIVE] [--lock FILE]
          metadata fetch  [--lock FILE] [--snapshot FILE] [--archive LOCAL_ARCHIVE]
          metadata verify [--snapshot FILE] [--lock FILE]
          metadata import-lexicon --jmdict GZIP [--metadata-db ORIGINAL] [--snapshot FILE] [--output ARCHIVE] [--lock CANDIDATE_LOCK]
          metadata refresh [--snapshot FILE] [--output ARCHIVE] [--lock CANDIDATE_LOCK] [--api-budget 200] [--minutes 30]
          explain  --reading TEXT | --surface TEXT [--reports DIR] [--snapshot FILE] [--format json]
          package  [--dict-dir DIR] [--output ZIP] [--notices FILE]
          verify-package [--output ZIP]
          lookup   --reading TEXT [--prefix] | --surface TEXT [--limit 50]
          convert  --input TEXT [--nbest 10]
          test     --cases TSV [--nbest 64]
          compare --before AUDIT.gz --after AUDIT.gz [--output DIR]
          evaluate [--words TSV] [--sentences TSV] [--baseline JSON] [--output JSON] [--enforce]
          cache    prune|clear [--cache FILE] [--cache-limit-mib 512]
        lookup/convert/test: [--base-dir DIR] [--dict-dir DIR]
          [--categories all|none|person,place,...] [--exclude-categories unclassified]
          [--no-system] [--format table|json]
        research prepare|bulk|pilot|run|status|explain|review-export|import-review|complete-source-search|select-gold|freeze-gold|accept|finalize|export [--ledger path]
          pilot|run: direct reference checks offline by default [--online] [--batch-size 100]
          review-export --output JSON [--batch-size 100] [--id ID] [--surface TEXT] [--reason REASON] [--after-id ID]
          import-review --input JSON
          complete-source-search --source-staging SQLITE (requires complete imported corpus coverage)
          select-gold --input JSON (independent candidateId/split cohort before labels)
          Additional online research is bounded; local models are not required.
        Categories: ${publishedCategories.joinToString(",")}
        Exit codes: 0 success, 1 test mismatch/no conversion, 2 input/configuration error,
          3 research has unresolved review or processing failures.
    """.trimIndent()
}
