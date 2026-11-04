"""Resolve pending source rows using pinned sources and finite review policies.

Case alternatives are predictions, not a guess about the intended entity. An
exclusion requires explicit labels on every English sense in the snapshot and
no independently approved modern exact-surface interpretation. No network.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import tempfile
from urllib.parse import quote

import extend_lexicon as extension
import lexicon_pipeline as pipeline
from wiktionary_index import Index


def esdb_case_words(directory, words):
    # import_esdb validates the manifest/database/notice hashes before use.
    connection = sqlite3.connect((directory / "esdb.db").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return {word for word, in connection.execute("select distinct word from entries") if word.lower() in words}
    finally:
        connection.close()


def ineligible_exact_words(records):
    """Require an explicit disqualifying label on every attested exact sense.

    Missing glosses, extraction errors and absent entries establish nothing.
    """
    entries = defaultdict(list)
    for _, row in records:
        entries[row['word']].append(row)
    result = set()
    for word, values in entries.items():
        if any(not row.get('senses') for row in values):
            continue
        labels = [set(row.get('tags', [])) | set(sense.get('tags', []))
                  for row in values for sense in row['senses']]
        if (all(tags & (pipeline.RESTRICTED | {'misspelling'}) for tags in labels) and
                not any(tags & {'no-gloss', 'error-unknown-tag', 'error-unrecognized-form'} for tags in labels)):
            result.add(word)
    return result


def cases(model, rows, exact_english, explicitly_ineligible=()):
    blocking_exact = exact_english - set(explicitly_ineligible)
    by_reading = defaultdict(set)
    for surface, identifiers in model.approved.items():
        if identifiers and surface != surface.lower():
            by_reading[surface.lower()].add(surface)
    result = []
    for row in rows:
        word = row["surface"]
        # Preserve modern exact readings. A disqualified historical/typo reading
        # does not invalidate independently attested canonical names. These are
        # alternative interpretations, never a claim about corpus sense counts.
        if (word != word.lower() or word in blocking_exact or
                model.approved.get(word)):
            continue
        targets = sorted(target for target in by_reading[word]
                         if pipeline.keyboard_reading(target) == row["reading"])
        relation = "case_correction" if len(targets) == 1 else "case_candidates"
        for target in targets:
            url = min(item["url"] for key in model.approved[target] for item in model.evidence[key, target]
                      if item.get("approved", True))
            result.append({"id": row["id"], "source": word, "target": target, "relation": relation, "evidence": url})
    return result


def exclusions(model, rows, records, mapped_ids, pending):
    by_word = defaultdict(list)
    for number, row in records:
        by_word[row["word"]].append((number, row))
    result = []
    canonical = defaultdict(set)
    for surface, identifiers in model.approved.items():
        if identifiers and surface != surface.lower():
            canonical[surface.lower()].add(surface)
    for original in rows:
        word = original["surface"]
        if original["id"] in mapped_ids or model.approved.get(word):
            continue
        entries = by_word[word]
        if not entries or any(not entry.get("senses") for _, entry in entries):
            continue
        labels = [set(entry.get("tags", [])) | set(sense.get("tags", []))
                  for _, entry in entries for sense in entry["senses"]]
        if any(tags & {"no-gloss", "error-unknown-tag", "error-unrecognized-form"} for tags in labels):
            continue
        reason = ("restricted" if all(tags & pipeline.RESTRICTED for tags in labels) else
                  "malformed" if all("misspelling" in tags for tags in labels) else
                  "ineligible_senses" if all(tags & (pipeline.RESTRICTED | {'misspelling'}) for tags in labels) else None)
        if not reason:
            continue
        alternatives = sorted(surface for surface in canonical[word]
                              if pipeline.keyboard_reading(surface) == original["reading"])
        if alternatives:
            # Lowercase `taylor` has an obsolete lexical reading while `Taylor`
            # is a modern name. Its source frequency/cost does not tell us which
            # reading was intended. Do not delete the name or transfer the cost
            # to another sense automatically.
            pending.append({"sourceId": original["id"], "surface": word,
                            "reason": "restricted_surface_has_eligible_case_alternative",
                            "candidateSurfaces": alternatives, "sourceLabelReason": reason})
            continue
        url = "https://en.wiktionary.org/wiki/" + quote(word.replace(' ', '_'), safe='') + "#English"
        result.append(dict(original, decision="exclude", lexeme_ids="-", reason=reason, evidence=url))
        pending.append({"sourceId": original["id"], "surface": word, "reason": "source_label_exclusion",
                        "decisionReason": reason, "evidence": {"source": "wiktionary", "url": url,
                        "entries": [{"entryId": number, "pos": entry.get("pos"),
                                     "senseTags": [sorted(set(entry.get("tags", [])) | set(s.get("tags", [])))
                                                   for s in entry["senses"]]} for number, entry in entries]}})
    return result


def revalidate_machine_reviews(model, reviews, pending):
    """Reopen generated exclusions when later sources contradict their policy.

    A human override is not silently removed. Only rows with a matching audit
    record from this tool's source-label exclusion policy are eligible.
    """
    generated = {(event.get("sourceId"), event.get("surface"), event.get("decisionReason"), event.get("evidence", {}).get("url"))
                 for event in pending if event.get("reason") == "source_label_exclusion"}
    canonical = defaultdict(set)
    for surface, identifiers in model.approved.items():
        if identifiers:
            canonical[surface.lower()].add(surface)
    kept, reopened = [], []
    for review in reviews:
        key = review["id"], review["surface"], review["reason"], review["evidence"]
        alternatives = sorted(surface for surface in canonical[review["surface"].lower()]
                              if surface == review["surface"] or pipeline.keyboard_reading(surface) == review["reading"])
        if review["decision"] == "exclude" and key in generated and alternatives:
            reopened.append(review["id"])
            pending.append({"sourceId": review["id"], "surface": review["surface"],
                            "reason": "machine_exclusion_reopened_after_new_evidence",
                            "previousDecision": dict(review), "eligibleSurfaces": alternatives})
        else:
            kept.append(review)
    return kept, set(reopened)


def resolve(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(line) for line in (args.base / "status.jsonl").read_text().splitlines()]
    prior_path = args.base / "reviewed-overrides.tsv"
    previous_reviews = pipeline.read_table(prior_path, "decisions") if prior_path.is_file() else []
    previous_reviews, reopened = revalidate_machine_reviews(model, previous_reviews, pending)
    unresolved = [row for row, state in zip(rows, states) if state["decision"] == "pending" or row["id"] in reopened]
    wanted = {row["surface"] for row in unresolved}
    expanded = wanted | esdb_case_words(args.esdb, wanted)
    manifest, imported = extension.import_esdb(model, expanded, args.esdb, pending)
    previous_reviews, newly_reopened = revalidate_machine_reviews(model, previous_reviews, pending)
    reopened.update(newly_reopened)
    if newly_reopened:
        unresolved = [row for row, state in zip(rows, states) if state["decision"] == "pending" or row["id"] in reopened]
        wanted = {row["surface"] for row in unresolved}
    sources["esdbCaseLookup"] = {key: manifest[key] for key in ("revision", "databaseSha256", "recipe")}
    index = Index(args.index)
    try:
        records = list(index.lookup(wanted))
        sources["pendingReviewSnapshot"] = index.manifest["snapshotSha256"]
    finally:
        index.close()
    correction_path = args.base / "surface-corrections.tsv"
    corrections = pipeline.read_table(correction_path, "corrections") if correction_path.is_file() else []
    ineligible = ineligible_exact_words(records)
    additions = cases(model, unresolved, {row["word"] for _, row in records}, ineligible)
    for original in unresolved:
        alternatives = [item['target'] for item in additions if item['id'] == original['id']]
        if original['surface'] in ineligible and alternatives:
            pending.append({'sourceId': original['id'], 'surface': original['surface'],
                'reason': 'eligible_case_interpretations_with_disqualified_exact_readings',
                'candidateSurfaces': alternatives, 'corpusSenseDisambiguated': False})
    corrections += additions
    reviews = exclusions(model, unresolved, records, {row["id"] for row in corrections}, pending)
    reviews = previous_reviews + reviews
    sources["pendingResolutionPolicy"] = {
        "case": "all verified canonical alternatives; absent exact entry or every exact sense explicitly restricted/misspelled; no eligible exact reading; retain ambiguity, original rows and costs",
        "exclude": "every English sense explicitly restricted or misspelled, including mixed labels; no eligible exact or case-alternative interpretation",
        "absence": "never an exclusion reason"}
    sources["pendingResolutionPolicy"]["reviewRefresh"] = "reopen only audited machine exclusions contradicted by current eligible exact/case evidence; preserve human overrides"
    for name in manifest["notices"]:
        notices[name] = (args.esdb / name).read_bytes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".source-review-", dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / "reviewed.tsv"
        pipeline.table(reviewed, "decisions", reviews)
        summary = pipeline.publish(model, rows, args.base / "inventory.jsonl", args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps({"esdbRecordsImported": imported, "newCaseRows": len({row["id"] for row in additions}),
                      "machineExclusionsReopened": len(reopened),
                      "newCaseCandidates": len(additions), "exclusionReasons": dict(Counter(row["reason"] for row in reviews)),
                      "includedRows": summary["includedRows"], "excludedRows": summary["excludedRows"],
                      "pendingRows": summary["pendingRows"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "seed", "esdb", "index", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    resolve(parser.parse_args())
