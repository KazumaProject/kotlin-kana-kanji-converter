"""Resolve pending rows using pinned local lexical sources and explicit rules."""
import argparse
from collections import defaultdict
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import lexicon_pipeline as pipeline
from prepare_esdb import REVISION, URL

EXTRA_CATEGORIES = {
    "orthography_existing_manual_alias": ("Reviewed existing manual case/space or explicitly reviewed space/hyphen alias of an independently approved ordinary English head; no externally attested raw spelling, preferred name or inferred word-boundary claim", "existing compact display aliases"),
    "identifier_taxonomic_name": ("Explicitly reviewed scientific taxon label; no ordinary English POS or inherited inflection claim", "documented genus and taxon names"),
    "identifier_programming_keyword": ("Explicitly identified programming-language keyword; no ordinary English POS or inflection implied", "foreach"),
    "identifier_markup_attribute": ("Explicitly identified markup-language attribute name; no ordinary English POS or inflection implied", "href"),
    "contraction": ("Contracted written form; expansions are separate spelling relations", "can't, don't, I'm"),
    "noun_possessive_singular": ("Singular noun genitive explicitly recorded in a source", "dog's, child's"),
    "noun_possessive_plural": ("Plural noun genitive explicitly recorded in a source", "dogs', children's"),
    "register_nonstandard": ("Usage explicitly labeled nonstandard; no automatic normalization", "ain't"),
    "pronoun_plural": ("Pronoun explicitly marked plural; grammatical case is separate", "we, these"),
    "numeral_roman": ("Roman numeral explicitly listed in the source; no cardinal/ordinal inference", "iii, vi, xvi"),
    "symbol": ("Written symbol explicitly identified in an English source entry", "fm"),
    "phrase": ("Fixed expression explicitly identified as a phrase; syntax remains separate", "kk"),
    "identifier_computer_language": ("Canonical language/format label in GitHub Linguist; no lexical POS or inflection inference", "C#, GraphQL, Markdown"),
    "identifier_command_line": ("Exact command name or literal expression in English command documentation; no lexical POS or inflection inference", "git status, npm install"),
    "identifier_command_prefix": ("Documented literal command prefix; may require arguments or completion; no execution or lexical POS claim", "git commit -m, pip install -r"),
    "name_brand": ("Documented brand or explicit brand alias; company/product type and lexical inflections remain separate", "SpaceX, Next.js, Google Sheets"),
    "name_work": ("Attested title or alias of a specific creative work, including documented software; no inflection inference", "documented book, film or software titles"),
    "identifier_data_format": ("Documented data/file-format identifier or alias; no lexical POS or inflection inference", "documented file-format labels"),
    "identifier_programming_api": ("Case-sensitive public programming API type or explicitly reviewed exported function identifier; qualified module context retained without English POS or inflection inference", "InputConnection, Coroutine, ViewModel, NextAuth"),
    "identifier_command_template": ("Existing manual syntactic instantiation of a documented command template; argument values do not prove installed packages or existing project scripts", "npm run dev, black ."),
    "identifier_phonetic_code": ("Explicit NATO/ICAO phonetic-codeword reading; no month or personal-name sense inference", "november, zulu"),
    "orthography_informal_ing": ("Derived informal final-written-g omission from a verified English -ing verb form, with the original lemma and participle use", "drinkin, huntin"),
    "phrase_noun_compositional": ("Existing manual label with verified noun/adjective modifiers and noun head; productive phrase, without a claim of lexicalized fixed-expression attestation", "wire number, safety relay"),
    "orthography_initial_capital": ("Derived initial-capital spelling of a verified ordinary English form; no proper-name or preferred case claim", "Compose, Coroutines"),
    "orthography_expressive_lengthening": ("Derived informal repeated-letter spelling of an independently verified English form; no claim of individual attestation or inherited inflection flags", "soooo, loooong"),
    "identifier_named_component": ("Whole attested word within a verified English proper name; requires named context, with no standalone name, English POS or inflection claim", "Phnom in Phnom Penh, Moines in Des Moines"),
    "identifier_software_catalog": ("Published software catalog slug or explicit alternate identifier; no lexical POS or preferred vendor spelling claim", "jupyterlab, junit"),
    "name_fictional": ("Attested name of a fictional character, species, place, object or material; no real-person, biological-species or real-world existence claim", "Bulbasaur, Charizard, Alola, Vibranium"),
}


def ensure_categories(model, categories):
    for name in sorted(categories - model.names):
        definition, examples = EXTRA_CATEGORIES[name]
        model.definitions.append({"category": name, "definition": definition, "examples": examples})
        model.names.add(name)


def load_base(directory, seed):
    started = time.monotonic()
    def progress(phase, count=None):
        if os.environ.get('ENGLISH_LEXICON_PROGRESS') == '1':
            record = {'event':'load_base','phase':phase,'elapsedSeconds':round(time.monotonic()-started,1)}
            if count is not None: record['records'] = count
            print(json.dumps(record,sort_keys=True),file=sys.stderr,flush=True)
    progress('verify')
    pipeline.verify(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, expected in manifest["sources"]["seed"].items():
        if pipeline.digest(seed / (name + ".tsv")) != expected:
            raise ValueError("Curated seed changed since the base materialization")
    progress('tables')
    model = pipeline.Lexicon(directory / "grammar")
    curated = pipeline.Lexicon(seed)
    model.seed_morphology = curated.seed_morphology
    model.seed_surfaces = curated.seed_surfaces
    model.approved = defaultdict(set)
    model.evidence = defaultdict(list)
    progress('evidence',0)
    with (directory / "evidence.jsonl").open(encoding='utf-8') as stream:
        for number,line in enumerate(stream,1):
            record = json.loads(line)
            key = record["lexeme_id"], record["surface"]
            if key not in model.forms or key in model.evidence:
                raise ValueError("Changed or duplicate lexical evidence")
            model.evidence[key] = record["evidence"]
            if any(item["source"] in {"curated_seed", "wiktionary", "esdb", "ngsl_list", "software_registry", "geonames", "tldr_command", "english_namenet", "census_surname", "dbpedia14_title", "verified_manual_name_case", "documented_command_prefix", "brand_metadata", "verified_contraction_case", "yago_english_name", "public_api_identifier", "documented_command_template", "standard_roman_numeral", "yago_name_variant", "public_technology_catalog", "yago_named_component", "expressive_orthography", "verified_initial_capital", "official_product_label", "official_reference_label", "compositional_manual_noun_phrase", "research_attested_abbreviation", "derived_informal_ing", "historical_ssa_given_name", "reviewed_english_usage", "reviewed_wikipedia", "reviewed_manual_lexical_alias", "published_reference_label", "reviewed_lexical_entry"} and item.get("approved", True) and not item.get("requiresFullNamedContext", False)
                   or item["source"] in {"reviewed_official_command_example", "reviewed_formal_command_prefix", "reviewed_public_api_function", "reviewed_tatoeba_interjection"} and item.get("approved", True) and not item.get("requiresFullNamedContext", False)
                   for item in record["evidence"]):
                model.approved[key[1]].add(key[0])
            if number % 100000 == 0: progress('evidence',number)
    if set(model.evidence) != set(model.forms):
        raise ValueError("Missing lexical evidence")
    rows = pipeline.inventory(directory / "inventory.jsonl")
    pending = [json.loads(line) for line in (directory / "pending-evidence.jsonl").read_text().splitlines()]
    notices = {path.name: path.read_bytes() for path in (directory / "notices").iterdir() if path.is_file()}
    sources = copy.deepcopy(manifest["sources"])
    sources["baseMaterializationSha256"] = pipeline.digest(directory / "manifest.json")
    progress('ready',len(model.forms))
    return model, rows, sources, notices, pending


def wordnet_roles(model):
    result = defaultdict(set)
    for (_, surface), records in model.evidence.items():
        for record in records:
            if record["source"] != "wordnet_3.0":
                continue
            member = record["member"].split('/')[-1]
            for suffix, role in pipeline.WORDNET_ROLES.items():
                if member in {"index." + suffix, suffix + ".exc"}:
                    result[surface].add(role)
    return result


def roles_for(base_pos, pos):
    if base_pos in {"n", "pl"}:
        return {"noun"}
    if base_pos == "v":
        return {"verb"}
    if base_pos == "n_v":
        if pos in {"m0", "ms"}:
            return {"noun", "verb"}
        return {"noun"} if pos.startswith('n') else {"verb"}
    if base_pos == "aj_av":
        return {"adjective", "adverb"}
    return {"aj": {"adjective"}, "av": {"adverb"}, "pn": {"pronoun"}, "c": {"conjunction"},
            "pp": {"preposition"}, "d": {"determiner"}, "i": {"interjection"},
            "abbr": {"abbreviation"}, "s": {"contraction"}}.get(base_pos, set())


def categories_for(record, role, paradigm):
    pos = record["pos"]
    categories = {role}
    if role == "noun":
        if pos in {"np", "nsp", "nssp"}:
            categories.add("noun_possessive_singular" if pos == "np" else "noun_possessive_plural")
        elif record["base_pos"] == "pl":
            categories.add("noun_plural_only")
        elif pos in {"ns", "nss", "ms"}:
            categories.add("noun_count_plural")
        elif pos in {"n0", "m0"} and paradigm & {"ns", "ms"}:
            categories.add("noun_count_singular")
        if record["pos_class"] in {"name", "person", "surname", "place"}:
            categories.add("noun_proper")
        if record["pos_class"] in {"person", "surname"}:
            categories.add("name_person")
        elif record["pos_class"] == "place":
            categories.add("name_place")
    elif role == "verb":
        # A defective modal's dictionary headword (may/can/shall) is not an
        # infinitive. The full inflectional paradigm distinguishes these groups.
        ordinary = 'vg' in paradigm
        if pos in {"v0", "m0"} and ordinary:
            categories.add("verb_base")
            if record["lemma"] != "be" and paradigm & {"vs", "ms"}:
                categories.add("verb_present_non3sg")
        elif pos == "vd":
            categories.add("verb_past")
        elif pos == "vn":
            categories.add("verb_past_participle")
        elif pos == "vg":
            categories.add("verb_ing")
        elif pos in {"vs", "ms"} and ordinary and record["lemma"] != "be":
            categories.add("verb_present_3sg")
    elif role in {"adjective", "adverb"}:
        number = pos[-1:]
        if number in {"0", "1", "2"}:
            suffix = {"0": "base", "1": "comparative", "2": "superlative"}[number]
            if role == "adjective" or number != "0":
                categories.add(role + '_' + suffix)
    elif role == "pronoun":
        categories.update({"pn1": {"pronoun_object"}, "pnd": {"det_possessive"}, "pnp": {"pronoun_possessive"},
                           "pnr0": {"pronoun_reflexive"}, "pnrs": {"pronoun_reflexive"},
                           "pns": {"pronoun_plural"}}.get(pos, set()))
    if record["usage_note"] in {"colloquial", "informal"}:
        categories.add("register_informal")
    elif record["usage_note"] == "nonstandard":
        categories.add("register_nonstandard")
    return categories


def import_esdb(model, wanted, directory, pending):
    manifest = json.loads((directory / "manifest.json").read_text())
    if (manifest["schemaVersion"] != 1 or manifest["revision"] != REVISION or
            manifest["recipe"] != "combine.py create-db --raw; omit data/coca_llm merge" or
            pipeline.digest(directory / "esdb.db") != manifest["databaseSha256"]):
        raise ValueError("Changed or unapproved ESDB database")
    for name, expected in manifest["notices"].items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError("Changed ESDB notice")
    wn_roles = wordnet_roles(model)
    connection = sqlite3.connect((directory / "esdb.db").resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("pragma temp_store=memory")
        connection.execute("create temp table targets (word text primary key)")
        connection.executemany("insert into targets values (?)", [(word,) for word in sorted(wanted)])
        query = """select e.*,s.size,s.category,s.tag,s.spelling,s.variant_level
          from scowl_ s join entries e using(word_id) join targets t on s.word=t.word
          where s.size<=80 and s.variant_level<=6 and s.group_rank not in ('@','~')
            and s.entry_rank not in ('@','~') and s.usage_note not like 'vulgar%'
            and s.usage_note not like 'offensive%'"""
        records = {}
        for value in connection.execute(query):
            row = dict(value)
            current = records.setdefault(row["word_id"], row | {"sourceLines": []})
            current["sourceLines"].append({key: row[key] for key in ("size", "tag", "category", "spelling", "variant_level")})
        connection.execute("create temp table families (lemma_id integer primary key)")
        connection.executemany("insert into families values (?)", [(number,) for number in sorted({r["lemma_id"] for r in records.values()})])
        paradigms = defaultdict(set)
        for row in connection.execute("""select distinct lemma_id,pos from scowl_ join families using(lemma_id)
                where size<=60 and variant_level<=6 and group_rank not in ('@','~')
                  and entry_rank not in ('@','~') and usage_note not like 'vulgar%'
                  and usage_note not like 'offensive%'"""):
            paradigms[row["lemma_id"]].add(row["pos"])
        imported = 0
        for record in sorted(records.values(), key=lambda row: row["word_id"]):
            roles = roles_for(record["base_pos"], record["pos"])
            roman = record["base_pos"] == "x" and any(line["category"] == "roman-numerals" for line in record["sourceLines"])
            if roman:
                roles = {"numeral"}
            if not roles:
                continue  # m/a are explicitly uncertain POS assignments upstream.
            lines = record["sourceLines"]
            vetted = any(line["size"] <= 60 and line["tag"] not in {"[ukfreq]", "[stale]", "[ukacd]", "[plurals]", "[-]"} for line in lines)
            medium = any(line["size"] <= 70 and line["tag"] not in {"[ukfreq]", "[stale]", "[ukacd]", "[plurals]", "[-]"} for line in lines)
            for role in sorted(roles):
                approved = vetted or medium and role in wn_roles[record["word"]]
                identifier = f"esdb-{record['group_id']}-{record['lemma_id']}-{role}"
                evidence = {"source": "esdb", "url": URL, "wordId": record["word_id"], "groupId": record["group_id"],
                            "lemmaId": record["lemma_id"], "pos": record["pos"], "basePos": record["base_pos"],
                            "definitionNote": record["defn_note"], "usageNote": record["usage_note"],
                            "sourceLines": lines, "approved": approved}
                categories = categories_for(record, role, paradigms[record["lemma_id"]]) if approved else {role}
                if roman:
                    categories.add("numeral_roman")
                categories = pipeline.constrain_morphology(model, record["lemma"], record["word"], categories, evidence, pending)
                ensure_categories(model, categories)
                if (identifier, record["lemma"]) not in model.forms:
                    model.add(identifier, record["lemma"], record["lemma"], {role},
                              dict(evidence, relation="supporting_lemma", approved=False))
                model.add(identifier, record["lemma"], record["word"], categories, evidence, approved=approved)
                imported += 1
    finally:
        connection.close()
    return manifest, imported


def extend(args):
    model, rows, sources, notices, pending = load_base(args.base, args.seed)
    manifest, imported = import_esdb(model, {row["surface"] for row in rows}, args.esdb, pending)
    sources["esdb"] = {key: manifest[key] for key in ("revision", "url", "recipe", "databaseSha256")}
    sources["esdb"]["policy"] = "size<=60 vetted sources; size<=70 with matching WordNet role; other matches classification only"
    for name in manifest["notices"]:
        notices[name] = (args.esdb / name).read_bytes()
    notices["ESDB-CHANGES.txt"] = ("Derived named dictionaries with separate lexeme, inflection and spelling relationships.\n"
        "Preserved source group/lemma/word IDs; omitted data/coca_llm; retained raw source tags.\n"
        "Filtered archaic, inapplicable, offensive and vulgar entries and invalid variants.\n"
        "Higher-size matches require corroboration for adoption; pending original rows are retained.\n").encode()
    prior_reviews = args.base / "reviewed-overrides.tsv"
    correction_path = args.base / "surface-corrections.tsv"
    corrections = pipeline.read_table(correction_path, "corrections") if correction_path.is_file() else []
    result = pipeline.publish(model, rows, args.base / "inventory.jsonl", args.out, sources, notices, pending,
                              reviewed_decisions=prior_reviews if prior_reviews.is_file() else None,
                              allow_input_spellings=True, corrections=corrections)
    print(json.dumps({"esdbLexicalRecordsImported": imported, "includedRows": result["includedRows"],
                      "pendingRows": result["pendingRows"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "seed", "esdb", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    extend(parser.parse_args())
