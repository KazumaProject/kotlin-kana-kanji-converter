"""Build a pinned, offline ESDB database while retaining source provenance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

REVISION = "1e5b7d3a72f47a71da5d28686c1dd4b397178485"
URL = "https://github.com/en-wl/wordlist/tree/" + REVISION


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source, output):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source, text=True)
    if revision != REVISION or dirty:
        raise ValueError("ESDB must be an unchanged checkout of the pinned revision")
    if output.exists():
        raise ValueError("Output already exists")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=source).decode().split('\0')
    inputs = {name: sha256(source / name) for name in sorted(filter(None, tracked))}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".esdb-", dir=output.parent) as temporary:
        result = Path(temporary) / "result"
        result.mkdir()
        database = result / "esdb.db"
        # The upstream file contains LLM-assisted promotions and POS adjustments.
        # Omit that merge entirely; filtering its tag afterwards cannot undo POS
        # changes. --raw retains the primary source tags and separate POS groups.
        driver = r'''
from pathlib import Path
import sys
text = Path("combine.py").read_text()
line = "    'data/coca_llm',\n"
if text.count(line) != 1:
    raise ValueError("Unexpected ESDB merge recipe")
text = text.replace(line, "", 1)
destination = sys.argv[1]
sys.argv = ["combine.py", "create-db", "--raw", destination]
exec(compile(text, "combine.py (without coca_llm)", "exec"))
'''
        environment = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
        for key in ("SCOWL_CACHE", "SCOWL_DB", "SCOWL_OPTS"):
            environment.pop(key, None)
        process = subprocess.run([sys.executable, "-B", "-c", driver, str(database.resolve())],
                                 cwd=source, env=environment, capture_output=True, text=True)
        if process.returncode:
            raise ValueError("ESDB build failed:\n" + process.stderr[-6000:])
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            if connection.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise ValueError("ESDB integrity check failed")
            if connection.execute("select count(*) from scowl_data where tag='[coca-llm]'").fetchone()[0]:
                raise ValueError("LLM-only source rows remain")
            counts = {table: connection.execute("select count(*) from " + table).fetchone()[0]
                      for table in ("groups", "words", "scowl_data")}
        shutil.copyfile(source / "Copyright", result / "ESDB-Copyright.txt")
        shutil.copyfile(source / "docs/sources.md", result / "ESDB-Sources.md")
        manifest = {"schemaVersion": 1, "revision": revision, "url": URL,
                    "recipe": "combine.py create-db --raw; omit data/coca_llm merge",
                    "inputs": inputs, "databaseSha256": sha256(database), "counts": counts,
                    "notices": {name: sha256(result / name) for name in ("ESDB-Copyright.txt", "ESDB-Sources.md")}}
        (result / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        result.rename(output)
    print(json.dumps({"revision": revision, "databaseSha256": manifest["databaseSha256"], "counts": counts}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source.resolve(), args.out.resolve())
