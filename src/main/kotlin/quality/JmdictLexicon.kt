package com.kazumaproject.quality

import java.io.File
import java.text.Normalizer
import java.util.zip.GZIPInputStream
import javax.xml.stream.XMLInputFactory
import javax.xml.stream.XMLStreamConstants

/** Reference only: callers supply existing candidate pairs; no dictionary words are injected. */
object JmdictLexicon {
    val technicalFields = setOf("comp", "chem", "math", "med", "pharm", "physics", "biol", "bot", "anat", "engr", "elec", "electr", "telec", "stat", "logic", "geol", "astron", "law")
    private val nameTypes = mapOf("char" to "character", "company" to "organization", "organization" to "organization", "person" to "person", "given" to "person", "surname" to "person", "place" to "place", "product" to "product", "work" to "work", "ev" to "event")
    private val named = nameTypes.keys + setOf("ship", "unclass")
    private val obsolete = setOf("obs", "arch", "oK", "ok")
    fun reading(value: String) = Normalizer.normalize(value, Normalizer.Form.NFKC).map { if (it in 'ァ'..'ヶ') (it.code - 96).toChar() else it }.joinToString("")
    fun pair(yomi: String, surface: String) = reading(yomi) to Normalizer.normalize(surface, Normalizer.Form.NFKC)
    private data class Element(val name: String, val text: StringBuilder = StringBuilder(), val children: MutableList<Element> = mutableListOf()) {
        fun values(name: String) = children.filter { it.name == name }.map { it.text.toString() }
        fun elements(name: String) = children.filter { it.name == name }
    }
    fun read(file: File, wanted: Set<Pair<String, String>>, visit: (LexicalFact) -> Unit) {
        val factory = XMLInputFactory.newFactory().apply {
            setProperty(XMLInputFactory.SUPPORT_DTD, true)
            setProperty("http://www.oracle.com/xml/jaxp/properties/entityExpansionLimit", "3000000")
            setProperty("http://www.oracle.com/xml/jaxp/properties/totalEntitySizeLimit", "134217728")
            setProperty("http://www.oracle.com/xml/jaxp/properties/maxGeneralEntitySizeLimit", "32768")
            setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES, false)
            setProperty(XMLInputFactory.IS_REPLACING_ENTITY_REFERENCES, true)
            xmlResolver = javax.xml.stream.XMLResolver { _, _, _, _ -> error("External XML resources are forbidden") }
        }
        val tags = mutableMapOf<String, String>()
        val version = sha256(file)
        val input = if (file.name.endsWith(".gz")) GZIPInputStream(file.inputStream()) else file.inputStream()
        input.buffered().use { stream ->
            val reader = factory.createXMLStreamReader(stream, "UTF-8")
            val stack = ArrayDeque<Element>()
            try {
                while (reader.hasNext()) {
                    when (reader.next()) {
                        XMLStreamConstants.DTD -> {
                            val dtd = reader.text
                            @Suppress("UNCHECKED_CAST")
                            val declarations = reader.getProperty("javax.xml.stream.entities") as? List<javax.xml.stream.events.EntityDeclaration>
                            declarations.orEmpty().forEach { declaration ->
                                require(declaration.systemId == null && declaration.publicId == null) { "External entities are forbidden" }
                                declaration.replacementText?.let { tags[it] = declaration.name }
                            }
                            require(!Regex("(?:SYSTEM|PUBLIC)\\s+[\"']").containsMatchIn(dtd)) { "External DTD/entities are forbidden" }
                            Regex("<!ENTITY\\s+([\\w-]+)\\s+\"([^\"]*)\"\\s*>").findAll(dtd).forEach { tags[it.groupValues[2]] = it.groupValues[1] }
                        }
                        XMLStreamConstants.START_ELEMENT -> if (stack.isNotEmpty() || reader.localName == "entry") stack.addLast(Element(reader.localName))
                        XMLStreamConstants.CHARACTERS, XMLStreamConstants.CDATA, XMLStreamConstants.ENTITY_REFERENCE -> if (stack.isNotEmpty()) {
                            val text = reader.text ?: ""; require(stack.last().text.length + text.length <= 1048576) { "Oversized XML element" }; stack.last().text.append(text)
                        }
                        XMLStreamConstants.END_ELEMENT -> if (stack.isNotEmpty()) {
                            val node = stack.removeLast()
                            if (stack.isEmpty()) process(node, tags, wanted, version, visit) else stack.last().children.add(node)
                        }
                    }
                }
            } finally { reader.close() }
        }
    }
    private fun process(entry: Element, codes: Map<String, String>, wanted: Set<Pair<String,String>>, version: String, visit: (LexicalFact) -> Unit) {
        fun tags(node: Element, name: String) = node.values(name).map { codes[it] ?: it }.toSet()
        val spellings = entry.elements("k_ele").associate { it.values("keb").single() to tags(it, "ke_inf") }
        val id = entry.values("ent_seq").single()
        var inheritedPos = emptySet<String>(); var inheritedMisc = emptySet<String>()
        entry.elements("sense").forEachIndexed { index, sense ->
            val explicitPos = tags(sense,"pos"); if (explicitPos.isNotEmpty()) inheritedPos = explicitPos
            val explicitMisc = tags(sense,"misc"); if (explicitMisc.isNotEmpty()) inheritedMisc = explicitMisc
            val fields = tags(sense,"field"); val misc = inheritedMisc; val pos = inheritedPos
            val categories = mutableSetOf<String>()
            nameTypes.forEach { (tag, category) -> if (tag in misc) categories.add(category) }
            if (fields.contains("food")) categories.add("food")
            if (fields.any { it in technicalFields }) categories.add("technical")
            if (fields.isEmpty() && pos.any { it in setOf("n", "n-adv", "n-t") } && pos.none { it in setOf("n-pr", "unc") } && misc.none { it in named || it == "rare" }) categories.add("general")
            // Individually reviewed senses whose POS alone incorrectly suggests a common noun.
            when (id to (index+1)) {
                "5708730" to 1 -> { categories.clear(); categories.add("work") }
                "2248830" to 1 -> { categories.clear(); categories.add("work") }
                "2399700" to 1 -> { categories.clear(); categories.add("food") }
                "2399700" to 2 -> { categories.clear(); categories.add("character") }
            }
            val stagk = sense.values("stagk").toSet(); val stagr = sense.values("stagr").toSet()
            entry.elements("r_ele").forEach { r ->
                val yomi = r.values("reb").single(); if (stagr.isNotEmpty() && yomi !in stagr) return@forEach
                val restricted = r.values("re_restr").toSet()
                val eligible = if (r.elements("re_nokanji").isNotEmpty()) emptyMap() else spellings.filterKeys { restricted.isEmpty() || it in restricted }
                (eligible + (yomi to emptySet())).forEach spellingLoop@ { (surface, spellingInfo) ->
                    if (stagk.isNotEmpty() && surface !in stagk) return@spellingLoop
                    if (pair(yomi,surface) !in wanted || (spellingInfo + tags(r,"re_inf") + misc).any { it in obsolete }) return@spellingLoop
                    val evidence = "https://www.edrdg.org/jmdict/edict_doc.html#entry-$id-sense-${index+1}"
                    visit(LexicalFact(reading(yomi), Normalizer.normalize(surface,Normalizer.Form.NFKC), categories, evidence, id, fields, pos, version, "JMdict", misc, sense.values("gloss")))
                }
            }
        }
    }
}
