# System N-Gram dictionary

The system N-Gram dictionary is an immutable, adjustment-free set of typed 2–5 node patterns. A matched conversion path belongs to the preferred candidate group; candidates inside the same group keep their normal conversion-cost order.

## Editing rules

Tracked source files live in `src/main/ngram/rules`. A `.ngram` file contains one pattern per line and has no header or metadata columns:

```text
布 + で + [名詞] + を + 拭く
服 + を + 着る
```

An ordinary element is an exact NFC-normalized surface. Only non-word elements use notation:

- `[名詞]`: coarse POS class derived from Mozc `id.def`
- `*`: any one lattice node
- `"C++"`: a quoted exact word when the surface itself contains `+`

Japanese POS names are `名詞`, `固有名詞`, `動詞`, `形容詞`, `副詞`, `助詞`, `助動詞`, `記号`, `その他`, and `未知語`. Their English enum names are also accepted. A proper noun also matches `[名詞]`.

Add or edit a pattern by changing its line. Delete the line to remove it. Prefix the line with `#` to keep it in the file without compiling it:

```text
# 服 + を + 着る
```

Patterns must contain 2–5 elements and must be globally unique across all `.ngram` files. Validation errors identify the source file and line, so IDs are unnecessary.

## Local commands

```bash
./gradlew validateSystemNgramSources
./gradlew generateSystemNgramDictionary
./gradlew verifySystemNgramDictionary
./gradlew benchmarkSystemNgramDictionary
./gradlew packageSystemNgramRelease
```

Generated runtime files are deliberately ignored by Git:

- `src/main/resources/ngram/system_ngram.dat`
- `src/main/resources/ngram/system_ngram_manifest.json`

The release bundle is `release_zips/system_ngram_dictionary.zip`. It contains the binary, manifest, editable sources, and performance evidence. The main JapaneseKeyboard assets ZIP also contains the binary and manifest under `app/src/main/assets/ngram/`.

## Binary structure

`system_ngram.dat` has a versioned header, payload size, and CRC32. Its payload contains:

1. an UTF-8 byte-labelled LOUDS vocabulary mapping exact surfaces to local word IDs;
2. an integer-labelled LOUDS pattern trie whose labels are tagged `WORD`, `POS`, or `ANY`;
3. terminal bits representing membership, with no adjustment array;
4. a compact `leftId -> coarse POS` byte table generated from the same Mozc `id.def` as the dictionary build.

The loader rejects unsupported versions, malformed lengths, inconsistent LOUDS topology, CRC failures, and trailing bytes. A rule edit always performs a deterministic full rebuild; the succinct structure is never mutated in place.

## Performance evidence

`benchmarkSystemNgramDictionary` reports:

- serialized byte size;
- structural retained-memory estimate;
- JOL retained object-graph size using the current JVM layout information;
- heap size with one reusable allocation-free matcher;
- GC-sensitive process heap delta as supporting information only;
- median, p95, and maximum exact-word lookup time;
- median, p95, and maximum encoded pattern lookup time.

Pattern lookup uses precomputed word/POS IDs and a reusable matcher, which is the intended conversion hot path. Word lookup includes NFC normalization and UTF-8 encoding and should happen once while constructing a lattice node, not for every A* edge expansion.

Timing results are observations, not fixed CI thresholds. GitHub Actions appends the Markdown report to the job summary and publishes it in the release ZIP.

## JapaneseKeyboard integration contract

Load one `SystemNgramDictionary` and create one matcher per conversion thread. Store the N-Gram-local word ID and coarse POS ID on each lattice node. A path carries `hasSystemNgram`, updated with logical OR when a 2–5 node window matches.

Final candidate ordering is lexicographic:

```text
(hasSystemNgram ? preferred : normal, originalConversionCost)
```

To guarantee that a registered pattern is globally first, the flag must participate in path search state; reranking only an already-truncated candidate list is not sufficient.
