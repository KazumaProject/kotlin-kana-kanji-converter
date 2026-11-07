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
dictionary and uses its grammar index to rank the candidates it finds.

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

## Add the reviewed practical vocabulary

To include the practical vocabulary for everyday writing, work, technology
and travel, generate the bundle with the supplement enabled.

```sh
python3 -B english-ime/tools/replay_source.py build \
  --supplement english-ime/data/supplement --out /tmp/reviewed-english-extended
./gradlew :english-ime:run --quiet --args='convert --assets /tmp/reviewed-english-extended --text twofactorauthentication --format json'
```

The supplement contains only reviewed forms with source identifiers. Joined
and spaced readings are derived from the written form. Related inflections
share a lexeme when their sources establish that relationship. Base readings,
candidates, costs, notices, and original decisions are preserved. The new
source notices and supplement manifest accompany the extended output. The
original build command without the option still reproduces the base bundle.

Use the same installed CLI to compare the two asset directories. The
`:english-ime:verifySupplementAssets` task accepts `-PenglishBaseAssets`
and `-PenglishExtendedAssets` and compares every decoded reading, candidate and
original cost, plus each new lexical form and its categories.

## Pack a runtime bundle

After generating either reviewed bundle, use `pack-runtime` with a new output directory.

```sh
./gradlew :english-ime:run --quiet --args='pack-runtime --assets /tmp/reviewed-english-extended --out /tmp/english-runtime'
./gradlew :english-ime:run --quiet --args='convert --assets /tmp/english-runtime --text hecantake'
```

The runtime bundle carries the conversion binaries, Glide index, source notices,
provenance manifests, and a grammar index of shared category masks. Use the
full reviewed bundle for `evaluate --lexicon` and for inspecting the review data.
The runtime grammar index is supported by this module's `convert` command.

To verify conversion with your own UTF-8 JSON array of input strings, pass
`--inputs` to the CLI verifier. It checks both exact and prefix modes. Use
`--reference-assets` to compare the entire JSON response, including candidate
order, costs, grammar scores, and segments, against a second bundle.

```sh
python3 -B english-ime/tools/verify_conversion_cli.py \
  --cli english-ime/build/install/english-ime/bin/english-ime \
  --assets /tmp/english-runtime --reference-assets /tmp/reviewed-english-extended \
  --inputs /tmp/english-inputs.json
```

## Grow the vocabulary with a resumable review harness

The Python 3.11+ harness mines missing spellings from pinned public lexical sources.
It compares them to **decoded runtime binary candidates**, not a similarly named
text dictionary. It prioritizes missing headwords and observed training-corpus
forms before possessives of already covered heads. Existing excluded spellings
remain excluded. This workflow does not change the converter's grammar or costs.

Keep all work outside the checkout, including ignored build directories. Start
with the full extended bundle produced by the replay command above:

```sh
python3 -B english-ime/tools/vocabulary_harness.py prepare \
  --work-dir /tmp/english-vocabulary-run \
  --assets /tmp/reviewed-english-extended \
  --source-dir /tmp/english-lexical-sources --esdb-dir /tmp/english-esdb \
  --fetch-sources --max-candidates 1000
python3 -B english-ime/tools/vocabulary_harness.py status \
  --work-dir /tmp/english-vocabulary-run
```

`--fetch-sources` downloads inputs pinned by the current supplement manifest and
prepares the pinned raw ESDB database without its LLM-assisted merge. Omit it to
use an existing verified cache. Source changes fail verification. Additional
explicitly reviewed reference documents can be supplied through `--references`:
an external JSON manifest with `documents`, each containing `file`, `url`,
`sha256`, `entries` using the seven supplement TSV fields, and `notices` with
`file`, `name`, and `sha256`. Exact spellings must occur in the document; lexical
roles require source review. Definitions and source prose stay outside Git.

### Optional Gemini proposals, within a verified free project

Gemini use is separate from signed-in Codex subscription usage. No API runs during
ordinary builds or CI. Before each day's API work, check the project's Free tier,
absence of billing, the key's project, and the actual model RPM/TPM/RPD in AI Studio.
Save this operator confirmation outside the repository as `free-tier-proof.json`:

```json
{"project_id":"your-project-id","model":"gemini-3.5-flash-lite","free_tier":true,
 "billing_enabled":false,"api_project_verified":true,"api_quota_verified":true,
 "rpm":15,"tpm":250000,"rpd":500,"verified_at":"2026-11-07T12:00:00+00:00"}
```

The numbers above illustrate the format; use the limits actually displayed for
your project. Confirmations expire after 24 hours. A key or a local confirmation
file alone cannot prove Google's current billing state or the key's project.
The harness does not enable billing, switch models, or use paid fallback tools.
Set `GEMINI_API_KEY` or provide a protected external key file; never commit it.

```sh
python3 -B english-ime/tools/vocabulary_harness.py review \
  --work-dir /tmp/english-vocabulary-run \
  --free-proof /private/path/free-tier-proof.json \
  --api-key-file /private/path/gemini-key --max-requests 1
```

Defaults are at most 20 candidates/request, one request/minute and 20 attempted
requests/day, with smaller batches for the input budget. The daily counter is
shared by project across runs in `~/.cache/english-vocabulary-harness/quota` and
resets at midnight Pacific time. Failed/unknown requests count locally too.
Other tools using the same Google project are outside this local counter.
`--wait` paces additional calls; without it, rerun after `minute_limit`.
Quota, transport and invalid-output errors save progress and stop. An interrupted
inflight request may have reached Google; its reservation is retained on retry.
Never change quota directories to evade limits.

### Source review, reproducible build and evaluation

`status` writes external `proposals.jsonl`. Gemini proposals alone cannot enter
the dictionary. A Codex/operator source review supplies an external JSONL file
with one record per reviewed candidate:

```json
{"id":"candidate ID","decision":"include","reason":"Source-backed review reason","proofIds":["supplied proof ID"]}
```

Decisions are `include`, `defer` or `exclude`; IDs and proof IDs must come from the
sealed candidate snapshot. Source review also works without Gemini. Final
decisions are immutable and idempotent; use a new run to revise them. This is
not a claim of human review or that every candidate was assessed by Gemini.

```sh
python3 -B english-ime/tools/vocabulary_harness.py review \
  --work-dir /tmp/english-vocabulary-run --decisions /tmp/source-review.jsonl
python3 -B english-ime/tools/vocabulary_harness.py build \
  --work-dir /tmp/english-vocabulary-run --out /tmp/english-vocabulary-result
python3 -B english-ime/tools/vocabulary_harness.py evaluate \
  --work-dir /tmp/english-vocabulary-run --assets /tmp/english-vocabulary-result/assets \
  --cases /tmp/heldout-cases.jsonl
```

The build merges reviewed entries with the current supplement, preserves notices,
freezes output hashes, replays from the original source bundle, audits every old
and new binary pair/category, and compares full/runtime conversion results. It
publishes `supplement`, `assets`, `runtime` and `verification.json` only on success.
For a custom supplement, the binary audit accepts `-PenglishSupplementEntries`;
`-PenglishRuntimeAssets` also audits every packed candidate and lexical surface role.
Only reviewed `supplement/entries.tsv`, its manifest and required notices belong
in a vocabulary PR; the generated binaries and verification report do not.

Evaluation cases are frozen external JSONL records with exactly `id`, `input`,
`expected`, `mode` (`exact`/`prefix`), `domain` and an HTTPS `source`. Use a pinned
held-out corpus, not the training sources used for candidate selection. Coverage
includes all cases, including missing words. Ranking uses a deterministic sample
of at most 200 cases, balanced across available domains and ordered by hashed ID,
configurable with `--sample-size`. Reports keep
separate denominators and domain counts; literal input echo, including partially copied words, is never a dictionary
hit. A report records case and asset hashes and cannot overwrite an earlier run.
The evaluation is JVM CLI evidence, not verification of an Android IME.

## 基本語とスペルミスの診断 / Basic vocabulary and typo diagnostic

ここでの目標は、日常のメッセージ、検索、買い物、移動、仕事・学校の基本的な連絡に
使う英語を、少ない打鍵と候補選択で自然な表記にできることです。
1,000件は試行・評価の単位であり、実用性の達成条件ではありません。
まず既存辞書の不足と検索・順位の問題を測ります。
スペルミスからの候補提示も目標に含めますが、現在の変換器には誤字訂正検索がありません。
このハーネスはその不足を測るもので、訂正エンジン自体の実装ではありません。
定期実行は設定しません。辞書の自動採用・API呼出しも行いません。

The goal is useful English entry for everyday messages, search, shopping, travel,
and basic work/school communication, with few keystrokes and candidate selections.
A 1,000-case pilot is a work unit, not a definition of completeness.
`practical_harness.py` diagnoses the current converter before vocabulary or
ranking changes. It includes typo suggestions as a required capability to measure;
it does not implement a typo search engine or claim practical acceptance.

```sh
./gradlew :english-ime:installDist
python3 -B english-ime/tools/practical_harness.py prepare \
  --source-dir /tmp/english-basic-sources --fetch-sources \
  --out /tmp/english-basic-suite
python3 -B english-ime/tools/practical_harness.py evaluate \
  --suite /tmp/english-basic-suite \
  --baseline-assets /tmp/reviewed-english-extended \
  --cli english-ime/build/install/english-ime/bin/english-ime \
  --out /tmp/english-basic-baseline --split dev --rank-limit 1000
```

All downloads, cases, inventories, checkpoints and reports must be outside any
Git checkout. Preparation pins and checks exact bytes, SHA-256, and source versions.
It uses first-column headwords only: NGSL 1.2 (2,809), NGSL-Spoken 1.2 (721),
and the supplementary list (52). Their union has 2,861 case-sensitive spellings
(2,859 casefolded keys); `May`/`may` and `March`/`march` remain distinct targets.
These are audit targets, **not newly added dictionary words**, and the lists'
published text/conversation coverage is not an IME success rate.
No inflected forms are inferred from lemmatized teaching/research lists.

Separate diagnostic groups measure:

- Exact basic headwords, including display capitalization; three-letter completion
  for alphabetic targets longer than three letters. Source groups retain general,
  spoken, and supplementary membership; these overlap and must not be summed.
- Publicly listed spelling errors from the pinned codespell **data**, restricted
  to single unannotated corrections independently present in the basic targets.
  Annotated/ambiguous corrections and inputs that are basic headwords are skipped.
  This list is not an observed IME error-frequency distribution.
- Deterministic synthetic deletion, insertion, adjacent-QWERTY substitution and
  adjacent transposition. Basic-word collisions are skipped; other legitimate
  readings may remain and are counted as `knownInputCases` from each binary.
  These are suggestion tests, not permission to automatically replace input.
- Project-authored everyday phrases, contractions, and preservation examples for
  correct words, a name, and an identifier. These small examples are smoke tests,
  not proof of complete phrase or false-correction coverage.

Coverage checks every target in the requested split against the decoded binary's
reading/surface pairs, preserving output case. `targetCovered` means direct
registration; a phrase can still be composed successfully from multiple words.
Ranking uses a deterministic sample, round-robin across scenarios and edit types,
with separate denominators. It does not weight synthetic errors as actual usage.
An echoed input or partially copied alphanumeric span never counts as dictionary
retrieval. Preservation has its own `preservedTop1` metric, where literal echo is
appropriate. `*-diagnostics.jsonl` includes each sampled input, target, rank,
registration status, diagnosis and proof; `missingBasicSpellings` lists basic gaps.

All variants of a casefolded target share a deterministic 80/20 dev/holdout split;
the realized counts can differ from 80/20. This is not a lemma-family split or a
guaranteed untouched benchmark. Use `dev` for iteration, and reserve `holdout`
for a later check; inspecting it repeatedly consumes that independence.
Default ranking sample size is 1,000; `--split all` checks both splits explicitly.
Use `--jobs 2` (up to 4) to run read-only JVM queries concurrently if memory allows;
the default is one, and candidate scoring/checkpoint order stays deterministic.
Acceptance thresholds for coverage, completion and typo success remain to be
agreed. Reports deliberately contain no `practicalReady` judgment. Interactive
typing latency, memory, and Android IME behavior remain unverified.

For a comparison, add `--candidate-assets DIR` and, when comparing converter
implementations, `--baseline-cli OLD_INSTALL/bin/english-ime`. Omitting candidate
assets measures one baseline; identical engine/asset hashes reuse the same queries.
Runs freeze suite/tool hashes, launcher/JAR hashes, and all asset hashes, and save
candidate/segment evidence outside the repository. Re-running the same command
resumes completed queries; changed inputs/options require a new output directory.
`--fail-on-regression` fails on lost target registration, loss from the top five,
loss of basic exact top one, or loss of correct first-candidate preservation in
the measured sample. No measured regression is not evidence of practical readiness.

### 評価素材のライセンス / Evaluation data licenses

| Material | License | Attribution and source |
| --- | --- | --- |
| NGSL 1.2 and supplementary words | CC BY-SA 4.0 | [Browne, Culligan, Phillips / official NGSL page](https://www.newgeneralservicelist.com/new-general-service-list) |
| NGSL-Spoken 1.2 | CC BY-SA 4.0 | [Browne and Culligan / official spoken page](https://www.newgeneralservicelist.com/ngsl-spoken) |
| codespell spelling dictionary at `b53e95197f7c799674c785028a182e2dfd1df881` | CC BY-SA 3.0 | [codespell dictionary contributors; derived from English Wikipedia contributors / pinned license statement](https://github.com/codespell-project/codespell/blob/b53e95197f7c799674c785028a182e2dfd1df881/README.rst#license) |
| Harness code and project-authored examples | MIT | [Project license](../LICENSE) |

素材ごとの出典・版・SHA-256・ライセンスURL・表示すべき著作者・加工内容を
`suite.json`、`attribution.json`、`ATTRIBUTION.txt`に記録し、評価出力にも引き継ぎます。
派生評価データ集はCC BY-SA 4.0で提供し、元素材の表示と条件を保持します。
コードのMITライセンスで辞書・評価データを一括して扱いません。
今回、配布辞書やそのライセンス構成は変更しません。将来評価素材を辞書に採用する場合も、
出典と適用条件を配布物に引き継ぐ必要があります。

Generated suites and reports retain per-source attribution, versions, hashes,
license URLs, and a description of selection/normalization/synthetic changes.
The derived evaluation collection is CC BY-SA 4.0 with original source notices
retained. This does not relicense program code or the existing dictionary bundle.
No codespell GPL program/library code is imported. Preserve attribution and
applicable share-alike terms if these data are later used in distributed assets.

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

## Unattended adoption and daily execution

`vocabulary_auto.py adopt` re-extracts candidates from checksum-verified sources
and automatically adopts only multi-character spellings backed by ESDB size <=60,
an eligible WordNet role, and CMU spelling, observed training usage, or a listed
headword. Gemini defer/exclude proposals veto automatic adoption. Unsupported
sources or insufficient evidence are deferred. These are automated source-policy
decisions, not human reviews. The immutable candidate must match the new extraction.

```sh
python3 -B english-ime/tools/vocabulary_auto.py daily \
  --work-dir /tmp/english-daily --timezone America/Toronto \
  --assets /tmp/reviewed-english-extended \
  --source-dir /tmp/english-lexical-sources --esdb-dir /tmp/english-esdb \
  --max-candidates 1000
```

`daily` checkpoints one run per calendar day, resumes it after failure and builds
only approved entries through the existing binary/replay/runtime validation gates.
Outputs remain external. It makes zero implicit API calls. To use optional Gemini
proposals, run `prepare` and `review` for that day's run before `daily` or `adopt`.
Expired free-project confirmations must never be renewed just by changing their
timestamp: recheck AI Studio, or continue with the source-only policy and report it.
Scheduling is configured separately in the Codex app; local runs require the
computer and app to be running. Verified dictionary changes can be copied to the
working branch and published through a PR; no automatic main merge or app release
is implemented. Use the newly adopted supplement's assets as the next day's
baseline, so already adopted spellings are not selected again.
