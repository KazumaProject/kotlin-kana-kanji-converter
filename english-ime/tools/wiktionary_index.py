"""Index the pinned English Wiktionary snapshot locally, without quotations."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time

from classification import digest

SNAPSHOT_SHA256 = "5ff2c072f8099f2d2ce484bd6957bf179f046d2ad37bc36555edf8bb84cb5291"
EXTRACTOR_REVISION = "19f9a3006a405fb7bfb40193dca41c7117a009a5"
DUMP_DATE = "2026-10-01"


def compact(row):
    return {key: row[key] for key in ("word", "pos", "tags", "etymology_number", "head_templates", "categories") if key in row} | {
        "senses": [{key: sense[key] for key in ("id", "senseid", "tags", "topics", "categories", "form_of", "alt_of", "glosses", "raw_glosses", "links") if key in sense}
                   for sense in row.get("senses", [])],
        "forms": [{key: form[key] for key in ("form", "tags") if key in form} for form in row.get("forms", [])],
    }


def build(source, output, notices):
    before = source.stat()
    if digest(source) != SNAPSHOT_SHA256:
        raise ValueError("Unexpected Wiktextract snapshot")
    if output.exists():
        raise ValueError("Output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".wiktionary-index-", dir=output.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        database = stage / "english.db"
        started = time.monotonic()
        connection = sqlite3.connect(database)
        try:
            connection.execute("create table entries (entry_id integer primary key, word text not null, folded text not null, record text not null)")
            count = 0
            total = 0
            with gzip.open(source, "rt", encoding="utf-8") as stream:
                for total, line in enumerate(stream, 1):
                    row = json.loads(line)
                    if row.get("lang_code") == "en":
                        value = compact(row)
                        connection.execute("insert into entries values (?,?,?,?)", (
                            total, row["word"], row["word"].casefold(),
                            json.dumps(value, sort_keys=True, ensure_ascii=False)))
                        count += 1
                    if total % 1000000 == 0:
                        print(json.dumps({"rawEntriesScanned": total, "englishEntriesIndexed": count,
                                          "seconds": round(time.monotonic() - started, 1)}), file=sys.stderr, flush=True)
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("Snapshot changed while indexing")
            connection.execute("create index entries_word on entries(word)")
            connection.execute("create index entries_folded on entries(folded)")
            connection.commit()
            if connection.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise ValueError("Index integrity check failed")
        finally:
            connection.close()
        for name in ("WIKTIONARY.txt", "CC-BY-SA-4.0.txt"):
            shutil.copyfile(notices / name, stage / name)
        manifest = {"schemaVersion": 1, "snapshotSha256": SNAPSHOT_SHA256,
                    "sourceUrl": "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz",
                    "dumpDate": DUMP_DATE, "extractorRevision": EXTRACTOR_REVISION,
                    "rawEntries": total, "englishEntries": count, "databaseSha256": digest(database),
                    "notices": {name: digest(stage / name) for name in ("WIKTIONARY.txt", "CC-BY-SA-4.0.txt")}}
        (stage / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        stage.rename(output)
    print(json.dumps(manifest, sort_keys=True))


class Index:
    def __init__(self, directory):
        self.directory = directory
        self.manifest = json.loads((directory / "manifest.json").read_text())
        if (self.manifest["schemaVersion"] != 1 or self.manifest["snapshotSha256"] != SNAPSHOT_SHA256 or
                self.manifest["extractorRevision"] != EXTRACTOR_REVISION or
                digest(directory / "english.db") != self.manifest["databaseSha256"]):
            raise ValueError("Changed or incompatible Wiktionary index")
        for name, expected in self.manifest["notices"].items():
            if digest(directory / name) != expected:
                raise ValueError("Changed Wiktionary notice")
        self.connection = sqlite3.connect((directory / "english.db").resolve().as_uri() + "?mode=ro", uri=True)

    def lookup(self, words, folded=False):
        words = sorted(set(word.casefold() if folded else word for word in words))
        column = "folded" if folded else "word"
        for offset in range(0, len(words), 400):
            chunk = words[offset:offset + 400]
            sql = "select entry_id,record from entries where " + column + " in (" + ",".join("?" for _ in chunk) + ") order by entry_id"
            for identifier, record in self.connection.execute(sql, chunk):
                yield identifier, json.loads(record)

    def close(self):
        self.connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--notices", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.out, args.notices)
