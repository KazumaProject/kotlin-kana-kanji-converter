#!/usr/bin/env bash
set -euo pipefail
archive=${1:-build/dictionary-metadata/snapshot.sqlite.gz}
lock=${2:-src/main/dictionary-quality/snapshot.lock.json}
repo=KazumaProject/kotlin-kana-kanji-converter
# Validate all release identity fields before using them as CLI arguments.
mapfile_compat() { while IFS= read -r line; do fields+=("$line"); done; }
fields=()
mapfile_compat < <(python3 - "$archive" "$lock" <<'PY'
import hashlib,json,re,sys
from pathlib import Path
archive,lock=map(Path,sys.argv[1:])
spec=json.loads(lock.read_text())
assert spec['schemaVersion']==2
assert re.fullmatch(r'dictionary-metadata-[0-9a-f]{16}',spec['tag'])
assert spec['asset']=='snapshot.sqlite.gz'
assert spec['url']==f"https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/download/{spec['tag']}/snapshot.sqlite.gz"
assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==spec['archiveSha256']
print(spec['tag']);print(spec['archiveSha256'])
PY
)
[[ ${#fields[@]} == 2 ]]
tag=${fields[0]}
expected=${fields[1]}
gh auth status >/dev/null
# Never replace an existing snapshot. Verify an already published asset instead.
if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  gh release download "$tag" --repo "$repo" --pattern snapshot.sqlite.gz --dir "$work"
  actual=$(python3 - "$work/snapshot.sqlite.gz" <<'PY'
import hashlib,sys
with open(sys.argv[1],'rb') as f:print(hashlib.file_digest(f,'sha256').hexdigest())
PY
)
  [[ "$actual" == "$expected" ]]
else
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  cp "$archive" "$work/snapshot.sqlite.gz"
  cp "$lock" "$work/snapshot.lock.json"
  gh release create "$tag" "$work/snapshot.sqlite.gz" "$work/snapshot.lock.json" --latest=false --repo "$repo" --target "$(git rev-parse HEAD)" --title "$tag" --notes 'Reduced immutable dictionary metadata. The application build selects this snapshot only after its lock file is committed.'
fi
