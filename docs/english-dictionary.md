# ひらがな読み→英語辞書

このプロジェクトでは、[JapaneseCorpus v2026.0810.7](https://github.com/KazumaProject/JapaneseCorpus/releases/tag/v2026.0810.7) の `mozc-english-unigram-00000.txt.zst` を `english-dictionary.txt` として展開し、通常のシステム辞書とは別の `english_reading` 辞書を生成する。

## 変換の意味

これは日本語文を英訳する辞書ではない。JMdict のうち、読みが Unicode カタカナブロックだけで構成された項目を選び、NFKC 正規化後にひらがなへ変換した読みをキーにする。英語の `gloss` と完全な `lsource` が英語候補になるため、例えば次のような変換を作れる。

```text
ぎゃらりー             → gallery
あーと                 → art
あすきー               → ASCII
あいあいおーてぃー     → IIoT
```

同じ読みの候補は実行時には最良の1件だけを採用する。例えば `ぎゃらりー` の `art gallery` / `corridor`、`あーと` の `assisted reproductive technologies` は監査表には残るが、実行時辞書には収録しない。`iron (element)` のような括弧注釈は監査表に原文を残し、実行時表記を `iron` に正規化する。

入力の読みはひらがなであり、長音記号 `ー` や中点 `・` を含む読みもデータに存在する。漢字を含む読みや、英語以外の JMdict gloss は対象外である。

## 最新リリースの全件集計

リリースの生成済み5列ソースを実際に展開して集計した結果は次の通り。

| 項目 | 件数 |
| --- | ---: |
| 変換エントリ | 118,711 |
| 正規化後のユニークな読み | 71,600 |
| ユニークな英語候補 | 65,267 |
| ユニークな読み・候補ペア | 118,711 |
| 候補が1件だけの読み | 46,819 |
| 候補が複数ある読み | 24,781 |
| 1つの読みの最大候補数 | 39 |
| 読みの長さ | 1〜27文字 |
| コスト | 12,000〜18,880 |

## 品質改善後の採用区分

全118,711エントリーを機械的に再検査し、次の3区分に分ける。JMdict の gloss は辞書訳として正しくても、そのまま変換結果として表示すると説明文になることがあるため、候補を無条件に同じ優先度では扱わない。

| 区分 | 件数 | 実行時の扱い |
| --- | ---: | --- |
| `primary` | 70,784 | 読みごとに選んだ最良の英単語・英語句 |
| `review` | 46,727 | 監査表だけに保持し、実行時辞書から除外 |
| `excluded` | 1,200 | 不自然な読み・記号・数値表記・単独機能語・間投詞・接辞・未完の省略などを通常辞書から除外 |
| 実行時の採用件数 | 70,784 | primary のみ。正規化・読みごとの選択後 |
| 実行時に検索できる読み | 70,784 | ノイズ除去済み辞書のキー |

`review` は入力ソースから削除せず監査表に残すが、ノイズ除去済みの `english_reading` 辞書には読みごとに `primary` を1件だけ収録する。これにより説明文・別義語・括弧注釈が変換結果として大量に出力されることを防ぐ。略語と展開形が競合する場合は略語を優先し、JapaneseCorpus の優先度コストも候補選択に利用する。読みの `ゕ`/`ゖ` は通常の `か`/`け` に正規化し、正規化後の重複も除去する。

追加のハード除外では、`あー`・`いー`・`おー` のように同じ母音を伸ばすだけの読み、`A`・`E`・`O` のような単一文字、数字・序数・数式だけの候補、`!`/`?` を含む感嘆表現、`a`・`the` など単独の機能語、`ah`・`ugh`・`ha ha ha` など非語彙的な間投詞を除外する。`eye`・`iron`・`ice cream`・`United States` のような通常の英単語・英語句はこの規則では除外しない。短い定義断片は `review` として監査表に残す。

リリース manifest の `unique_readings` は 71,605 だが、取得した出力ファイルの読み列をそのままユニーク化すると 71,600件だった。辞書で実際に検索できるキー数は、実ファイルを基準にした後者である。

## 全読みの確認方法

辞書ソースはリポジトリに含めず、次のように固定リリースから準備する（`zstd` が必要）。

```bash
mkdir -p src/main/resources
curl --fail --location \
  https://github.com/KazumaProject/JapaneseCorpus/releases/download/v2026.0810.7/mozc-english-unigram-00000.txt.zst \
  --output /tmp/mozc-english-unigram-00000.txt.zst
echo "b24cfec43651627fc829645e74400c49a4999550899dd17d00a2431ffcb434fa  /tmp/mozc-english-unigram-00000.txt.zst" | shasum -a 256 --check
zstd --decompress --stdout /tmp/mozc-english-unigram-00000.txt.zst > src/main/resources/english-dictionary.txt
```

その後、次を実行する。

```bash
./gradlew validateEnglishDictionary analyzeEnglishDictionary
```

全71,600読みと候補を1行ずつまとめたファイルは次に出力される。

```text
build/reports/english-dictionary/english-dictionary-candidates.tsv
```

列は読み、正規化後の読み、全候補数、区分別の候補数、区分別の候補一覧。候補欄には候補、元コスト、品質区分、フラグ、実行時コストをすべて記載している。

全118,711件を1エントリー1行で確認する場合は次の監査表を見る。

```text
build/reports/english-dictionary/english-dictionary-quality.tsv
```

列は `entry_index`, `reading`, `normalized_reading`, `english_candidate`, `normalized_surface`, `source_cost`, `runtime_cost`, `status`, `score`, `flags`。この表を使えば、どの候補をなぜ採用・監査のみ・除外にしたかを全件確認できる。`runtime_cost` が空欄の候補はノイズ除去済み辞書には収録しない。元の機械可読な5列データが必要な場合は `src/main/resources/english-dictionary.txt` を確認する。

GitHub Actions では、この全件レポートを `english-dictionary-report` artifact として保存する。
`english-dictionary.txt` はビルド用入力であり、Release に単独のテキストファイルとしては含めない。コンパイル済みの英語辞書は通常の `system` 辞書とは分離し、次の3ファイルとして `english_reading` 配下に入る。

```text
app/src/main/assets/english_reading/yomi.dat.zip
app/src/main/assets/english_reading/tango.dat.zip
app/src/main/assets/english_reading/token.dat.zip
```

`system/yomi.dat.zip`・`system/tango.dat.zip`・`system/token.dat.zip` には英語候補を混ぜない。

## データの出典と固定値

- 入力: `https://github.com/KazumaProject/JapaneseCorpus/releases/download/v2026.0810.7/mozc-english-unigram-00000.txt.zst`
- SHA-256: `b24cfec43651627fc829645e74400c49a4999550899dd17d00a2431ffcb434fa`
- 元データ: JMdict_e、ライセンスは CC BY-SA 4.0
- 抽出条件: 英語 gloss、完全な英語 lsource、説明型 gloss (`expl`) は除外
- 実行時の追加フィルター: `primary` のみを採用し、説明文・定義断片・括弧注釈・不自然な母音反復読み・単一文字・数値表記・感嘆表現・非語彙的な間投詞などを除外

JMdict の帰属表示・ライセンス条件は JapaneseCorpus リリースの `JMDICT-LICENSE.html` に従う。
配布 ZIP は辞書データだけを含み、`THIRD-PARTY-NOTICES.md` や `licenses/` は含めない。出典と条件の整理はリポジトリ内の [`THIRD-PARTY-NOTICES.md`](../src/main/resources/THIRD-PARTY-NOTICES.md) を確認する。
