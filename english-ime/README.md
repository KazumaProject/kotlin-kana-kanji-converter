# English IME dictionary

This JVM 17 module builds the English-input dictionaries. Run from the repository root.

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
./gradlew :english-ime:run --args='build-reviewed --decisions /absolute/path/decisions.tsv --lexicon /absolute/path/grammar --relations /absolute/path/relations.tsv --out /absolute/path/reviewed'
```

The inventory includes the first data line and the v23 manual tables, for 102,051 rows. IDs identify rows within these fixed inputs. Export again and compare the complete row inventory when the source changes. The Python 3.11+ alignment tool joins exact English surfaces to [WordNet 3.0](https://wordnet.princeton.edu/license-and-commercial-use) and the [Wiktextract raw snapshot](https://kaikki.org/dictionary/rawdata.html). Record the Wiktionary dump date, extractor revision and SHA-256 alongside the snapshot and follow the [Wiktionary attribution and share-alike terms](https://en.wiktionary.org/wiki/Wiktionary:Copyrights) when distributing derived data. WordNet hits are lexical leads. Wiktionary evidence carries sense, form and restriction information for review.

The reviewed generator takes the same three lexicon tables as the CLI, a separate spelling relations table, and a TSV with header `id reading surface cost decision lexeme_ids reason evidence` (tab-separated). An `include` row takes one or more comma-separated lexeme IDs for that exact surface, reason `verified`, and an evidence URL. An `exclude` row uses `-` for lexeme IDs and one of `malformed`, `wrong_mapping`, `unattested`, `restricted`, or `unsupported_mapping` with its evidence URL. Use `restricted` when every verified sense is archaic, obsolete, offensive, or vulgar. Preserve any eligible modern senses. A mapped output containing spaces is unsupported by the current Sumire surface decoder. Identical reading and surface phrases can still use the reading as the surface. Missing, duplicate, or inconsistent decisions prevent output.

The build writes the four binary assets and a separate `grammar` directory. Relations describe contractions, regional spellings, hyphenation, capitalization and derivation. These links can have multiple targets and do not automatically create conversion entries. The generated Glide index omits legacy fallback additions. Sumire's own fallback path is a separate runtime path.

### Classification proposals

Use `classification.py prepare --inventory INVENTORY --allowlist IDS --categories CATEGORIES --out BATCHES` to prepare stable chunks from an explicitly reviewed public input allowlist. The categories TSV is the named dictionary catalog. Each response JSONL uses the matching batch filename and has `id`, `surface`, `categories`, `batchSha256` and `categoriesSha256` fields on every row. Use `classification.py verify --batches BATCHES --responses RESPONSES --out PROPOSALS` to validate finished chunks and report which are still missing. Proposals are separate from inclusion decisions. The tooling operates on local files. For an authorized live Gemini run, check the existing free project's billing status, model, remaining limits and data terms before any request.

The repository contains the grammar seed and relation examples. A completed full-source decision ledger is required to build the reviewed dictionary.
