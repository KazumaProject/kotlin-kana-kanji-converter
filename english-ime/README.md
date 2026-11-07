# English IME dictionary

This JVM 17 module builds the English-input dictionaries. Run from the repository root.

## Reproduce the completed dictionary

The reviewed source bundle under `data/reviewed` contains decisions for all
102,051 original rows: **101,626 admitted, 425 excluded, zero pending**. It
preserves the original IDs, order, readings and costs, multiple lexical
interpretations, lemma/form links, category memberships and case alternatives.
The small `data/grammar` seed remains available for focused tests and examples.

With Python 3.11+ and JDK 17:

```sh
python3 -B english-ime/tools/replay_source.py verify
python3 -B english-ime/tools/replay_source.py build --out build/reviewed-english
```

The build checks the original ZIP, exports the current Kotlin manual/source
inventory, compares every ordered tuple, and runs the existing `build-reviewed`
command with corrections and all source notices. It compares every resulting
payload, grammar table, compact category index and notice to the verified final
build. The output directory must be new. Gradle may download its ordinary build
dependencies when uncached; dictionary replay needs no classification API, keys
or private research corpora. These commands do not publish or release assets.

`manifest.json` pins the compressed archive and every uncompressed file with
SHA-256 and byte lengths. Extraction rejects missing/extra files, duplicate
members, links and escaping paths. Its `reviewed-replay-v1` format is distinct
from a research materialization: it replays the completed ledger rather than
repeating semantic research or synthesizing approval evidence. The large raw
research evidence and source prose, definitions and code are omitted. Compact
provenance retains lexical identities, source pointers, qualified namespaces
and document checksums. Checksums are integrity checks, not digital signatures.

[Category counts](data/reviewed/category-counts.tsv) distinguish admitted distinct
candidate surfaces and original input rows from supporting model references.
Categories overlap; their counts must not be summed as a vocabulary total.
Named account/work references, technical identifiers and narrowly attested
regional or expressive forms retain their documented meanings; they do not
establish ordinary English senses or personal/legal identities.

To inspect or evaluate the full tables:

```sh
python3 -B english-ime/tools/replay_source.py verify --out /tmp/reviewed-english-inputs
./gradlew :english-ime:run --args='evaluate --lexicon /tmp/reviewed-english-inputs/grammar --text "He has <candidate>" --candidate taken --candidate took --format json'
```

All source notices travel with generated assets, including WordNet,
Wiktionary/wordfreq share-alike data and EDRDG/JMnedict attribution and conditions.
Keep the required source acknowledgements in the consuming application's
About/Sources interface. The host checks identify Sumire consumer
`427baa8ef19a5917ea931d6731ec9d1fd95289d7` and category reader
`2a42c4b3c978a51243a9baeb7fc6777573e31712`; physical Android memory, IME UI and
production ranking remain unverified.

## Convert English text

Build the reviewed dictionary with the replay command above, then pass the
generated directory to `convert`. The command reads the reviewed binary
dictionary and uses the full grammar tables to rank the candidates it finds.

```sh
./gradlew :english-ime:run --quiet --args='convert --assets /absolute/path/reviewed-english --text hecantake'
./gradlew :english-ime:run --quiet --args='convert --assets /absolute/path/reviewed-english --text "its working" --format json'
./gradlew :english-ime:run --quiet --args='convert --assets /absolute/path/reviewed-english --text "he tak" --mode prefix'
```

The first example ranks `he can take` first. The second can rank `it's working`
above `its working` using the following word, while `the dog chased its tail`
favors the possessive. The third uses the typed prefix to find forms such as
`takes`. The default mode is `exact`. Prefix mode considers dictionary cost
before limiting completions, and favors completing the typed word over
splitting it when both are possible. It also completes a partially typed
spelling such as `don'` or `wi-`. Both modes can infer boundaries in
joined input. In text that already has word boundaries, a registered word is
kept intact. Sentence punctuation and unrecognized spans are copied from the input.

By default the CLI returns up to 10 candidates. `--limit` accepts 1–50, and
input is limited to 256 UTF-16 code units. Text output lists rank, candidate,
dictionary cost and grammar reasons, with tabs and line breaks escaped inside
the result field. JSON adds the grammar score and segments
with zero-based, end-exclusive UTF-16 offsets into the original input.
A segment records whether it is an exact dictionary match, a completion, or
literal text. `inferredSpace` marks a space inserted before a segment.

The rules cover selected local English constructions, and the search is bounded.
Grammar ranks candidates available for the typed reading. Exact input such as
`he take` keeps the typed verb rather than replacing it with a different
inflection.

## Legacy compatibility

```sh
./gradlew :english-ime:test
./gradlew :english-ime:run --args='build-legacy --out build/legacy'
```

The default input is `data/1-grams_score_cost_pos_combined_with_ner.zip` within this module. Use `--source` with an absolute path to select a different ZIP. Output paths are relative to the module unless absolute. The compatibility command writes `reading.dat`, `word.dat`, `token.dat` and `qwerty_glide_index.dat`.

The compatibility path reproduces [kotlin-louds-english v23](https://github.com/KazumaProject/kotlin-louds-english/tree/683d856361a49e8f3d69b962a8c51c28ad2329a7), including skipping the first data row and allocating a token slot per input row. The TSV has 100,075 data rows. The compatibility loader reads 100,074, then the builder adds 1,976 manual rows. The original data has 64 additional rows for shared readings and the combined input has 946 more token slots than distinct terminal readings. Some source surfaces, including `I` and `don't`, are reconstructed as their input spelling. The four output payloads match the legacy assets shipped in the Sumire v1.7.140 Lite Standard ARM64 APK. Sumire separately compacts its three LOUDS and token payloads during its Android build.

## Attribution

- Migrated Kotlin source and the manual list come from KazumaProject's v23 tree. See [the upstream MIT license](notices/KOTLIN-LOUDS-ENGLISH-MIT.txt).
- The bundled data ZIP is from [english_dictionary_builder at 541d358](https://github.com/KazumaProject/english_dictionary_builder/tree/541d358ae4855c34c42be449679b076dd33ea11c), with SHA-256 `33dfe992f0220f28f18a8ca21af2139a4f345871c5bd6004ce09c109e1791c8c`. Its TSV payload matches the v23 Kotlin project's TSV, SHA-256 `68b9c3878bc8a2472ccf0688908b61e56cbd07de9095ff939590b06f08477f4d`. The ZIP carries the upstream provenance summary, notice, and CC BY-SA 4.0 text. The builder project uses [Apache 2.0](notices/ENGLISH-DICTIONARY-BUILDER-APACHE.txt).
- The frequency-derived data is attributed to Robyn Speer and redistributed under CC BY-SA 4.0 with the [wordfreq notice and underlying source acknowledgments](notices/WORDFREQ-NOTICE.md). These include Google Books, OpenSubtitles and the freely available SUBTLEX word lists by Marc Brysbaert et al. The upstream builder filtered and normalized vocabulary, assigned costs and merged manual entries and generated inflections. Its recorded build disabled the WikiText and SCOWL layers. The exact wordfreq package version used in that build is unconfirmed. [wordfreq's software license](notices/WORDFREQ-APACHE.txt) applies to its code. Keep the data notices with redistributions of the generated dictionaries.

## Context evaluation

```sh
./gradlew :english-ime:run --quiet --args='evaluate --text "Does he <candidate>?" --candidate take --candidate takes --format json'
```

Use one `<candidate>` marker. Repeat `--candidate` for alternative completions, and use `--lexicon DIR` to load a different directory. Scores are 1 for a supported interpretation, -1 when all known interpretations conflict with a supported rule, and 0 when the evaluator lacks evidence. The CLI ranks candidates without editing input. It recognizes simple agreement, coordination, intervening adverbs, and auxiliary clauses. Unsupported constructions, including ambiguous uses of `to`, receive a neutral result.

The seed lexicon under `data/grammar` has one row per named dictionary definition, one row per lexeme and surface pair, and separate dictionary memberships. A form can belong to multiple dictionaries. Each membership is attached to one form of one lexeme, so shared spellings such as `saw` cannot combine roles across lemmas. The definitions describe each dictionary's role and provide examples. The forms link to lexical evidence.

## Full-source evidence and reviewed builds

```sh
./gradlew :english-ime:run --quiet --args='export-inventory --out /absolute/path/inventory.jsonl'
python3 -B english-ime/tools/classification.py align \
  --inventory /absolute/path/inventory.jsonl --wordnet /absolute/path/WordNet-3.0.tar.gz \
  --wiktextract /absolute/path/raw-wiktextract-data.jsonl.gz --wiktextract-sha256 "$WIKTEXTRACT_SHA256" \
  --out /absolute/path/evidence.jsonl
./gradlew :english-ime:run --args='build-reviewed --decisions /absolute/path/decisions.tsv --lexicon /absolute/path/grammar --relations /absolute/path/grammar/relations.tsv --corrections /absolute/path/surface-corrections.tsv --notices /absolute/path/notices --out /absolute/path/reviewed'
```

The inventory includes the first data line and the v23 manual tables, for 102,051 rows. IDs identify rows within these fixed inputs. Export again and compare the complete row inventory when the source changes. The Python 3.11+ alignment tool joins exact English surfaces to [WordNet 3.0](https://wordnet.princeton.edu/license-and-commercial-use) and the [Wiktextract raw snapshot](https://kaikki.org/dictionary/rawdata.html). Record the Wiktionary dump date, extractor revision and SHA-256 alongside the snapshot and follow the [Wiktionary attribution and share-alike terms](https://en.wiktionary.org/wiki/Wiktionary:Copyrights) when distributing derived data. WordNet hits are lexical leads. Wiktionary evidence carries sense, form and restriction information for review.

The reviewed generator takes the same three lexicon tables as the CLI, a separate spelling relations table, and a TSV with header `id reading surface cost decision lexeme_ids reason evidence` (tab-separated). An `include` row takes one or more comma-separated lexeme IDs for the effective surfaces, reason `verified`, and an evidence URL. An `exclude` row uses `-` for lexeme IDs and one of `malformed`, `wrong_mapping`, `unattested`, `restricted`, `ineligible_senses`, `ineligible_reference`, or `unsupported_mapping` with its evidence URL. Use `restricted` when every verified sense is archaic, obsolete, offensive, or vulgar. Preserve eligible modern senses and independently attested names. Source absence alone does not establish a malformed word. Case and input-spelling alternatives must pass the existing guards and retain their original row. Mapped spaces use the reviewed alias/consumer contract tested above; replay adds no stricter CLI-only filter. Missing, duplicate, pending or inconsistent decisions prevent output. Binary generation retains the existing minimum-cost aggregation for duplicate reading/surface pairs; the complete original costs remain in the ledger and inventory.

The build writes the four binary assets and a separate `grammar` directory. Relations describe contractions, regional spellings, hyphenation, capitalization and derivation. These links can have multiple targets and do not automatically create conversion entries. The generated Glide index omits legacy fallback additions. Sumire's own fallback path is a separate runtime path.

### Classification proposals

Use `classification.py prepare --inventory INVENTORY --allowlist IDS --categories CATEGORIES --out BATCHES` to prepare stable chunks from an explicitly reviewed public input allowlist. The categories TSV is the named dictionary catalog. Each response JSONL uses the matching batch filename and has `id`, `surface`, `categories`, `batchSha256` and `categoriesSha256` fields on every row. Use `classification.py verify --batches BATCHES --responses RESPONSES --out PROPOSALS` to validate finished chunks and report which are still missing. Proposals are separate from inclusion decisions. The tooling operates on local files. For an authorized live Gemini run, check the existing free project's billing status, model, remaining limits and data terms before any request.

The repository contains both the grammar seed and the completed replay inputs.
For a newly completed research materialization, pack it only after its final
audit and actual-reader checks succeed:

```sh
python3 -B english-ime/tools/replay_source.py pack \
  --directory /path/to/final-materialization --audit /path/to/final-quality-audit.json \
  --gold /path/to/verified-final-build --out /path/to/new-reviewed-source
```

The pack step requires zero pending rows, unchanged pinned original inputs and
the exact final validation proofs. It preserves all source notices and produces
a separate typed replay manifest. Research `load_base`/`verify` continue to
require their full evidence and cannot consume this smaller replay bundle.


### Category-count performance check

`lexicon_pipeline.category_surface_counts` counts distinct surfaces across lexical
identities in one membership pass. Sorted category order, empty definitions and
homograph de-duplication retain the previous semantics; it does not cache results.

For an existing public materialization, compare a pinned baseline source with the
current implementation using the same interpreter:

```sh
git show f18eb132ffa5635200243d169647b0ebf60ab7ae:english-ime/tools/lexicon_pipeline.py > /tmp/lexicon_pipeline_baseline.py
python3 english-ime/tools/benchmark_category_counts.py \
  --baseline /tmp/lexicon_pipeline_baseline.py \
  --candidate english-ime/tools/lexicon_pipeline.py \
  --directory /path/to/public-materialization \
  --seed english-ime/data/grammar --tools english-ime/tools \
  --out /tmp/category-count-benchmark
```

The output directory must be new. The benchmark alternates sequential before/after
runs, checks ordered category counts, and compares every generated file hash. Its
end-to-end scope is a no-op extension: base verification, evidence reload,
publication and staged verification. It excludes external-source reimport and
JVM/Android readers. On 421,132 forms / 124 categories, seven local repetitions
and three end-to-end repetitions per mode measured medians of 3.995 s vs 0.177 s
for counting, and 72.62 s vs 60.38 s for the extension. The category calculation
was observed three times per extension. These are host Python measurements, not
smartphone timings. Run again for your interpreter and data.
