"""Attach source-backed vocabulary-domain membership without guessing POS.

Uses headwords only. Published/generated word-family tables do not prove that
every listed plural or verb form exists. Membership is word-level evidence,
separate from lexical readings; adoption still needs independent eligible proof.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

import extend_lexicon as extension
import lexicon_pipeline as pipeline

NGSL_URL = "https://www.newgeneralservicelist.com/new-general-service-list"
BSL_URL = "https://www.newgeneralservicelist.com/business-service-list"
DATA = {
    "NGSL-1.2.txt": ("8056a5252576ddc5a3c2e96b1422eb2bc7991bdc527ecb2e00181fadff51d9dc", "a", 2809, "domain_daily", NGSL_URL),
    "NGSL-supplement.csv": ("7bb4c76cbe43ae87240be4ac7ada370b9e1a0d9d631d8c4430138646965d03f6", None, 52, "domain_daily", NGSL_URL),
    "BSL-1.2.txt": ("8a17b77465ecb382b33af4567ab1427c0950e2c0db8490cb83abf286bf9379ac", "abolish", 1744, "domain_business", BSL_URL),
}
PAGES = {"NGSL-source.html": "292e9b64956b78024fafe408fad0b133d76903323a614fb3b78a8498c862d306",
         "BSL-source.html": "0eda8af0ac8e4eb21d7aa9834a66a35e3beb7618f708a1731dcc646d09c0bf9e"}
NOTICE = """NGSL and BSL derived vocabulary-domain memberships.
NGSL: Browne, C., Culligan, B., and Phillips, J.; BSL: Browne, C. and Culligan, B.
https://www.newgeneralservicelist.com/new-general-service-list
https://www.newgeneralservicelist.com/business-service-list
Creative Commons Attribution-ShareAlike 4.0 International:
https://creativecommons.org/licenses/by-sa/4.0/
Changes: selected exact headwords, kept case and separate word-level domain
identities, joined independently verified lexical readings. No POS/tense flags
were inferred from list membership or from generated word-family expansions.
The BSL download link is labeled 1.2; its header describes 1.0 and its actual
headword count is 1,744. We pin that exact file and do not claim its version or
the advertised 1,700/approximately 1,754 counts are reconciled.
Preserve this attribution, the source links, changes and license on distribution.
"""


def headwords(path, first, count):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if first is None:
            # Do not import the rule-generated inflections in columns 2+.
            words = [(i, row[0].strip()) for i, row in enumerate(csv.reader(stream), 1) if row]
        else:
            lines = stream.read().splitlines()
            start = lines.index(first)
            words = [(i + 1, word.strip()) for i, word in enumerate(lines) if i >= start and word.strip()]
    if (len(words) != count or len({word for _, word in words}) != count or
            any(not re.fullmatch(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", word) for _, word in words)):
        raise ValueError("Unexpected word list structure or headword count")
    return words


def attach(model, name, words, category, url, sha256):
    accepted = 0
    for line, word in words:
        support = sorted(key for key in model.approved.get(word, set()) if any(
            item["source"] in {"curated_seed", "wiktionary", "esdb"} and item.get("approved", True)
            for item in model.evidence[key, word]))
        approved = bool(support)
        key = "domain-list-" + hashlib.sha256(json.dumps([name, word]).encode()).hexdigest()[:24]
        model.add(key, word, word, {category}, {"source": "ngsl_list", "url": url, "file": name,
            "line": line, "sha256": sha256, "headword": word, "scope": "word_level_not_sense_disambiguated",
            "corroboratingLexemes": support, "approved": approved}, approved=approved)
        accepted += approved
    return {"headwords": len(words), "withIndependentEligibleReading": accepted,
            "classificationOnly": len(words) - accepted}


def extend(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    for name, expected in PAGES.items():
        if pipeline.digest(args.lists / name) != expected:
            raise ValueError("Word-list license/source page changed; review before updating pins")
    counts = {}
    records = {}
    for name, (expected, first, count, category, url) in DATA.items():
        if pipeline.digest(args.lists / name) != expected:
            raise ValueError("Word list changed; review before updating pins")
        words = headwords(args.lists / name, first, count)
        counts[name] = attach(model, name, words, category, url, expected)
        records[name] = {"sha256": expected, "sourceUrl": url, "category": category, "headwords": len(words)}
    sources["domainWordLists"] = {"files": records, "sourcePages": PAGES,
        "scope": "exact headwords only; no POS, inflection, derivation or sense-level domain inference",
        "bslVersionConflict": "link 1.2; header 1.0; 1744 actual headwords; version unresolved"}
    for row in model.definitions:
        if row["category"] == "domain_daily":
            row["definition"] = "Everyday/general vocabulary; NGSL headword evidence is word-level, not every sense"
    notices["NGSL-BSL-NOTICE.txt"] = NOTICE.encode()
    correction_path = args.base / "surface-corrections.tsv"
    corrections = pipeline.read_table(correction_path, "corrections") if correction_path.is_file() else []
    reviews = args.base / "reviewed-overrides.tsv"
    summary = pipeline.publish(model, rows, args.base / "inventory.jsonl", args.out, sources, notices, pending,
        reviewed_decisions=reviews if reviews.is_file() else None, allow_input_spellings=True, corrections=corrections)
    print(json.dumps({"wordLists": counts, "includedRows": summary["includedRows"],
                      "excludedRows": summary["excludedRows"], "pendingRows": summary["pendingRows"],
                      "dailySurfaces": summary["categorySurfaces"]["domain_daily"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "seed", "lists", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    extend(parser.parse_args())
