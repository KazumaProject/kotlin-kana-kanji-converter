"""Offline dictionary evidence and proposal batches. All paths are local."""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

WORDNET_SHA256 = "640db279c949a88f61f851dd54ebbb22d003f8b90b85267042ef85a3781d3a52"
WORDNET_ROLES = {"noun": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb"}
WIKTIONARY_ROLES = {
    "noun": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb",
    "name": "noun_proper", "pron": "pronoun", "det": "determiner", "article": "det_article",
    "prep": "preposition", "conj": "conjunction", "intj": "interjection", "num": "numeral",
    "particle": "particle", "abbrev": "abbreviation",
}
RESTRICTED = {"archaic", "obsolete", "offensive", "derogatory", "vulgar", "slur", "proscribed"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def read_inventory(path):
    rows = list(read_jsonl(path))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate inventory ID")
    return rows


def wordnet(path, surfaces):
    if digest(path) != WORDNET_SHA256:
        raise ValueError("Unexpected WordNet 3.0 SHA-256")
    evidence = defaultdict(list)
    with tarfile.open(path, "r:gz") as archive:
        for suffix, category in WORDNET_ROLES.items():
            member = f"WordNet-3.0/dict/index.{suffix}"
            with archive.extractfile(member) as stream:
                for line in stream:
                    if line.startswith(b" "):
                        continue
                    word = line.split()[0].decode("ascii").replace("_", " ")
                    if word in surfaces:
                        evidence[word].append({"category": category, "file": member, "lemma": word})
    return evidence


def wiktionary(path, expected, surfaces):
    if digest(path) != expected:
        raise ValueError("Unexpected Wiktextract SHA-256")
    evidence = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            word = entry.get("word")
            if entry.get("lang_code") != "en" or word not in surfaces:
                continue
            for index, sense in enumerate(entry.get("senses", []), 1):
                tags = sorted(set(sense.get("tags", [])) | set(entry.get("tags", [])))
                evidence[word].append({
                    "category": WIKTIONARY_ROLES.get(entry.get("pos")),
                    "etymology": entry.get("etymology_number", 0),
                    "sense": sense.get("id") or index,
                    "restricted": bool(RESTRICTED.intersection(tags)),
                    "tags": tags,
                    "topics": sorted(set(sense.get("topics", []))),
                    "formOf": [value["word"] for value in sense.get("form_of", [])],
                    "altOf": [value["word"] for value in sense.get("alt_of", [])],
                })
    return evidence


def align(args):
    rows = read_inventory(args.inventory)
    surfaces = {row["surface"] for row in rows}
    primary = wordnet(args.wordnet, surfaces)
    secondary = wiktionary(args.wiktextract, args.wiktextract_sha256, surfaces)
    write_jsonl(args.out, (
        {"id": row["id"], "reading": row["reading"], "surface": row["surface"],
         "wordnet": primary.get(row["surface"], []), "wiktionary": secondary.get(row["surface"], [])}
        for row in rows
    ))
    print(json.dumps({
        "inventorySha256": digest(args.inventory), "wordnetSha256": WORDNET_SHA256,
        "wiktextractSha256": args.wiktextract_sha256, "inputRows": len(rows),
        "wordnetMatchedRows": sum(row["surface"] in primary for row in rows),
        "wiktionaryMatchedRows": sum(row["surface"] in secondary for row in rows),
    }, sort_keys=True))


def prepare(args):
    rows = read_inventory(args.inventory)
    with args.allowlist.open(encoding="utf-8") as stream:
        allowed = set(stream.read().splitlines())
    payload = [{"id": row["id"], "surface": row["surface"]} for row in rows if row["id"] in allowed]
    if {item["id"] for item in payload} != allowed:
        raise ValueError("Unknown ID in the public input allowlist")
    if not payload or not 1 <= args.size <= 100:
        raise ValueError("A nonempty allowlist and batch size of 1 to 100 are required")
    args.out.mkdir(parents=True, exist_ok=True)
    with args.categories.open(encoding="utf-8", newline="") as stream:
        definitions = list(csv.DictReader(stream, delimiter="\t"))
    if not definitions or len({row["category"] for row in definitions}) != len(definitions):
        raise ValueError("Category definitions must be nonempty and unique")
    chunks = []
    for offset in range(0, len(payload), args.size):
        number = offset // args.size + 1
        path = args.out / f"batch-{number:05d}.jsonl"
        write_jsonl(path, payload[offset:offset + args.size])
        chunks.append({"file": path.name, "sha256": digest(path)})
    manifest = {"schemaVersion": 1, "inventorySha256": digest(args.inventory),
                "categoriesSha256": digest(args.categories), "categories": definitions, "chunks": chunks}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify(args):
    manifest_path = args.batches / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["schemaVersion"] != 1:
        raise ValueError("Unsupported batch manifest")
    categories = {row["category"] for row in manifest["categories"]}
    expected = {}
    pending = []
    proposed = []
    expected_files = {f"batch-{index:05d}.jsonl" for index in range(1, len(manifest["chunks"]) + 1)}
    unexpected_files = {path.name for path in args.responses.glob("batch-*.jsonl")} - expected_files
    if unexpected_files:
        raise ValueError(f"Unknown response chunks: {sorted(unexpected_files)}")
    for index, chunk in enumerate(manifest["chunks"], 1):
        filename = f"batch-{index:05d}.jsonl"
        source = args.batches / filename
        if chunk["file"] != filename or digest(source) != chunk["sha256"]:
            raise ValueError(f"Input changed: {source}")
        items = read_inventory(source)
        ids = {row["id"]: row["surface"] for row in items}
        if set(expected).intersection(ids):
            raise ValueError("Duplicate ID across chunks")
        expected.update(ids)
        path = args.responses / filename
        if not path.is_file():
            pending.append(filename)
            continue
        results = read_inventory(path)
        if {row["id"] for row in results} != set(ids):
            raise ValueError(f"Unknown or missing ID in {path}")
        for row in results:
            if row.get("batchSha256") != chunk["sha256"] or row.get("categoriesSha256") != manifest["categoriesSha256"]:
                raise ValueError(f"Stale response for {row['id']}")
            if row["surface"] != ids[row["id"]]:
                raise ValueError(f"Changed spelling for {row['id']}")
            proposed_categories = row["categories"]
            if (not isinstance(proposed_categories, list)
                or not all(isinstance(category, str) and category in categories for category in proposed_categories)
                or len(set(proposed_categories)) != len(proposed_categories)):
                raise ValueError(f"Invalid or duplicate category for {row['id']}")
            proposed.append({"id": row["id"], "surface": row["surface"], "categories": proposed_categories,
                             "batchSha256": chunk["sha256"], "responseSha256": digest(path)})
    write_jsonl(args.out, proposed)
    print(json.dumps({"manifestSha256": digest(manifest_path), "proposalCount": len(proposed), "pending": pending}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("align")
    for flag in ("inventory", "wordnet", "wiktextract", "out"):
        command.add_argument("--" + flag, type=Path, required=True)
    command.add_argument("--wiktextract-sha256", required=True)
    command.set_defaults(run=align)
    command = commands.add_parser("prepare")
    for flag in ("inventory", "allowlist", "categories", "out"):
        command.add_argument("--" + flag, type=Path, required=True)
    command.add_argument("--size", type=int, default=50)
    command.set_defaults(run=prepare)
    command = commands.add_parser("verify")
    for flag in ("batches", "responses", "out"):
        command.add_argument("--" + flag, type=Path, required=True)
    command.set_defaults(run=verify)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
