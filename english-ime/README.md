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

## 対象を固定して収録率を改善する / Operate the target catalog

`catalog_harness.py` は、既存辞書を調べる前に必要語の集合を固定し、表記の収録率と
カテゴリの補完率を別々に測定します。対象・保留語も分母に残します。1,000件は採用時の
チェックポイントの大きさであり、必要語の上限ではありません。

The versioned [taxonomy](data/catalog/taxonomy.json) defines 67 topical categories.
Alongside daily/IT vocabulary it covers mathematics, statistics, physics,
electronics, embedded systems, mechanics, manufacturing, robotics, materials,
chemistry, civil engineering, energy, environment, transport, aerospace, biology,
medicine, agriculture, photography, audio and graphics. Personal names, public
figures by field, products, brands, organizations and services have distinct scopes.
The independent
[target declarations](data/catalog/core-targets.json) combine NGSL headwords, explicit
everyday/technical requirements, attested given names/surnames, selected named
entities and a frozen top-100 Homebrew catalog selection. The latter is one
software source, not a general product-popularity metric. Primary product labels are core; explicit additional
labels are extended. These are scoped requirements, not a claim to cover all English.

Topic, lexical role, lemma/form, entity kind and target tier are separate axes.
Existing reviewed lexical analyses can support topic-only enrichment. Their lemma,
POS, readings and costs are retained; annotations cannot invent grammatical roles or
new candidates. New spellings require independent source evidence. Ordinary lowercase
terms are declared explicitly and may match source heading case; names, acronyms and
language labels require exact case. No suffix/plural derivation is performed. Topic
membership classifies declared surface vocabulary; it does not disambiguate senses.

Use Python 3.11+, the installed JDK 17 CLI, and new external work/output directories.
First obtain the lexical sources with `dictionary_sources.py fetch` as shown below,
and build the current full extended dictionary. Install the pinned RDF parser in
an external virtual environment (Python 3.11+) for QUDT, then activate it:

```sh
python3 -m venv /tmp/english-catalog-venv
/tmp/english-catalog-venv/bin/pip install -r english-ime/tools/requirements-catalog.txt
source /tmp/english-catalog-venv/bin/activate
python3 -B english-ime/tools/catalog_harness.py fetch \
  --source-dir /tmp/english-catalog-sources
python3 -B english-ime/tools/catalog_harness.py fetch-world \
  --source-dir /tmp/english-catalog-sources
python3 -B english-ime/tools/catalog_harness.py prepare \
  --work-dir /tmp/english-catalog-run --assets /tmp/reviewed-english-extended \
  --source-dir /tmp/english-catalog-sources \
  --lexical-source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
python3 -B english-ime/tools/catalog_harness.py report \
  --work-dir /tmp/english-catalog-run --out /tmp/english-catalog-before
python3 -B english-ime/tools/catalog_harness.py adopt \
  --work-dir /tmp/english-catalog-run --batch-size 1000
python3 -B english-ime/tools/catalog_harness.py build \
  --work-dir /tmp/english-catalog-run --out /tmp/english-catalog-result
python3 -B english-ime/tools/catalog_harness.py report \
  --work-dir /tmp/english-catalog-run --assets /tmp/english-catalog-result/assets \
  --out /tmp/english-catalog-after
python3 -B english-ime/tools/catalog_review.py export \
  --work-dir /tmp/english-catalog-run --assets /tmp/english-catalog-result/assets \
  --out /tmp/english-catalog-review
```

`fetch` freezes source/notice bytes, URLs, authors, capture times and hashes; it
verifies an existing snapshot instead of refreshing it. `prepare` seals the complete
targets, source proofs, decoded baseline inventory and planned changes.
`adopt` re-extracts source evidence and dictionary bindings, then commits decisions
in resumable batches with an immutable journal. Repetition does not double-adopt.
Optional previous model vetoes remain vetoes; no model output establishes a word.
If `prepare` reports zero planned operations, no build is needed; retain the
baseline report as the result and inspect its unresolved targets.

`report.json`, `coverage.tsv` and `unresolved.jsonl` distinguish existing spellings,
new normalized spellings, case variants, metadata-only operations and blocked
evidence/format/binding cases, with core/extended and per-topic denominators. A
registered spelling means an actual decoded candidate under some real reading; it
does not assert typing, completion or ranking behavior. Coverage of overlapping
topics is not additive. Reports and all downloaded sources remain outside Git.
Targets retain kind/entity identity, so a shared display spelling can have several
targets. Coverage denominators count targets; newly registered spelling totals
count distinct display strings.

`fetch-world` freezes the Wikimedia API responses, QUDT Turtle and ChEBI OBO data,
full license texts and attribution, together with both scope hashes. It paces new
downloads and retries HTTP 429/503 with bounded backoff; cached responses are reused.
Existing snapshots are verified rather than refreshed. Source APIs are contacted
only during fetching, and never during adoption, ordinary builds or CI replay.

[Named-entity requirements](data/catalog/world-entities.json) declare the desired
spelling, kind, English article and selection reason before adoption. Wikidata
evidence uses exact English/default (`mul`) labels or aliases, or an exactly
matching English sitelink title. No disambiguation suffix is stripped. A personal
entity must have a non-deprecated human statement. These are project-curated
requirements with spelling evidence, not measured input-frequency rankings or a
claim that all Wikidata items are useful IME entries.

Wiktionary evidence requires an English section. An explicit `en-noun` head can
establish a nominal lemma; it does not generate inflections. ESDB head records are
preferred over a different lemma's participle (for example, the noun `kerning`
does not inherit the verb `kern` merely because its record appears first).
QUDT contributes English quantity-kind labels; ChEBI contributes non-obsolete
three-star curated names and exact synonyms only. Definitions, quotations and
source articles stay outside Git. Unsupported new spellings remain in the audit
with their original spelling and reason.

`catalog_review.py export` emits an external `adopted.tsv`, unique-spelling counts
and a ready-to-paste PR word list with expandable per-category sections. It verifies
every listed candidate and exact lexical/topic binding in the supplied binary
assets first. [adopted-world.tsv](data/catalog/adopted-world.tsv) is the compact
public adoption ledger for this expansion: spellings, kinds, categories, change
types, lexical identities, source links, licenses and entity IDs. This requested
dictionary data is committed; raw responses and operational reports are external.
Inspect it directly on GitHub, download it as TSV, or read the full lists in the PR.
Large releases also provide small category-specific TSV pages under
[`data/catalog/words`](data/catalog/words), linked from the PR's count table.
CI verifies the ledger against regenerated assets and checks every category page
against that ledger (including page boundaries, spellings, kinds and change types):

```sh
python3 -B english-ime/tools/catalog_review.py verify \
  --assets /tmp/reviewed-english-extended
```

Counts distinguish new display spellings (including case variants) from existing
spellings receiving metadata. Categories overlap and must not be summed.
The review ledger lists only topic memberships assigned by this operation, not
previously registered related topics; `topics=-` denotes domain-only annotations.
Source existence, a Wikipedia article, and popularity are separate signals. The current
core selection uses explicit required lists; it imports no page-view ranking or public
name-frequency statistics and makes no global coverage claim.

### Discover candidates beyond the regression list

The fixed required-word catalog is a regression benchmark, not an acquisition cap.
`discover` independently enumerates source classes/categories using
[discovery-policy.json](data/catalog/discovery-policy.json): Wikidata human
occupations and product/brand/organization/service classes, and English Wiktionary
technical categories. It follows pagination and merges source IDs and exact
spellings. Discovered targets have the `extended` tier and separate identities;
they do not add requirements to an existing core benchmark item.

```sh
python3 -B english-ime/tools/catalog_harness.py discover \
  --source-dir /tmp/english-discovery --max-requests 120 \
  --max-new-pages-per-selector 2
python3 -B english-ime/tools/catalog_harness.py prepare \
  --work-dir /tmp/english-discovery-run --assets /tmp/reviewed-english-extended \
  --source-dir /tmp/english-catalog-sources --discovery-dir /tmp/english-discovery \
  --lexical-source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
```

Request/page settings bound source traffic per invocation, not adopted word counts.
Zero pages means no per-selector request cap. Sealed snapshots record actual rows,
source hashes and continuation/status for every selector. Budget stops, timeouts
and rate limits remain explicitly incomplete; partial data is not reported as
source exhaustion. Successful pages remain usable. Resume into a **new** snapshot:

```sh
python3 -B english-ime/tools/catalog_harness.py discover \
  --source-dir /tmp/english-discovery-next --resume-from /tmp/english-discovery \
  --max-new-pages-per-selector 1
```

Prior snapshots/decisions remain reproducible. Untouched fields are visited before
extending large fields. Wikidata uses declared direct classes/occupations, an
English article and a minimum number of language sitelinks: an explicit source
breadth proxy, not IME input frequency. Wiktionary supplies direct members of
declared English topical categories. Neither path invents words or aliases.
Existing format/exclusion gates and real-binary audits still apply. The funnel
distinguishes source rows, distinct targets, existing spellings, new spellings,
annotations, withholding and pending source work.

Combine batches relative to the PR's actual parent inventory so an earlier addition
is not counted as an existing word merely because a later batch adds another topic:

```sh
python3 -B english-ime/tools/catalog_review.py publish \
  --ledger /tmp/first-adopted.tsv --ledger /tmp/next-adopted.tsv \
  --parent-inventory /tmp/first-run/baseline.jsonl \
  --assets /tmp/latest-result/assets --out /tmp/english-publication
```

This verifies the combined ledger against the latest binaries and emits unique
counts, a category count/link table, and 500-word TSV pages for browsing on GitHub.

For missing MDN evidence, `fetch-references --work-dir /tmp/english-catalog-run
--source-dir /tmp/english-catalog-new-sources` can add official glossary pages to a
copy of a source snapshot. It records download failures. Prepare a **new** run from
the enriched snapshot; a sealed run never changes its target/evidence inputs.

Supplement schema v2 adds `categories.tsv` (topic definitions) and `metadata.tsv`
(topic/domain memberships attached to exact existing lexical identities), with
manifest checksums. Schema v1 replay remains supported. Existing punctuation such
as an already encoded `C++` can receive metadata without new readings; unsupported
**new** labels remain blocked. The binary category format remains ECAT1. Build
replays fresh inputs and verifies all previous reading/surface/cost pairs, lexical
analyses and memberships, plus full/runtime parity. These are JVM checks; Android
IME compatibility remains unverified for these additions.

Additional source notices accompany the adopted data:

| Source | License / attribution |
| --- | --- |
| [Python glossary](https://github.com/python/cpython/blob/3.14/Doc/glossary.rst) | [PSF 2.0 and bundled terms](https://github.com/python/cpython/blob/3.14/LICENSE), Python Software Foundation and contributors |
| [PostgreSQL glossary](https://github.com/postgres/postgres/blob/REL_18_STABLE/doc/src/sgml/glossary.sgml) | [PostgreSQL](https://github.com/postgres/postgres/blob/REL_18_STABLE/COPYRIGHT), PostgreSQL Global Development Group / University of California |
| [.NET ML glossary](https://github.com/dotnet/docs/blob/main/docs/machine-learning/resources/glossary.md) | [CC BY 4.0](https://github.com/dotnet/docs/blob/main/LICENSE), Microsoft and .NET documentation contributors |
| [Transformers glossary](https://github.com/huggingface/transformers/blob/main/docs/source/en/glossary.md) | [Apache 2.0](https://github.com/huggingface/transformers/blob/main/LICENSE), Hugging Face and contributors |
| [Kubernetes glossary](https://kubernetes.io/docs/reference/glossary/) | [CC BY 4.0](https://github.com/kubernetes/website/blob/main/LICENSE), Kubernetes documentation contributors |
| [Linguist language names](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml) | [MIT](https://github.com/github-linguist/linguist/blob/main/LICENSE), GitHub and Linguist contributors |
| [Wikidata structured data](https://www.wikidata.org/wiki/Wikidata:Licensing) | CC0 1.0, Wikidata contributors |
| [Wiktionary English headwords](https://en.wiktionary.org/wiki/Wiktionary:Copyrights) | CC BY-SA 4.0, Wiktionary contributors; no external quotations imported |
| [QUDT quantity kinds](https://qudt.org/) | [CC BY 4.0](https://github.com/qudt/qudt-public-repo/blob/main/LICENSE), QUDT.org contributors |
| [ChEBI names and exact synonyms](https://www.ebi.ac.uk/chebi/about/) | CC BY 4.0, EMBL-EBI / ChEBI contributors |

NGSL, ESDB, WordNet, MDN and Homebrew terms/attribution from the acquisition section
below are retained. Data licenses apply separately from the program's MIT license.
This workflow makes **zero external AI API calls**, has no paid fallback and does
not install a schedule. It can be operated manually using public sources.

## Grow the vocabulary with a resumable review harness

For category-balanced dictionary acquisition, use `--profile dictionary` in the
section below. The default `vocabulary` profile retains the earlier lexical-only
mining policy; `dictionary_sources.py adopt` is the adoption command for the new profile.

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

For additional acquisition, [`gemini_acquisition.py`](tools/gemini_acquisition.py)
prioritizes the topics in [gemini-acquisition-policy.json](data/catalog/gemini-acquisition-policy.json)
that have at most 50 actual candidate spellings. It counts unique display spellings
with real topical memberships, excluding grammar-only supporting forms. The policy
covers 40 sparse topics across daily vocabulary, non-Web technical fields and names;
large science/person/car categories are not the focus of this pass.

```sh
python3 -B english-ime/tools/gemini_acquisition.py prepare \
  --assets /tmp/parent-english-assets --work-dir /tmp/english-sparse-leads
python3 -B english-ime/tools/gemini_acquisition.py propose \
  --work-dir /tmp/english-sparse-leads --free-proof /private/path/free-tier-proof.json \
  --api-key-file /private/path/gemini-key --max-requests 10 --wait
python3 -B english-ime/tools/gemini_acquisition.py fetch-evidence \
  --work-dir /tmp/english-sparse-leads --source-dir /tmp/english-catalog-sources \
  --lexical-source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
python3 -B english-ime/tools/catalog_harness.py prepare \
  --assets /tmp/parent-english-assets --work-dir /tmp/english-sparse-run \
  --gemini-dir /tmp/english-sparse-leads --source-dir /tmp/english-catalog-sources \
  --lexical-source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
python3 -B english-ime/tools/catalog_harness.py adopt --work-dir /tmp/english-sparse-run
python3 -B english-ime/tools/catalog_harness.py build \
  --work-dir /tmp/english-sparse-run --out /tmp/english-sparse-result
python3 -B english-ime/tools/gemini_acquisition.py coverage \
  --work-dir /tmp/english-sparse-leads --assets /tmp/english-sparse-result/assets \
  --out /tmp/english-sparse-coverage
```

Gemini proposes approximately 100 practical spellings per topic in small groups.
This is a requested yield, not a maximum number of words adopted. Exact repeated
leads are merged, and unused article hints for ordinary words are ignored.
Conflicting named-entity titles, unexpected topics, incomplete generations and
changed saved responses are rejected. Requests are reserved in the **same** project
quota ledger as vocabulary review, including failed/unknown requests. Completed
responses resume without a model call; inspect failed attempts before using
`--retry-failed`. That flag first revalidates saved output, preserving its history.
An existing macOS Keychain item can be used with `--keychain-service SERVICE`
instead of a key file; its account must match the free-project proof.

Model output never supplies a spelling proof or data license. Ordinary words must
match pinned ESDB/WordNet data or an exact Wiktionary headword with an English
section. Named spellings must match an English/default Wikidata label, alias or
English article title; human/nonhuman checks also apply. No model-only proposal
may annotate even an already existing candidate. Ordinary-word POS and inflections
come from the dictionary adapters. Proper-name roles follow the declared entity
kind. **Kind/topic placement is proposed by Gemini and may receive explicit
corrections; spelling attestation does not independently verify placement, sense
or input frequency.** Raw requests, responses, source payloads and operational reports
remain outside Git. Sealed evidence is rechecked at adoption, without API calls.
No recurring execution is added.

Source failures stay explicitly pending. Resume them into a **new** directory,
reusing the completed model responses and verified source pages without more model
calls; the earlier sealed snapshot remains unchanged:

```sh
python3 -B english-ime/tools/gemini_acquisition.py resume-evidence \
  --work-dir /tmp/english-sparse-leads --out /tmp/english-sparse-leads-next \
  --source-dir /tmp/english-catalog-sources \
  --lexical-source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
```

Prepare a new catalog run with `--gemini-dir /tmp/english-sparse-leads-next`.

The first build is staging for checking names. Before publishing, export its
binary-verified ledger and run the focused name review to separate products,
brands, organizations, services and capitalized generic article headings:

```sh
python3 -B english-ime/tools/catalog_review.py export \
  --work-dir /tmp/english-sparse-run --assets /tmp/english-sparse-result/assets \
  --out /tmp/english-sparse-review
python3 -B english-ime/tools/gemini_acquisition.py review-names \
  --work-dir /tmp/english-sparse-leads-next --ledger /tmp/english-sparse-review/adopted.tsv \
  --out /tmp/english-name-review --free-proof /private/path/free-tier-proof.json \
  --api-key-file /private/path/gemini-key
```

This is another explicit call within the same model/project quota, with no paid
fallback. A generic heading such as `Softbox` is deferred as a product name; it is
never silently lowercased into a new lexical spelling. Inspect the model's kind
and topic decisions. Corrections can be finalized into a new external directory:

```sh
python3 -B english-ime/tools/gemini_acquisition.py finalize-names \
  --work-dir /tmp/english-sparse-leads-next --review-dir /tmp/english-name-review \
  --decisions /tmp/name-topic-corrections.json --out /tmp/english-name-review-final
```

The correction JSON is an array of `surface`, `kind`, `topics`, `decision` and
`reason` records, limited to already reviewed spellings and declared topics.
It cannot invent a word, rewrite its spelling or supply a spelling proof. Prepare
a **new** catalog run against the same parent using `--gemini-named-review-dir
/tmp/english-name-review-final`, then adopt/build/export that run. Both model
decisions and explicit corrections remain hash-pinned in the final provenance.

The stacked expansion has its own [adoption ledger](data/catalog/adopted-sparse.tsv)
and [category pages](data/catalog/words-sparse), with the same spelling/source/license
columns and binary/page verification as the earlier world-vocabulary expansion.

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
Only adopted `supplement/entries.tsv`, optional v2 `metadata.tsv`/`categories.tsv`,
its manifest and required notices belong in the data change; the generated binaries
and verification report do not.

Evaluation cases are frozen external JSONL records with exactly `id`, `input`,
`expected`, `mode` (`exact`/`prefix`), `domain` and an HTTPS `source`. Use a pinned
held-out corpus, not the training sources used for candidate selection. Coverage
includes all cases, including missing words. Ranking uses a deterministic sample
of at most 200 cases, balanced across available domains and ordered by hashed ID,
configurable with `--sample-size`. Reports keep
separate denominators and domain counts; literal input echo, including partially copied words, is never a dictionary
hit. A report records case and asset hashes and cannot overwrite an earlier run.
The evaluation is JVM CLI evidence, not verification of an Android IME.

## 辞書を充実させる / Acquire dictionary vocabulary

辞書向けの `--profile dictionary` は、基本語・日常語・表記・活用形・技術語・商品名・人名を
出典から収集し、既存の実バイナリと表記単位で比較します。誤字訂正・候補順位はIME側の仕事であり、
この収集・採用ハーネスの評価対象には含めません。定期実行は設定しません。

The dictionary profile acquires attested words and forms; it does not generate typo
cases or evaluate IME ranking. It uses the existing prepare/review/build/status
checkpoints and binary audits. All acquisition data and work files stay outside Git.

```sh
python3 -B english-ime/tools/dictionary_sources.py fetch \
  --source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
python3 -B english-ime/tools/vocabulary_harness.py prepare --profile dictionary \
  --work-dir /tmp/english-dictionary-run --assets /tmp/reviewed-english-extended \
  --source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb \
  --max-candidates 1000
python3 -B english-ime/tools/dictionary_sources.py adopt \
  --work-dir /tmp/english-dictionary-run \
  --source-dir /tmp/english-dictionary-sources --esdb-dir /tmp/english-esdb
python3 -B english-ime/tools/vocabulary_harness.py status \
  --work-dir /tmp/english-dictionary-run
python3 -B english-ime/tools/vocabulary_harness.py build \
  --work-dir /tmp/english-dictionary-run --out /tmp/english-dictionary-result
```

| 対象 / Facet | 取得・確認方法 / Evidence | License |
| --- | --- | --- |
| 基本語 / basic | NGSL 1.2・Spoken・補助語の見出しからESDBの実在語形を選ぶ / basic-list headwords select attested ESDB forms | NGSL: CC BY-SA 4.0; ESDB: component notices |
| 日常語 / daily | ESDB、WordNetとEWT trainの観測語形 / lexical records and observed training forms | Existing pinned source notices |
| 活用形 / inflection | ESDBのlemma・品詞・語形コード / source paradigms, including irregular forms | ESDB Copyright and Sources |
| 表記 / orthography | 同じ読みの大文字・小文字違いも正確な出典表記で保持 / exact source display case | Respective source license |
| 技術語 / technology | MDN Glossaryのリンク名と参照先 / glossary labels and URLs | CC BY-SA 2.5 or later |
| 商品名 / product | Homebrew Caskのname欄 / published product display labels | BSD 2-Clause |
| 人名 / person | ESDBでperson・surnameとされた見出し / attested given-name/surname spellings | ESDB component notices |

Source lists do not authorize mechanically generating inflections or treating source
capitalization as a canonical spelling. Each adopted form comes from an ESDB record
with lemma/POS, or a literal named catalog label. The source-list `TRUE/FALSE`
spellings do not manufacture uppercase dictionary entries. Names are collected as
heads without generating possessives; technical labels receive a technology domain
without guessing English POS. Product display names are not package tokens, and
product names receive no inferred inflections. Disabled/deprecated casks are skipped.
An inflection additionally needs two observed whole-form witnesses with its source
lemma and matching POS in the pinned EWT training data. Common lemma/POS usage alone
does not license an unobserved secondary paradigm (for example, `hide` does not
automatically promote `hided`). Insufficient usage evidence defers a source-attested form for review;
it does not declare the word invalid or the corpus exhaustive.
This is a given-name/surname source, not a catalog of full names of famous people.

Selection cycles across seven facets, with a per-facet ceiling of
`ceil(max-candidates / 7)`, and removes duplicate display spellings. Facets overlap:
one spelling can be a person, a product, and an orthographic addition. Counts must
not be summed as unique words. The ceiling limits draws from a bucket; overlapping
membership counts can exceed it. A cap of 1,000 can yield fewer than 1,000 selected
spellings while other categories still have candidates. Missing categories are not
filled with extra names. Products use a frozen 90-day Homebrew installation-rank
snapshot as a catalog-specific priority signal, not general language frequency or
a product recommendation. Each facet retains its own priority when spellings overlap.

`dictionary-withheld.jsonl` records already registered spellings, base exclusions,
unsupported format and category failures. The present supplement format accepts
ASCII letters/digits, spaces, apostrophes, dots, slashes and hyphens, up to 64
characters. Labels containing `+`, `#`, or unsupported Unicode are withheld with
the exact original label; they are never rewritten to a different name. Supporting
more such labels requires a separately verified dictionary-format change.

`adopt` re-extracts every selected candidate from the frozen inputs, verifies the
snapshot and notices, and records source-based decisions. It makes no model/API
calls and is not a human-review claim. Optional existing Gemini review can veto a
candidate; model output alone supplies neither a spelling nor an inflection.
Repeated adoption is idempotent. Build requires final source decisions, preserves
all previous reading/surface/cost pairs, and audits added pairs and lexical roles
in both full and packed binaries. Case variants such as `May` alongside `may` are
allowed; identical existing display spellings and base exclusions remain blocked.
No change to IME search, typo correction or ranking is part of this profile.

The external source manifest records snapshot dates/hashes, source URLs, license
identifiers, authors and full notice files. The resulting supplement manifest and
notices retain these records and transformation descriptions for redistribution.
The code's MIT license does not replace the data licenses. No definitions, source
articles, software installers, program code, logos or images are imported.

- [NGSL licensing](https://www.newgeneralservicelist.com/new-general-service-list)
- [NGSL-Spoken licensing](https://www.newgeneralservicelist.com/ngsl-spoken)
- [ESDB Copyright](https://github.com/en-wl/wordlist/blob/1e5b7d3a72f47a71da5d28686c1dd4b397178485/Copyright)
- [MDN licensing](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license)
- [Homebrew Cask license](https://github.com/Homebrew/homebrew-cask/blob/main/LICENSE)

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
