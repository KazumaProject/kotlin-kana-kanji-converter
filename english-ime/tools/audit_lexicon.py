"""Audit all excluded rows and accepted daily surfaces against pinned sources.

This checks source joins and explicit decision rules, not the completeness of
all possible English senses or an independent semantic review of every word.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import domain_wordlists as domains
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_wiktionary as resolver
from wiktionary_index import Index


def records(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def independently_eligible(evidence, word_evidence):
    wn_roles = {pipeline.WORDNET_ROLES[suffix] for suffix in pipeline.WORDNET_ROLES
                for item in word_evidence if item["source"] == "wordnet_3.0" and
                item["member"].split('/')[-1] in {"index." + suffix, suffix + ".exc"}}
    for item in evidence:
        if not item.get("approved", True) or not item.get("url", "").startswith("https://"):
            continue
        if item["source"] == "curated_seed":
            return True
        if item["source"] == "wiktionary" and not set(item.get("tags", [])) & resolver.BAD:
            return True
        if item["source"] != "esdb" or item.get("usageNote", "").startswith(("vulgar", "offensive")):
            continue
        lines = [line for line in item.get("sourceLines", []) if line["variant_level"] <= 6 and
                 line["tag"] not in {"[ukfreq]", "[stale]", "[ukacd]", "[plurals]", "[-]"}]
        if any(line["size"] <= 60 for line in lines) or any(line["size"] <= 70 for line in lines) and (
                extension.roles_for(item["basePos"], item["pos"]) & wn_roles):
            return True
    return False


def audit(directory, index_path, lists):
    summary = pipeline.verify(directory)
    decisions = pipeline.read_table(directory / "decisions.tsv", "decisions")
    states = list(records(directory / "status.jsonl"))
    daily_keys = {(row["lexeme_id"], row["surface"]) for row in pipeline.read_table(directory / "grammar/memberships.tsv", "memberships")
                  if row["category"] == "domain_daily"}
    accepted_daily = set()
    for decision, state in zip(decisions, states):
        if decision["decision"] == "include":
            surfaces = state.get("effective_surfaces", [state.get("effective_surface", state["surface"])])
            accepted_daily.update(surface for key in decision["lexeme_ids"].split(',') for surface in surfaces if (key, surface) in daily_keys)
    excluded = [row for row in decisions if row["decision"] == "exclude"]
    selected = accepted_daily | {row["surface"] for row in excluded}
    evidence = {}
    canonical = defaultdict(set)
    for row in records(directory / "evidence.jsonl"):
        if any(item["source"] in {"curated_seed", "wiktionary", "esdb", "ngsl_list", "software_registry", "geonames", "tldr_command"} and
               item.get("approved", True) for item in row["evidence"]):
            canonical[row["surface"].lower()].add(row["surface"])
        if row["surface"] in selected:
            evidence[row["lexeme_id"], row["surface"]] = row["evidence"]
    per_word = defaultdict(list)
    for (_, word), items in evidence.items():
        per_word[word].extend(items)
    source_heads = {}
    for name, (sha, first, count, _, _) in domains.DATA.items():
        if pipeline.digest(lists / name) != sha:
            raise ValueError("Changed domain-list source")
        source_heads[name] = dict(domains.headwords(lists / name, first, count))
    daily_issues = []
    for word in sorted(accepted_daily):
        proofs = []
        for (key, surface), items in evidence.items():
            if surface != word:
                continue
            for item in items:
                if item["source"] != "ngsl_list" or item.get("file", "").startswith("BSL"):
                    continue
                source_ok = (item.get("sha256") == domains.DATA[item["file"]][0] and
                             source_heads[item["file"]].get(item["line"]) == word and
                             item.get("headword") == word and item.get("scope") == "word_level_not_sense_disambiguated")
                supports = item.get("corroboratingLexemes", [])
                support_ok = bool(supports) and all(independently_eligible(evidence.get((identifier, word), []), per_word[word])
                                                    for identifier in supports)
                proofs.append(source_ok and support_ok and item.get("approved") is True)
        if not proofs or not any(proofs):
            daily_issues.append({"surface": word, "reason": "missing_or_uncorroborated_exact_headword_proof"})
    index = Index(index_path)
    english = defaultdict(list)
    try:
        for number, row in index.lookup({row["surface"] for row in excluded}):
            english[row["word"]].append((number, row))
    finally:
        index.close()
    exclusion_issues = []
    for review in excluded:
        entries = english[review["surface"]]
        tags = [set(entry.get("tags", [])) | set(s.get("tags", [])) for _, entry in entries for s in entry.get("senses", [])]
        labels_ok = (bool(tags) and all(entry.get("senses") for _, entry in entries) and
                     not any(t & {"no-gloss", "error-unknown-tag", "error-unrecognized-form"} for t in tags) and
                     (review["reason"] == "restricted" and all(t & pipeline.RESTRICTED for t in tags) or
                      review["reason"] == "malformed" and all("misspelling" in t for t in tags)))
        alternatives = sorted(word for word in canonical[review["surface"].lower()] if word == review["surface"] or
                              pipeline.keyboard_reading(word) == review["reading"])
        if not labels_ok or alternatives:
            exclusion_issues.append({"id": review["id"], "surface": review["surface"],
                                     "labelsMatchPolicy": bool(labels_ok), "currentEligibleSpellings": alternatives})
    return {"inputRowsPreservedAndHashed": summary["inputRows"], "acceptedDailySurfacesChecked": len(accepted_daily),
            "acceptedDailySourceJoinIssues": daily_issues, "exclusionsChecked": len(excluded), "exclusionIssues": exclusion_issues,
            "scope": "all selected daily surfaces and all excluded rows; source/rule audit, not proof of complete semantic classification"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("directory", "index", "lists", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory, args.index, args.lists)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    if result["exclusionIssues"] or result["acceptedDailySourceJoinIssues"]:
        raise SystemExit(1)
