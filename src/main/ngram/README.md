# N-gram Correction Sources

Add production N-gram correction data under `src/main/ngram/sources`.

1. Add a TSV file with columns:
   `order reading surface1 surface2 surface3 surface4 surface5 source comment`
2. Add one row to `sources/sources_manifest.tsv`.
3. Run `./gradlew generateNgramCorrectionData verifyNgramCorrectionData`.

The generated runtime dictionary is independent from the system dictionary. It
maps a full reading string to one or more exact surface sequences, so
JapaneseKeyboard can later place the first returned candidate at the top of the
conversion candidate list without resolving system token IDs.

Candidate priority is deterministic:

1. order of enabled files in `sources_manifest.tsv`
2. row order inside each TSV

Exact duplicate rules are deduped. Different surface sequences for the same
reading are kept as additional candidates, not scored rules.

`sources_manifest.tsv` columns:

- `enabled`: `true` or `false`.
- `file`: relative TSV path under `sources`.
- `kind`: currently `correction`.
- `orders`: comma-separated orders such as `1,2,3`, or `1,2,3,4,5`.
- `description`: human-readable source note.

The Gradle task `prepareNgramSources` copies these committed sources into
`src/main/resources/ngram/sources`, which remains ignored by git. The generator
then reads `src/main/resources/ngram/sources/*.tsv` through the manifest.
