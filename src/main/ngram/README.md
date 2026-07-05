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

## Contextual Correction Sources

Add variable-context correction rules under `src/main/ngram/context_sources`.

1. Add a TSV file with columns:
   `id pattern source comment`
2. Add one row to `context_sources/sources_manifest.tsv`.
3. Run `./gradlew generateContextualCorrectionData verifyContextualCorrectionData`.

Pattern DSL:

- `lit(reading,surface)`: fixed token, reading and surface must match exactly.
- `slot(name,CLASS)`: variable token constrained by coarse class such as `NOUN`.
- `target(reading,fromSurface,toSurface)`: fixed token to rewrite.

Example:

```text
lit(ぬので,布で) slot(object,NOUN) lit(を,を) target(ふく,吹く,拭く)
```

This matches `布で / フルート / を / 吹く` when `フルート` is tagged as
`NOUN`, and returns `布で / フルート / を / 拭く`. Rule priority is
deterministic: manifest order, then TSV row order. The runtime dictionary uses
token sequence exact checks plus coarse-class slots, and remains independent
from system dictionary IDs.

## Coarse POS Class Table

Contextual correction rules do not parse `id.def` at JapaneseKeyboard runtime.
The converter generates `ngram/coarse_pos_class.data` from Mozc `id.def`:

```text
leftId -> ContextualCorrectionCoarseClass byte
```

JapaneseKeyboard should build each contextual token from the actual conversion
path node:

```kotlin
ContextualCorrectionToken(
    reading = node.yomiUsed,
    surface = node.tango,
    coarseClass = coarsePosClassTable.classify(node.l),
)
```

The mapping policy is `LEFT_ID_POS1_V1`. It uses the left connection ID as the
primary POS signal:

- `名詞` -> `NOUN`
- `助詞` -> `PARTICLE`
- `動詞` -> `VERB`
- `助動詞` -> `AUX`
- `記号` -> `SYMBOL`
- everything else -> `UNKNOWN`

Run:

```shell
./gradlew generateCoarsePosClassData verifyCoarsePosClassData
```

The generated table is a compact byte array indexed by `leftId`; it is included
in the JapaneseKeyboard-ready assets package with `coarse_pos_class_manifest.json`.
