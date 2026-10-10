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

「なのか」「しろ」の優先はunigram辞書に収録しています。JapaneseKeyboardの既存処理により、入力全体を1つの辞書語で変換した候補だけに適用されます。文中の一部分には適用されず、通常辞書の品詞・コストは変更しません。CLIもこのunigramの適用条件に合わせて検証します。

```bash
./gradlew --quiet convertCandidates --args='--count 5 なのか しろ'
```

読みごとに1行のJSONを出力します。`rank` は1から始まります。以下は先頭2件の出力例です。

```json
{"input":"なのか","candidates":[{"rank":1,"text":"なのか"},{"rank":2,"text":"七日"}]}
{"input":"しろ","candidates":[{"rank":1,"text":"しろ"},{"rank":2,"text":"白"}]}
```

`--count` を省略すると候補を10件まで返します。生成済みの変換辞書がない環境では、Mozc辞書リソースを準備したうえで先に `./gradlew run` を実行してください。使い方は `./gradlew --quiet convertCandidates --args='--help'` で確認できます。

`src/main/resources/ngram` に生成済みの `system_ngram.dat` と `system_ngram_unigram.dat` がある場合は、それぞれ候補の再順位付けに使います。生成するには `./gradlew buildSystemNgramDictionary buildSystemUnigramDictionary` を実行してください。

「なのか」「しろ」の優先を確認するには、更新した `system_ngram_unigram.dat` が必要です。JapaneseKeyboardで利用するときも、生成したファイルを `app/src/main/assets/ngram/system_ngram_unigram.dat` として配置してください。

解析したJapaneseKeyboardの文節モードは、この優先順を最終候補にも維持します。一方、通常モードは最終候補をコスト順に並べ直すため、unigram辞書だけでは表示上の1位を保証できません。CLIは辞書ルールの適用条件を検証するもので、アプリ全体の表示順位を再現するものではありません。

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

The hiragana preferences are stored in the unigram asset. JapaneseKeyboard applies them only to a whole-input, single-node candidate, and the CLI follows that condition. Normal dictionary costs and POS IDs are unchanged. Rebuild the unigram asset for verification and ship it as `app/src/main/assets/ngram/system_ngram_unigram.dat` in JapaneseKeyboard.

In the inspected JapaneseKeyboard source, bunsetsu mode preserves that priority in its final candidates. Normal mode sorts final candidates by cost again, so the unigram asset alone cannot guarantee first place in that mode. The CLI verifies the dictionary rule's matching condition rather than reproducing all app ranking stages.

## License

This project is licensed under the [MIT License](LICENSE).
