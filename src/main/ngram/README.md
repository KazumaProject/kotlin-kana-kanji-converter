# System n-gram source

JapaneseKeyboard does not read these text files. `buildSystemNgramDictionary` compiles them into the scoreless binary asset `app/src/main/assets/ngram/system_ngram.dat` inside the release ZIP.

Each non-comment line is one 2- to 5-gram rule:

```text
"服" + "を" + "着る"
"布" + "で" + pos("名詞") + "を" + "拭く"
"布" + "で" + * + "を" + "拭く"
```

- Add a rule by adding a line to any `.ngram` file.
- Edit the line to change a rule.
- Delete the line to delete a rule.
- Split rules into files by domain when useful.
- `score`, `cost`, and `adjustment` are intentionally rejected.
- `*` matches exactly one conversion node regardless of word or POS.

Build and verify:

```shell
./gradlew buildSystemNgramDictionary test --tests 'com.kazumaproject.ngram.*'
```
