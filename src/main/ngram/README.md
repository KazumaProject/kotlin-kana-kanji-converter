# N-gram Presence Sources

Add production N-gram presence correction data under `src/main/ngram/sources`.

1. Add a TSV file with columns:
   `order reading surface1 surface2 surface3 surface4 surface5 source comment`
2. Add one row to `sources/sources_manifest.tsv`.
3. Run `./gradlew generateNgramPresenceData verifyNgramPresenceData`.

`sources_manifest.tsv` columns:

- `enabled`: `true` or `false`.
- `file`: relative TSV path under `sources`.
- `kind`: currently `presence`.
- `orders`: comma-separated orders such as `1,2,3`, or `1,2,3,4,5`.
- `description`: human-readable source note.

The Gradle task `prepareNgramSources` copies these committed sources into
`src/main/resources/ngram/sources`, which remains ignored by git. The generator
then reads `src/main/resources/ngram/sources/*.tsv` through the manifest.
