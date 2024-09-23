# かな漢字変換プログラム
[![Build and Release](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml/badge.svg)](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/build-and-release.yml)

## 概要

このプログラムは、Kotlin を使用して実装されたかな漢字変換システムです。ひらがなを入力すると、トライ構造とトークン配列を使用して効率的に漢字に変換されます。ビタビアルゴリズムを活用し、最適な変換結果を提供します。また、辞書ファイルはカスタマイズ可能で、さまざまな用途に応じた設定が可能です。

## 特徴

- ひらがなから漢字への迅速な変換
- カスタマイズ可能な辞書ファイル
- トライ構造による柔軟なデータ処理
- ビタビアルゴリズムを使用した最適な経路選択

## 自動ビルドとリリース

GitHub Actions を使用して、プッシュされたタグに基づいてビルドとリリースを自動化しています。このプロセスには、辞書ファイルのダウンロード、Kotlin アプリケーションのビルド、アーティファクトの生成、および GitHub Release へのアップロードが含まれます。

## インストール

```bash
git clone https://github.com/your-repo/kana-kanji-conversion.git
cd kana-kanji-conversion
./gradlew build
```

## 使い方

1. 辞書ファイルを準備し、プログラムを実行します。
2. ひらがな文字列を入力すると漢字に変換されます。

## ライセンス

このプロジェクトは [MIT ライセンス](LICENSE) のもとで提供されています。

---

### English README

# Kana-Kanji Conversion Program

## Overview

This program is a kana-kanji conversion system implemented in Kotlin. It efficiently converts hiragana input to kanji by leveraging trie structures and token arrays. The program uses the Viterbi algorithm to calculate the shortest path for selecting the most suitable kanji from multiple candidates. Customizable dictionary files are supported to allow for various uses.

## Features

- Fast conversion from hiragana to kanji
- Customizable dictionary files
- Flexible trie-based data processing
- Optimal path selection using the Viterbi algorithm

## Automated Build and Release

This project uses GitHub Actions to automate the build and release process based on pushed tags. The process includes downloading dictionary files, building the Kotlin application, generating artifacts, and uploading them to GitHub Releases.

## Installation

```bash
git clone https://github.com/your-repo/kana-kanji-conversion.git
cd kana-kanji-conversion
./gradlew build
```

## Usage

1. Prepare the dictionary files and run the program.
2. Input a hiragana string to convert it to kanji.

## License

This project is licensed under the [MIT License](LICENSE).