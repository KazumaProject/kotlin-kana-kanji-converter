# ひらがな読み→英語辞書

このプロジェクトでは、[JapaneseCorpus v2026.0803.6](https://github.com/KazumaProject/JapaneseCorpus/releases/tag/v2026.0803.6) の `mozc-english-unigram-00000.txt.zst` を `english-dictionary.txt` として展開し、通常のかな漢字辞書候補へ追加する。

## 変換の意味

これは日本語文を英訳する辞書ではない。JMdict のうち、読みが Unicode カタカナブロックだけで構成された項目を選び、NFKC 正規化後にひらがなへ変換した読みをキーにする。英語の `gloss` と完全な `lsource` が英語候補になるため、例えば次のような変換を作れる。

```text
あいあん       → iron
あいすくりーむ → ice cream
あめりか       → United States / US / USA / the Americas
```

括弧注釈を含む `iron (element)` や `(United States of) America` は品質監査表には残るが、ノイズ除去済みの実行時辞書には収録しない。

入力の読みはひらがなであり、長音記号 `ー` や中点 `・` を含む読みもデータに存在する。漢字を含む読みや、英語以外の JMdict gloss は対象外である。

## 最新リリースの全件集計

リリースの生成済み5列ソースを実際に展開して集計した結果は次の通り。

| 項目 | 件数 |
| --- | ---: |
| 変換エントリ | 118,632 |
| 正規化後のユニークな読み | 71,569 |
| ユニークな英語候補 | 65,228 |
| ユニークな読み・候補ペア | 118,632 |
| 候補が1件だけの読み | 46,807 |
| 候補が複数ある読み | 24,762 |
| 1つの読みの最大候補数 | 39 |
| 読みの長さ | 1〜27文字 |
| コスト | 12,000〜18,880 |

## 品質改善後の採用区分

全118,632エントリーを機械的に再検査し、次の3区分に分ける。JMdict の gloss は辞書訳として正しくても、そのまま変換結果として表示すると説明文になることがあるため、候補を無条件に同じ優先度では扱わない。

| 区分 | 件数 | 実行時の扱い |
| --- | ---: | --- |
| `primary` | 93,981 | 自然な英単語・英語句として通常順位 |
| `review` | 24,293 | 監査表だけに保持し、実行時辞書から除外 |
| `excluded` | 358 | 1文字読み、接辞 (`-ism`)、未完の省略 (`...`)、句読点だけ (`+-`) などを通常辞書から除外 |
| 実行時の採用件数 | 93,981 | primary のみ。正規化・重複除去後 |
| 実行時に検索できる読み | 59,962 | ノイズ除去済み辞書のキー |

`review` は入力ソースから削除せず監査表に残すが、ノイズ除去済みの実行時辞書には `primary` だけを収録する。これにより説明文や括弧注釈が変換結果として出力されることを防ぐ。読みの `ゕ`/`ゖ` は通常の `か`/`け` に正規化し、正規化後の重複も除去する。

リリース manifest の `unique_readings` は 71,574 だが、取得した出力ファイルの読み列をそのままユニーク化すると 71,569件だった。辞書で実際に検索できるキー数は、実ファイルを基準にした後者である。

## 全読みの確認方法

辞書ソースはリポジトリに含めず、次のように固定リリースから準備する（`zstd` が必要）。

```bash
mkdir -p src/main/resources
curl --fail --location \
  https://github.com/KazumaProject/JapaneseCorpus/releases/download/v2026.0803.6/mozc-english-unigram-00000.txt.zst \
  --output /tmp/mozc-english-unigram-00000.txt.zst
echo "b0bdc9ff0e6f7725758f65bb5fa3afc54df6dc22ecac73207c3289ff2111be13  /tmp/mozc-english-unigram-00000.txt.zst" | shasum -a 256 --check
zstd --decompress --stdout /tmp/mozc-english-unigram-00000.txt.zst > src/main/resources/english-dictionary.txt
```

その後、次を実行する。

```bash
./gradlew validateEnglishDictionary analyzeEnglishDictionary
```

全71,569読みと候補を1行ずつまとめたファイルは次に出力される。

```text
build/reports/english-dictionary/english-dictionary-candidates.tsv
```

列は読み、正規化後の読み、全候補数、区分別の候補数、区分別の候補一覧。候補欄には候補、元コスト、品質区分、フラグ、実行時コストをすべて記載している。

全118,632件を1エントリー1行で確認する場合は次の監査表を見る。

```text
build/reports/english-dictionary/english-dictionary-quality.tsv
```

列は `entry_index`, `reading`, `normalized_reading`, `english_candidate`, `source_cost`, `runtime_cost`, `status`, `score`, `flags`。この表を使えば、どの候補をなぜ採用・監査のみ・除外にしたかを全件確認できる。`runtime_cost` が空欄の候補はノイズ除去済み辞書には収録しない。元の機械可読な5列データが必要な場合は `src/main/resources/english-dictionary.txt` を確認する。

GitHub Actions では、この全件レポートを `english-dictionary-report` artifact として保存する。

## データの出典と固定値

- 入力: `https://github.com/KazumaProject/JapaneseCorpus/releases/download/v2026.0803.6/mozc-english-unigram-00000.txt.zst`
- SHA-256: `b0bdc9ff0e6f7725758f65bb5fa3afc54df6dc22ecac73207c3289ff2111be13`
- 元データ: JMdict_e、ライセンスは CC BY-SA 4.0
- 抽出条件: 英語 gloss、完全な英語 lsource、説明型 gloss (`expl`) は除外
- 実行時の追加フィルター: `primary` のみを採用し、説明文・括弧注釈・接辞・未完表現・句読点だけの候補などを除外

JMdict の帰属表示・ライセンス条件は JapaneseCorpus リリースの `JMDICT-LICENSE.html` に従う。
配布 ZIP には、JMdict と Mozc 辞書資源の個別条件をまとめた [`THIRD-PARTY-NOTICES.md`](../src/main/resources/THIRD-PARTY-NOTICES.md) と、JapaneseCorpus の `JMDICT-LICENSE.html` / `LICENSE-DATA.md` / `NOTICE.md`、Mozc の `MOZC-LICENSE` / `IPADIC-COPYING` / `IPADIC-NOTICE` を同梱する。
