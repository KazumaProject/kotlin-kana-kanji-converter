# System n-gram source

JapaneseKeyboard does not read these text files. `buildSystemNgramDictionary` compiles them into the scoreless binary asset `app/src/main/assets/ngram/system_ngram.dat` inside the release ZIP.

Unigram rules are maintained separately under `src/main/ngram-unigram`. The
`buildSystemUnigramDictionary` task compiles those one-word rules into the
version-4 asset `app/src/main/assets/ngram/system_ngram_unigram.dat`. Keeping
this file separate leaves the existing version-3 n-gram asset unchanged.

The ATOK archives analyzed for this branch contain 471 unique unigram pairs.
They are kept as one-word rules in `../ngram-unigram/atok-unigram.ngram` and as
dictionary records in `src/main/resources/atok-unigram-dictionary.txt`. The
converter loads the dedicated dictionary, removes exact `(読み, 表記)` pairs
already present in the base/custom dictionaries, and adds only the 273 missing
pairs to the normal system yomi/tango/token assets. This is required because a
unigram priority rule cannot create a candidate that the graph dictionary did
not generate. Each imported rule keeps its `読み -> 改善後` pair in the
preceding comment for auditing.

Each non-comment line is one 2- to 5-gram rule:

```text
"服" + "を" + "着る"
"布" + "で" + pos("名詞") + "を" + "拭く"
"布" + "で" + * + "を" + "拭く"
words("kaitai.words") + "を" + "解体"
```

- Add a rule by adding a line to any `.ngram` file.
- Edit the line to change a rule.
- Delete the line to delete a rule.
- Split rules into files by domain when useful.
- `score`, `cost`, and `adjustment` are intentionally rejected.
- `*` matches exactly one conversion node regardless of word or POS.
- `words("name.words")` expands to one rule for every word in the referenced file.

Each non-comment line in a `.words` file is one word. A word list can reuse another
list relative to its own directory; includes are treated as a set, so repeated words
are emitted only once:

```text
@include "appliance.words"
家
建物
```

Word-list references must remain inside this source directory. Missing files,
invalid extensions, empty lists, and include cycles fail the build.

## Unigram source

Each non-comment line in `src/main/ngram-unigram/*.ngram` is exactly one
literal word. POS features, wildcards, multi-word rules, and score fields are
rejected for this source. The existing `src/main/ngram` files remain limited
to 2- to 5-gram rules.

`atok-unigram-dictionary.txt` uses the standard five-column Mozc dictionary
format. Its 471 records are deliberately separate from `dictionary00.txt`-
`dictionary09.txt`; `Main.kt` performs exact-pair de-duplication before
building the normal dictionary. ATOK's HTML does not publish POS IDs or costs,
so newly added records use the same-reading/same-surface metadata when
available and otherwise the safe noun context `名詞,一般` (`1851/1851`) with
cost `9000`. The separate unigram binary supplies the actual priority, while
the conservative cost prevents these additions from globally replacing normal
context scoring when no ATOK rule matches.

The JVM converter can load the same packed assets for an end-to-end candidate
test. `KanaKanjiEngine` keeps the normal Viterbi result unchanged and promotes
only candidates whose node path matches a loaded scoreless rule:

```kotlin
val ngram = PackedSystemNgramDictionary.fromFile(File("system_ngram.dat"))
val unigram = PackedSystemUnigramDictionary.fromFile(File("system_ngram_unigram.dat"))
val engine = KanaKanjiEngine(ngram, unigram).apply { buildEngine() }
```

The runtime tests build temporary v3/v4 assets from the checked-in sources,
then verify the actual candidate order. This also keeps tests independent of
ignored generated files under `src/main/resources/ngram`.

Build and verify:

```shell
./gradlew buildSystemNgramDictionary buildSystemUnigramDictionary test --tests 'com.kazumaproject.ngram.*'

./gradlew verifyJapaneseKeyboardDictionaryAssets
```
