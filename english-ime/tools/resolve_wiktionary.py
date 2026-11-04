"""Resolve local Wiktionary references; preserve source rows and case corrections.

No network access. Entry/sense identities stay separate. Spelling equivalents
are not inflections; uncertain senses and multiple case candidates stay pending.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

BAD = pipeline.RESTRICTED | {"misspelling", "no-gloss", "error-unknown-tag", "error-unrecognized-form"}
ROLES = dict(pipeline.WIKTIONARY_ROLES, postp="postposition", contraction="contraction", symbol="symbol",
             character="symbol", phrase="phrase", prep_phrase="phrase")
MORPHOLOGY = {"verb_base", "verb_past", "verb_past_participle", "verb_ing", "verb_present_3sg",
              "verb_present_non3sg", "adjective_base", "adjective_comparative", "adjective_superlative",
              "adverb_comparative", "adverb_superlative", "noun_count_singular", "noun_count_plural"}
ADVERB_SENSE_CATEGORIES = {
    "English manner adverbs": "adverb_manner",
    "English frequency adverbs": "adverb_frequency",
    "English point-in-time adverbs": "adverb_time",
    "English time adverbs": "adverb_time",
    "English sentence adverbs": "adverb_sentence",
}


def eligible(row, sense):
    return not (set(row.get("tags", [])) | set(sense.get("tags", []))) & BAD


def identifier(*parts):
    return "wikt-index-" + hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:24]


def provenance(number, row, sense, ordinal):
    result = {"source": "wiktionary", "url": "https://en.wiktionary.org/wiki/" +
            quote(row["word"].replace(' ', '_'), safe='') + "#English", "entryId": number,
            "etymology": row.get("etymology_number", 0), "sense": sense.get("id") or sense.get("senseid") or ordinal,
            "tags": sorted(set(row.get("tags", [])) | set(sense.get("tags", []))),
            "topics": sorted(set(sense.get("topics", []))), "approved": True}
    if sense.get("_referenceRepair"):
        result["referenceRepair"] = sense["_referenceRepair"]
    return result


def categories(row, sense, pos, base=False):
    tags = set(row.get("tags", [])) | set(sense.get("tags", []))
    grammatical = "noun" if pos == "noun_proper" else pos
    result = pipeline.sense_categories(grammatical, tags, sense.get("topics", []), base)
    if pos == "noun_proper":
        result.add("noun_proper")
        labels = set(sense.get("categories", []))
        if labels & {"English given names", "English surnames"}:
            result.add("name_person")
        if any(label in {"en:Countries", "en:National capitals", "en:Islands", "en:Continents"} or
               label.startswith(("en:Cities in ", "en:Towns in ", "en:Villages in ", "en:Places in ",
                                 "en:County seats of ", "en:Rivers in ")) for label in labels):
            result.add("name_place")
    return result


def add(model, key, lemma, surface, values, evidence, pending):
    if "postposition" in values and "postposition" not in model.names:
        model.names.add("postposition")
        model.definitions.append({"category": "postposition", "definition": "Attested adposition following its complement", "examples": "ago"})
    extension.ensure_categories(model, values)
    values = pipeline.constrain_morphology(model, lemma, surface, values, evidence, pending)
    # A supporting lemma does not prove that lemma's infinitive or usage policy.
    if (key, lemma) not in model.forms:
        grammatical = next(role for role in ("noun", "verb", "adjective", "adverb", "pronoun", "determiner",
            "preposition", "postposition", "conjunction", "interjection", "numeral", "particle", "contraction", "abbreviation", "symbol", "phrase")
            if role in {pipeline.role(value) for value in values})
        model.add(key, lemma, lemma, {grammatical},
                  dict(evidence, relation="supporting_lemma", approved=False))
    model.add(key, lemma, surface, values, evidence, approved=True)


def load_closure(index, words):
    records = dict(index.lookup(words))
    visited = set(words)
    for _ in range(12):
        targets = {ref["word"] for row in records.values() for sense in row.get("senses", [])
                   if eligible(row, sense) for kind in ("form_of", "alt_of") for ref in sense.get(kind, [])
                   if "word" in ref} - visited
        if not targets:
            break
        visited.update(targets)
        records.update(index.lookup(targets))
    return sorted(records.items())


def import_records(model, records, wanted, pending, bootstrap_approved=False):
    roots = defaultdict(set)
    if bootstrap_approved:
        # Use independently approved ordinary lexical roles, never contextual
        # name parts, proper-name-only readings, or unapproved supporting lemmas.
        for key, form in model.forms.items():
            if key[0] not in model.approved.get(key[1], set()) or "noun_proper" in model.members[key]:
                continue
            for role in {"noun", "verb", "adjective", "adverb", "pronoun", "determiner", "preposition", "conjunction", "interjection", "numeral", "particle", "contraction", "abbreviation", "symbol", "phrase"} & model.members[key]:
                roots[key[1], role].add(key[0])
    links = []
    variants = []
    counts = Counter()
    for number, row in records:
        surface = row["word"]
        pos = ROLES.get(row.get("pos"))
        if not pos:
            continue
        for ordinal, sense in enumerate(row.get("senses", []), 1):
            if not eligible(row, sense):
                continue
            proof = provenance(number, row, sense, ordinal)
            refs = [ref["word"] for ref in sense.get("form_of", []) if "word" in ref]
            alternatives = [ref["word"] for ref in sense.get("alt_of", []) if "word" in ref]
            if refs:
                links.append((number, ordinal, row, sense, pos, refs, proof))
                continue
            if alternatives:
                variants.append((number, ordinal, row, sense, pos, alternatives, proof))
                continue
            if "form-of" in proof["tags"] or "alt-of" in proof["tags"]:
                continue
            # Modal heads and unlinked contractions have tables/headword labels
            # that do not establish a bare infinitive. Require an attested -ing
            # paradigm or an explicit infinitive before adding verb_base.
            ordinary = pos != "verb" or any(
                {"present", "participle"} <= set(form.get("tags", [])) or
                "gerund" in form.get("tags", []) or
                form.get("form") == surface and "infinitive" in form.get("tags", [])
                for form in row.get("forms", []))
            contracted_auxiliary = (pos == 'verb' and 'English contractions' in sense.get('categories', []) and
                'auxiliary' in proof['tags'] and any(
                    head.get('name') == 'en-head' and head.get('args', {}).get('1') == 'contr' or
                    head.get('name') == 'head' and head.get('args', {}).get('2') == 'verb form'
                    for head in row.get('head_templates', [])))
            if pos == "verb" and not ordinary and not any(
                    head.get("name") == "en-verb" or
                    head.get("name") == "head" and head.get("args", {}).get("2") == "verb"
                    for head in row.get("head_templates", [])) and not contracted_auxiliary:
                continue
            key = identifier(number, ordinal, pos)
            values = categories(row, sense, pos, base=ordinary)
            if contracted_auxiliary:
                values.add('contraction')
                proof = dict(proof, explicitAuxiliaryContractionHead=True)
            if pos == "verb" and not ordinary:
                proof = dict(proof, headwordRoleWithoutInfinitive=True)
            add(model, key, surface, surface, values, proof, pending)
            roots[surface, pipeline.role(pos)].add(key)
            counts["rootSenses"] += 1
            if pos == "verb" and not ordinary:
                counts["verbHeadsWithoutInfinitiveClaim"] += 1
            for form in row.get("forms", []):
                word, tags = form.get("form"), set(form.get("tags", []))
                if not word or word not in wanted or tags & (BAD | {"multiword-construction"}):
                    continue
                inherited = {"countable"} if "countable" in proof["tags"] else set()
                values = pipeline.tagged_categories("noun" if pos == "noun_proper" else pos, tags | inherited)
                if pos == "noun_proper":
                    values.add(pos)
                if not values & MORPHOLOGY:
                    continue
                if word != surface:
                    values.discard("verb_base")
                    values.discard("adjective_base")
                add(model, key, surface, word, values, dict(proof, relation="inflection_table", tags=sorted(tags)), pending)
                roots[word, pipeline.role(pos)].add(key)
                counts["tableForms"] += 1
    # The source proves the lemma spelling and the form's grammar even when it
    # cannot disambiguate the lemma's etymology. Keep an independent, explicitly
    # unresolved-sense lexeme instead of pooling all root inflection flags.
    # Resolve equivalent spellings only against an eligible same-role target.
    # Each target sense remains separate. Misspellings never reach this branch.
    # An explicitly identified written abbreviation is attested even when its
    # expansion is not a headword. Register this role before following spelling
    # references: lowercase `jk` can then refer to the independently attested
    # phrase `JK`, without borrowing an unrelated proper-name interpretation.
    for number, ordinal, row, sense, pos, refs, proof in variants:
        if not set(proof['tags']) & {'abbreviation', 'acronym', 'initialism', 'contraction'}:
            continue
        if pos == 'verb' and any(head.get('args', {}).get('2') == 'verb form' for head in row.get('head_templates', [])):
            continue
        surface = row['word']
        values = categories(row, sense, pos) - MORPHOLOGY
        values.add('contraction' if 'contraction' in proof['tags'] else 'abbreviation')
        key = identifier(number, ordinal, pos, 'attested_abbreviation')
        add(model, key, surface, surface, values, dict(proof, relation='abbreviation_expansion_unresolved', targets=refs), pending)
        roots[surface, pipeline.role(pos)].add(key)
    done = set()
    linked = set()
    relation_keys = {(r["relation"], r["source"], r["target"]) for r in model.relations}
    for _ in range(12):
        progressed = False
        for number, ordinal, row, sense, pos, refs, proof in links:
            slot = number, ordinal
            if slot in linked or len(set(refs)) != 1 or not roots.get((refs[0], pipeline.role(pos))):
                continue
            lemma = refs[0]
            values = categories(row, sense, pos)
            if row["word"] != lemma:
                values -= {"verb_base", "adjective_base"}
            key = identifier(number, ordinal, pos, "form-of", lemma)
            add(model, key, lemma, row["word"], values,
                dict(proof, relation="form_of", lemmaSense="unspecified", target=lemma), pending)
            roots[row["word"], pipeline.role(pos)].add(key)
            linked.add(slot)
            counts["formReferencesResolved"] += 1
            progressed = True
        for number, ordinal, row, sense, pos, refs, proof in variants:
            slot = number, ordinal
            if slot in done or len(set(refs)) != 1:
                continue
            target = refs[0]
            target_ids = roots.get((target, pipeline.role(pos)), set())
            if not target_ids:
                continue
            for target_id in sorted(target_ids):
                target_form = model.forms[target_id, target]
                is_head = target_form["lemma"] == target
                lemma = row["word"] if is_head else target_form["lemma"]
                values = categories(row, sense, pos, base=False)
                if not sense.get("_referenceRepair"):
                    values |= model.members[target_id, target] & MORPHOLOGY
                if not is_head:
                    values -= {"verb_base", "adjective_base"}
                key = identifier(number, ordinal, pos, "spelling", target_id)
                add(model, key, lemma, row["word"], values,
                    dict(proof, relation="spelling_variant", target=target, targetLexeme=target_id), pending)
                roots[row["word"], pipeline.role(pos)].add(key)
            relation = "spelling_variant", row["word"], target
            if row["word"] != target and relation not in relation_keys:
                model.relations.append(dict(zip(("relation", "source", "target", "evidence"), (*relation, proof["url"]))))
                relation_keys.add(relation)
            done.add(slot)
            counts["spellingSensesResolved"] += 1
            progressed = True
        if not progressed:
            break
    counts["unresolvedSpellingSenses"] = len(variants) - len(done)
    counts["unresolvedFormReferences"] = len(links) - len(linked)
    for number, ordinal, row, sense, pos, refs, proof in variants:
        if (number, ordinal) in done or not set(proof["tags"]) & {"abbreviation", "acronym", "initialism", "contraction"}:
            continue
        if pos == "verb" and any(head.get("args", {}).get("2") == "verb form" for head in row.get("head_templates", [])):
            continue
        # A written abbreviation/contraction is directly attested even when its
        # expansion is not itself a dictionary headword. Do not invent an
        # expanded lemma or any inflection flags from that missing reference.
        surface = row["word"]
        values = categories(row, sense, pos) - MORPHOLOGY
        values.add("contraction" if "contraction" in proof["tags"] else "abbreviation")
        key = identifier(number, ordinal, pos, "attested_abbreviation")
        add(model, key, surface, surface, values, dict(proof, relation="abbreviation_expansion_unresolved", targets=refs), pending)
        counts["attestedAbbreviationsWithoutExpansionLemma"] += 1
        pending.append({"surface": surface, "reason": "abbreviation_expansion_reference_pending",
                        "wordAccepted": True, "targets": refs, "evidence": proof})
    return counts


def case_corrections(model, rows, records):
    exact = {row["word"] for _, row in records}
    candidates = defaultdict(set)
    for _, row in records:
        word = row["word"]
        if word != word.lower() and model.approved.get(word):
            candidates[word.lower()].add(word)
    result = []
    for original in rows:
        word = original["surface"]
        targets = candidates.get(word, set())
        if (word in exact or word != word.lower() or model.approved.get(word) or len(targets) != 1):
            continue
        target = next(iter(targets))
        if pipeline.keyboard_reading(target) != original["reading"]:
            continue
        proof = min(item["url"] for key in model.approved[target] for item in model.evidence[key, target])
        result.append({"id": original["id"], "source": word, "target": target,
                       "relation": "case_correction", "evidence": proof})
    return result


def enrich_adverbs(model, records, pending):
    counts = Counter()
    for number, row in records:
        if row.get("pos") != "adv":
            continue
        if any(str(head.get("args", {}).get("2", "")).endswith(" form") for head in row.get("head_templates", [])):
            continue
        for ordinal, sense in enumerate(row.get("senses", []), 1):
            tags = set(row.get("tags", [])) | set(sense.get("tags", []))
            if (not eligible(row, sense) or sense.get("form_of") or sense.get("alt_of") or
                    tags & {"form-of", "alt-of", "comparative", "superlative"}):
                continue
            # Entry-wide categories can cover unrelated senses/POS/etymologies.
            # Import only the explicit categories on this exact adverb sense.
            labels = set(sense.get("categories", [])) & ADVERB_SENSE_CATEGORIES.keys()
            if not labels:
                continue
            values = {"adverb"} | {ADVERB_SENSE_CATEGORIES[label] for label in labels}
            proof = dict(provenance(number, row, sense, ordinal), relation="sense_adverb_subtype", sourceCategories=sorted(labels))
            key = identifier(number, ordinal, "adverb", "subtype")
            add(model, key, row["word"], row["word"], values, proof, pending)
            counts["senseAdverbReadings"] += 1
    return counts


def resolve(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    index = Index(args.index)
    try:
        if args.adverb_subtypes_only:
            words = {row["surface"] for row in rows}
            previous = args.base / "surface-corrections.tsv"
            if previous.is_file():
                words.update(row["target"] for row in pipeline.read_table(previous, "corrections"))
            counts = enrich_adverbs(model, index.lookup(words), pending)
            corrections = []
            sources["adverbSubtypePolicy"] = "explicit sense categories on direct English adverb lemmas only; no entry-wide labels, comparative forms or unverified degree/place mapping"
        else:
            states = [json.loads(line) for line in (args.base / "status.jsonl").read_text().splitlines()]
            wanted = {row["surface"] for row in states if row["decision"] == "pending"}
            folded = list(index.lookup({word for word in wanted if word == word.lower()}, folded=True))
            words = wanted | {row["word"] for _, row in folded}
            records = load_closure(index, words)
            counts = import_records(model, records, words, pending)
            pending_ids = {state["id"] for state in states if state["decision"] == "pending"}
            corrections = case_corrections(model, [row for row in rows if row["id"] in pending_ids], records)
        sources["wiktionaryIndex"] = index.manifest
        sources["wiktionaryResolutionPolicy"] = "explicit same-role form/spelling references; separate entry/sense IDs; case correction only for lowercase input with no exact English entry and one eligible canonical spelling"
        sources["wiktionaryHeadwordPolicy"] = "explicit verb heads without paradigms establish generic verb only; verb-form heads do not unless the exact eligible sense explicitly identifies an auxiliary contraction with a contraction/form head; no infinitive inferred; explicit symbols/phrases retain their types; source-labeled abbreviations can be attested independently of unresolved expansion lemmas"
        for name in index.manifest["notices"]:
            notices[name] = (args.index / name).read_bytes()
    finally:
        index.close()
    previous = args.base / "surface-corrections.tsv"
    if previous.is_file():
        prior = pipeline.read_table(previous, "corrections")
        previous_ids = {item["id"] for item in prior}
        corrections = prior + [item for item in corrections if item["id"] not in previous_ids]
    prior_reviews = args.base / "reviewed-overrides.tsv"
    reviews = pipeline.read_table(prior_reviews, 'decisions') if prior_reviews.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    import tempfile
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reference-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / "inventory.jsonl", args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, correctedRows=len(corrections), includedRows=summary["includedRows"], pendingRows=summary["pendingRows"]), sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "seed", "index", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--adverb-subtypes-only", action="store_true")
    resolve(parser.parse_args())
