# Kotlin Kana-Kanji Converter

[![Build and Release](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml/badge.svg)](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml)

Kotlin で実装されたかな漢字変換エンジンです。  
LOUDS ベースの辞書構造、トークン配列、接続コスト、Viterbi / n-best 探索を組み合わせて、ひらがな入力から変換候補を生成します。

## Overview

このリポジトリは、かな漢字変換に必要な以下の要素をひとまとめにしています。

- 辞書ソースからのアーティファクト生成
- 変換エンジン本体
- 単漢字・ことわざなどの補助辞書
- 精度および辞書生成の回帰テスト

現在の変換エンジンは、メイン辞書に加えて `singleKanji` と `kotowaza` の補助辞書を同一ラティス上で扱います。

## Key Capabilities

- LOUDS Trie による読み・表記辞書の圧縮表現
- 接続コストと単語コストを用いた Viterbi / n-best 探索
- 補助辞書を含む複数辞書の統合探索
- 辞書ビルド回帰テスト
- Mozc evaluation データを用いた精度回帰テスト

## Repository Layout

```text
src/main/kotlin/
  engine/           変換エンジン
  graph/            ラティス構築
  path_algorithm/   経路探索
  dictionary/       トークン配列・辞書モデル
  louds/            LOUDS 実装

src/main/resources/
  *.dat             生成済み辞書アーティファクト
  dictionary*.txt   辞書ソース

src/test/kotlin/
  engine/           精度評価テスト
  integration/      辞書ビルド統合テスト

src/test/resources/engine/
  mozc_evaluation.tsv
  mozc_evaluation_baseline.properties
```

## Requirements

- JDK 17
- Gradle Wrapper

macOS の例:

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew test
```

## Quick Start

リポジトリを取得してテストを実行します。

```bash
git clone https://github.com/KazumaProject/kotlin-kana-kanji-converter.git
cd kotlin-kana-kanji-converter
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew test
```

辞書アーティファクトを再生成する場合は以下を実行します。

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew run
```

## Evaluation

### 1. Mozc Evaluation Regression Test

`src/test/resources/engine/mozc_evaluation.tsv` に Mozc evaluation データを格納し、`OK:` 行を対象に回帰テストを実行します。

テストでは主に次を検証します。

- `Conversion Expected`: top1 が期待候補と一致すること
- `Conversion Expected N`: topN に期待候補が含まれること
- `Conversion Match`: top1 に指定語が含まれること
- `Conversion Not Match`: top1 に指定語が含まれないこと

また、`mozc_evaluation_baseline.properties` に保存したベースラインに対して、通過件数が悪化していないことを確認します。

精度テストのみを実行する場合:

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew test --tests engine.KanaKanjiEngineAccuracyTest
```

## Dictionary Build Verification

辞書生成の統合テストは通常の `test` に加えて、専用タスクでも実行できます。

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew dictionaryBuildTest
```

ベースラインを更新する場合:

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 17) ./gradlew updateDictionaryBuildBaseline
```

## Notes

- 補助辞書の一部は生成世代の差によって `pos_table` と互換性がずれることがあります。
- 変換精度を比較する際は、辞書アーティファクトを再生成したかどうかを揃えてください。
- `src/main/resources/*.dat` はビルド済み成果物です。辞書ソースを更新した場合は再生成が必要です。

## License

This project is licensed under the [MIT License](LICENSE).
