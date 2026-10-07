# Dictionary entry index

Every new dictionary release includes `dictionary-index.tsv.gz`,
`dictionary-index-manifest.json`, and `dictionary-index-NOTICES.md` alongside
`japanese_keyboard_dictionary_assets.zip`.

The UTF-8, gzip-compressed TSV has a header and three columns:
`dictionary`, `reading`, `word`. Fields containing quotes, tabs, or newlines use
CSV quoting with a tab delimiter. Rows describe decoded tokens in all 13 word
packs, including kana sentinels, custom system entries, and English-reading
conversion. Reading-correction explanations are display metadata and are
removed from the written form. Scores and n-gram/zero-query predictions are
not independent reading-to-word entries.

The manifest (schema version 1) records the exact release, converter and Mozc
commits, bundle and index SHA-256 hashes, row counts per pack, and the complete
POS mapping and hash of the packaged `id.def`. A consumer must verify all pack
counts, both artifacts, and the POS mapping before calling any word absent.
Source lookup tables and dictionary-quality metadata snapshots are not this
conversion entry index.

`./gradlew exportDictionaryIndex` runs packaging first and reads the resulting
binary assets. Local builds can set `-PdictionaryRelease=...`,
`-PconverterCommit=...`, and `-PmozcCommit=...`; release CI supplies actual
revisions. `./gradlew dictionaryIndexTest` checks fixture decoding, kana,
pack coverage, and corrupt-token rejection. Normal release CI also runs the
existing full resource validations and engine tests.

For New-word rollout, publish a version release containing the complete index,
then run its `check_dictionary_only` manual workflow. Enable the
`IME_COLLECTION_ENABLED` repository variable only after that check succeeds.
