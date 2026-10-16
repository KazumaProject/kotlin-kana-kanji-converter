# かな漢字変換プログラム

[![Build and Release](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml/badge.svg)](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml)

Web・Person・Place・Neologd・wikiの5辞書は28カテゴリ辞書に置き換えます。固定した分類結果から生成する配布形式、更新手順、利用側IMEで必要な変更は[分類辞書の生成と配布](docs/classified-dictionary-distribution.md)を参照してください。

各カテゴリの件数と全収録レコードの読み・表記・品詞ID・コストは[分類辞書の収録一覧](docs/classified-dictionary-catalog/index.md)で確認できます。

## 概要

このプログラムは、Kotlin
を使用して実装されたかな漢字変換システムです。ひらがなを入力すると、トライ構造とトークン配列を使用して効率的に漢字に変換されます。ビタビアルゴリズムを活用し、最適な変換結果を提供します。また、辞書ファイルはカスタマイズ可能で、さまざまな用途に応じた設定が可能です。

## 特徴

- ひらがなから漢字への迅速な変換
- カスタマイズ可能な辞書ファイル
- トライ構造による柔軟なデータ処理
- ビタビアルゴリズムを使用した最適な経路選択

かな→英語辞書の収録内容は、[英語表記・かな読みの全一覧](docs/english-dictionary-catalog.md)
で確認できます。上流と補完辞書を統合した採用結果を掲載しています。

## 自動ビルドとリリース

GitHub Actions を使用して、プッシュされたタグに基づいてビルドとリリースを自動化しています。このプロセスには、辞書ファイルのダウンロード、Kotlin
アプリケーションのビルド、アーティファクトの生成、および GitHub Release へのアップロードが含まれます。

## インストール

```bash
git clone https://github.com/KazumaProject/kotlin-kana-kanji-converter.git
cd kotlin-kana-kanji-converter
./gradlew build
```

## 使い方

1. 辞書ファイルを準備し、プログラムを実行します。
2. ひらがな文字列を入力すると漢字に変換されます。

候補をターミナルから確認するには、次のコマンドを使います。複数の読みを一度に渡せます。

既存の unigram（v4）は、候補経路内の各ノードを対象とする方式です。1ノードの表記が一致すると複合候補全体も優先されます。「入力全体が完全一致したときだけ」という条件ではありません。「しろ」の優先ルールは、「しろ＋医」などが「白い」より上位になるため取り消しました。「したい」「なら」「ごと」の優先ルールも取り消しました。修飾キー省略入力の「こと」から生成された「ごと」も表記一致で優先されるため、「ごと」のルールを削除しています。通常辞書の品詞・コストは変更していません。

```bash
./gradlew --quiet convertCandidates --args='--count 5 なのか しろ'
```

読みごとに1行のJSONを出力します。`rank` は1から始まります。以下は単体用辞書を生成した場合の先頭2件の出力例です。

```json
{"input":"なのか","candidates":[{"rank":1,"text":"なのか"},{"rank":2,"text":"七日"}]}
{"input":"しろ","candidates":[{"rank":1,"text":"しろ"},{"rank":2,"text":"白"}]}
```

`--count` を省略すると候補を10件まで返します。生成済みの変換辞書がない環境では、Mozc辞書リソースを準備したうえで先に `./gradlew run` を実行してください。使い方は `./gradlew --quiet convertCandidates --args='--help'` で確認できます。

`src/main/resources/ngram` に生成済みの `system_ngram.dat` と `system_ngram_unigram.dat` がある場合は、それぞれ候補の再順位付けに使います。生成するには `./gradlew buildSystemNgramDictionary buildSystemUnigramDictionary` を実行してください。

「しろ」「したい」「なら」「ごと」の優先を取り消すには、新しく生成した `system_ngram_unigram.dat` に置き換える必要があります。JapaneseKeyboardで利用するときは、配布ZIPの `app/src/main/assets/ngram/system_ngram_unigram.dat` を使用してください。既存の `v1.7.260` のファイルには「ごと」のルールが残っています。

単体入力用の別辞書（v5）には「しろ」「ごと」「したい」「はいる」「みた」「なにか」を登録しています。`./gradlew buildStandaloneUnigramDictionary` で生成すると CLI が読み込みます。入力全体と読み・表記が一致する1ノード経路だけを対象にし、既存の v4 ルールは維持します。[仕様・配布先・利用側で必要な対応](docs/standalone-unigram.md)を参照してください。JapaneseKeyboard 側の対応と実アプリでの検証は未実施です。

CLIはunigramの照合範囲・表記の重複排除・一致候補を優先してからコスト順にする処理をJapaneseKeyboardに合わせています。JapaneseKeyboardの文節判定、ビーム探索、学習辞書、予測候補、UI全体の表示順位まで同一とは保証しません。利用側を確認するときは実際のcheckoutと配布されたバイナリを使って検証してください。

## ライセンス

プログラムコードは [MIT ライセンス](LICENSE) のもとで提供されています。

辞書データには出典ごとの条件が適用されます。かな→英語の補完辞書はCC BY-SA 4.0で提供し、
JMdict・NGSLの出典表示と、CMUdict由来部分の著作権表示・条件・免責を維持します。
既存のMozc辞書資源にはIPAdic・ICOT・沖縄辞書などの条件があります。
[辞書データのライセンスと出典](LICENSE-DATA.md) および
[第三者表記](src/main/resources/THIRD-PARTY-NOTICES.md) を確認してください。

---

### English README

# Kana-Kanji Conversion Program

## Overview

This program is a kana-kanji conversion system implemented in Kotlin. It efficiently converts hiragana input to kanji by
leveraging trie structures and token arrays. The program uses the Viterbi algorithm to calculate the shortest path for
selecting the most suitable kanji from multiple candidates. Customizable dictionary files are supported to allow for
various uses.

## Features

- Fast conversion from hiragana to kanji
- Customizable dictionary files
- Flexible trie-based data processing
- Optimal path selection using the Viterbi algorithm

Browse the [complete English surface and kana reading catalog](docs/english-dictionary-catalog.md)
for the adopted entries from the upstream dictionary and curated supplement.

## Automated Build and Release

This project uses GitHub Actions to automate the build and release process based on pushed tags. The process includes
downloading dictionary files, building the Kotlin application, generating artifacts, and uploading them to GitHub
Releases.

## Installation

```bash
git clone https://github.com/KazumaProject/kotlin-kana-kanji-converter.git
cd kotlin-kana-kanji-converter
./gradlew build
```

## Usage

1. Prepare the dictionary files and run the program.
2. Input a hiragana string to convert it to kanji.

To inspect ranked candidates from a terminal, pass one or more readings:

```bash
./gradlew --quiet convertCandidates --args='--count 5 なのか しろ'
```

The command prints one JSON object per reading, with one-based candidate ranks. The default limit is 10 candidates. If generated conversion dictionaries are missing, prepare the Mozc dictionary resources and run `./gradlew run` first. Use `./gradlew --quiet convertCandidates --args='--help'` for usage.

Generated `system_ngram.dat` and `system_ngram_unigram.dat` files under `src/main/resources/ngram` are loaded when present for candidate reranking. Generate them with `./gradlew buildSystemNgramDictionary buildSystemUnigramDictionary`.

Unigram rules match each node in a candidate path, as in the current JapaneseKeyboard implementation. A matching node promotes the complete candidate, including compound candidates. These rules are not restricted to a whole-input, single-node path. The `しろ` rule has been removed because it promotes paths such as `しろ` + `医` above `白い`. The `したい`, `なら`, and `ごと` preferences have also been withdrawn. A modifier-key omission candidate can have a different reading from the input but still match the surface-only unigram rule; `こと` can generate `ごと` this way. Replace the deployed unigram binary with the newly generated asset; the v1.7.260 binary still contains the `ごと` rule.

A separate version-5 whole-input unigram asset contains `しろ`, `ごと`, `したい`, `はいる`, `みた`, and `なにか`. Generate it with `./gradlew buildStandaloneUnigramDictionary`. It promotes candidates with a single-node path covering the original input, with reading and surface both equal to that input. See [the contract and required consumer changes](docs/standalone-unigram.md). JapaneseKeyboard integration and app behavior have not been verified.

For the existing v4 dictionary, the CLI follows JapaneseKeyboard's unigram matching scope, first-distinct-surface matching, and match-before-cost ranking. It does not reproduce every segmentation, beam search, learned dictionary, prediction, or UI stage. Verify consumer behavior against the actual checkout and shipped binary before claiming app-level parity.

## License

The program code is licensed under the [MIT License](LICENSE).
Dictionary data retains its source-specific licenses, including CC BY-SA 4.0
for the curated English supplement and the CMUdict notice for its derived material.
See [data licenses and attribution](LICENSE-DATA.md) and
[third-party notices](src/main/resources/THIRD-PARTY-NOTICES.md).
