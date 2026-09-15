# Quantity dictionary

`src/main/quantity` contains reviewed **quantity classes and contexts**, not an
enumeration of every number or every sentence. The consumer proves a span from
its input reading before a `quantity("本")` condition can match `3本`, `３本` or
`三本`. Matching a kanji or a text suffix alone is insufficient. User/learned
entries must not be reinterpreted as numeric forms.

## Sources and artifact

* `units.txt`: accepted semantic units, including compound units and the reserved
  `@registered` class (requires an enabled user-defined reading proof).
* `suffixes.tsv`: base unit, appended reading, appended output, separated by tabs.
  `分 / かん / 間` is distinct from `足 / ぶん / 分`; arbitrary suffix concatenation
  is not allowed. Inflected base readings remain the consumer's responsibility.
* `counter-readings.tsv`: reviewed readings for 1–10 across all counter classes.
  Missing readings reuse an existing numeric lexeme's output, POS and word cost.
  For example, Mozc has numeric 三本 under さんぽん and a surname 三本 under
  さんぼん; the alias adds the numeric analysis without removing the surname.
  No row is synthesized when the upstream dictionary lacks a numeric lexeme.
  Arbitrary larger quantities are composed by the consumer using lexical metadata.
* `counters.ngram`: two to five literal word or quantity conditions. Unknown
  units, malformed syntax and duplicate rules fail compilation. No score column.
* `id.def`: numeric and counter POS context IDs come from the same Mozc checkout
  as the lexical dictionary and connection matrix. Never copy numeric IDs from a
  different release into an existing bundle.

`buildQuantityDictionary` produces `quantity/quantity.dat`, included in the normal
JapaneseKeyboard release ZIP. Its separate `JKQT` magic, version 5, payload length
and CRC32 protect the reader against mismatched/truncated/corrupt data. The
existing system n-gram v3 and unigram v4 formats are unchanged. Old consumers can
ignore this extra asset; new consumers must keep a fallback for an absent asset.

## Consumer contract and ranking

A quantity may span multiple adjacent lexical nodes. Word conditions retain their
lexical boundaries. Rules describe contexts, not numeric spelling priorities.
When several rules match, the most specific rule (number of conditions) wins;
ordinary lexical/connection/N-gram cost breaks ties. Generic quantity-first
rules must not replace a complete ordinary lexical reading (e.g. 発見だけ with
8件だけ). Literal semantic context before a quantity may disambiguate it. Numeric forms are expanded
only after path selection, in the user's configured order. They must not occupy
three independent slots during N-best search.

The IME searches the product of the lattice and each applicable quantity rule so
that a supported path is not lost merely because it lies outside the initial
N-best window. Supplemented readings use real numeric/counter lexical metadata,
including internal connection costs and lexical elements for N-gram evaluation.
The dictionary itself does not introduce a global numerical cost discount.
Rules are scoreless preferences; they do not guarantee the correct reading for
every ambiguous context. Review both positive and competing ordinary readings.

## Reproduce and release

Use the existing resource-download workflow (one Mozc revision; one resolved
JapaneseCorpus release with its checksum), then:

```
./gradlew buildQuantityDictionary quantityTest
./gradlew packageJapaneseKeyboardDictionaryAssets verifyJapaneseKeyboardDictionaryAssets test
```

The format tests cover split/joined spans, all three numerical notations,
protected entries, invalid data and ordinary words. Integration tests read newly
built dictionary files. Android consumer tests additionally cover all built-in
counter categories, user units, input edits, notation orders, candidate segments,
both conversion backends and the N-gram scoring contract. Emulator regression and
latency comparisons are required before publishing a consumer update.

PR builds validate/package without publishing. After review and passing checks,
merge and push a new unused `v*` tag. The existing GitHub Actions workflow creates
the formal dictionary release. Download the published ZIP, verify its manifest,
and rerun consumer tests against those exact assets before updating the IME PR.
Large downloaded corpora, generated `.dat` files and release ZIPs are build
outputs and stay out of Git; source rules, compiler, tests and this document are
versioned.
