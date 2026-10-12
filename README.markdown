# かな漢字変換プログラム

[![Build and Release](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml/badge.svg)](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml)

## 概要

このプログラムは、Kotlin
を使用して実装されたかな漢字変換システムです。ひらがなを入力すると、トライ構造とトークン配列を使用して効率的に漢字に変換されます。ビタビアルゴリズムを活用し、最適な変換結果を提供します。また、辞書ファイルはカスタマイズ可能で、さまざまな用途に応じた設定が可能です。

## 特徴

- ひらがなから漢字への迅速な変換
- カスタマイズ可能な辞書ファイル
- トライ構造による柔軟なデータ処理
- ビタビアルゴリズムを使用した最適な経路選択

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

unigramは、現在のJapaneseKeyboardと同じく、候補経路内の各ノードに照合します。1ノードの表記が一致すると複合候補全体も優先されます。「入力全体が完全一致したときだけ」という条件ではありません。「しろ」の優先ルールは、「しろ＋医」などが「白い」より上位になるため取り消しました。「したい」「なら」の優先ルールも取り消しました。通常辞書の品詞・コストは変更していません。

```bash
./gradlew --quiet convertCandidates --args='--count 5 なのか しろ'
```

読みごとに1行のJSONを出力します。`rank` は1から始まります。以下は先頭2件の出力例です。

```json
{"input":"なのか","candidates":[{"rank":1,"text":"なのか"},{"rank":2,"text":"七日"}]}
{"input":"しろ","candidates":[{"rank":1,"text":"白"},{"rank":2,"text":"しろ"}]}
```

`--count` を省略すると候補を10件まで返します。生成済みの変換辞書がない環境では、Mozc辞書リソースを準備したうえで先に `./gradlew run` を実行してください。使い方は `./gradlew --quiet convertCandidates --args='--help'` で確認できます。

`src/main/resources/ngram` に生成済みの `system_ngram.dat` と `system_ngram_unigram.dat` がある場合は、それぞれ候補の再順位付けに使います。生成するには `./gradlew buildSystemNgramDictionary buildSystemUnigramDictionary` を実行してください。

「しろ」「したい」「なら」の優先を取り消すには、新しく生成した `system_ngram_unigram.dat` に置き換える必要があります。JapaneseKeyboardで利用するときは、配布ZIPの `app/src/main/assets/ngram/system_ngram_unigram.dat` を使用してください。既存の `v1.7.259` のファイルには問題のルールが残っています。

CLIはunigramの照合範囲・表記の重複排除・一致候補を優先してからコスト順にする処理をJapaneseKeyboardに合わせています。JapaneseKeyboardの文節判定、ビーム探索、学習辞書、予測候補、UI全体の表示順位まで同一とは保証しません。利用側を確認するときは実際のcheckoutと配布されたバイナリを使って検証してください。

## ライセンス

このプロジェクトは [MIT ライセンス](LICENSE) のもとで提供されています。

ただし、生成される辞書データには JMdict/JMdict_e（CC BY-SA 4.0）および Mozc
辞書資源（IPAdic、ICOT、沖縄辞書など）の個別条件が適用されます。出典と条件の整理は
リポジトリ内の [`THIRD-PARTY-NOTICES.md`](src/main/resources/THIRD-PARTY-NOTICES.md) を確認してください。

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

Unigram rules match each node in a candidate path, as in the current JapaneseKeyboard implementation. A matching node promotes the complete candidate, including compound candidates. These rules are not restricted to a whole-input, single-node path. The `しろ` rule has been removed because it promotes paths such as `しろ` + `医` above `白い`. The `したい` and `なら` preferences have also been withdrawn. Replace the deployed unigram binary with the newly generated asset; the v1.7.259 binary still contains the rule.

The CLI follows JapaneseKeyboard's unigram matching scope, first-distinct-surface matching, and match-before-cost ranking. It does not reproduce every segmentation, beam search, learned dictionary, prediction, or UI stage. Verify consumer behavior against the actual checkout and shipped binary before claiming app-level parity.

## License

This project is licensed under the [MIT License](LICENSE).
