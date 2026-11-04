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
./gradlew :english-ime:run --args='evaluate --text "Does he <candidate>?" --candidate take --candidate takes --format json'
```

Use one `<candidate>` marker. Repeat `--candidate` for alternative completions, and use `--lexicon DIR` to load a different directory. Scores are 1 for a supported interpretation, -1 when all known interpretations conflict with a supported rule, and 0 when the evaluator lacks evidence. The CLI ranks candidates without editing input. It recognizes simple agreement, coordination, intervening adverbs, and auxiliary clauses. Unsupported constructions, including ambiguous uses of `to`, receive a neutral result.

The seed lexicon under `data/grammar` has one row per named dictionary definition, one row per lexeme and surface pair, and separate dictionary memberships. A form can belong to multiple dictionaries. Each membership is attached to one form of one lexeme, so shared spellings such as `saw` cannot combine roles across lemmas. The definitions describe each dictionary's role and provide examples. The forms link to lexical evidence.
