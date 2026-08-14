# ひらがな読み→英語辞書

英語辞書は通常のかな漢字辞書とは分離し、`english_reading` 用の3つの
コンパイル済みデータとして生成する。入力は JapaneseCorpus の
`mozc-english-reading-unigram-*.txt.zst` であり、一般的な JMdict の英語 gloss
をそのまま採用するものではない。

## 採用条件

JapaneseCorpus の生成側で、JMdict の英語候補を次の順に絞る。

1. 読み全体をひらがなへ正規化する。
2. 表記が英語の単語として妥当で、括弧注釈・説明文・未完表現を含まないことを確認する。
3. CMUdict の発音を英語表記の発音として使い、読み全体と完全に一致する候補だけを採用する。
4. CMUdict にない略語と複合語は、`reading<TAB>surface<TAB>reason` の完全一致 allowlist にある場合だけ採用する。

したがって、次のようになる。

```text
ぎゃらりー             → gallery
ぎゃらりー             ↛ art gallery
ぎゃらりー             ↛ corridor
あーと                 → art
あーと                 ↛ assisted reproductive technologies
あーとぎゃらりー       → art gallery
かー                   → car
```

`art gallery` は英語として自然でも、`ぎゃらりー` の読み全体には対応しない。
一方、`あーとぎゃらりー` のように日本語側の読み全体が一致する場合だけ例外表に
登録できる。読みごとに1件へ潰す処理は行わず、完全一致した自然な候補は残す。

括弧付きの `iron (element)` や長い `assisted reproductive technologies` は、
表記を `iron` などへ切り詰めない。元の候補を監査表に残したまま、実行時辞書から
除外する。

## 生成と監査

Actions はワークフローに固定した JapaneseCorpus リリースから、次のアセットだけを
ビルド入力として取得する。

```text
mozc-english-reading-unigram-00000.txt.zst
```

ローカルで確認する場合は、ワークフローの `JAPANESE_CORPUS_TAG` と SHA-256 を使う。

```bash
mkdir -p src/main/resources
curl --fail --location \
  "https://github.com/KazumaProject/JapaneseCorpus/releases/download/${JAPANESE_CORPUS_TAG}/mozc-english-reading-unigram-00000.txt.zst" \
  --output /tmp/mozc-english-reading-unigram-00000.txt.zst
echo "${JAPANESE_CORPUS_ENGLISH_SHA256}  /tmp/mozc-english-reading-unigram-00000.txt.zst" | shasum -a 256 --check
zstd --decompress --stdout /tmp/mozc-english-reading-unigram-00000.txt.zst > src/main/resources/english-dictionary.txt
./gradlew validateEnglishDictionary analyzeEnglishDictionary
```

監査結果は次に出る。

```text
build/reports/english-dictionary/english-dictionary-candidates.tsv
build/reports/english-dictionary/english-dictionary-quality.tsv
build/reports/english-dictionary/summary.md
```

Release には監査レポートや入力テキストを含めない。これらは Actions の
`english-dictionary-report` artifact としてのみ保存する。

## Release の分離

通常の辞書には英語候補を混ぜず、英語辞書は次のパスへ出力する。

```text
app/src/main/assets/english_reading/yomi.dat.zip
app/src/main/assets/english_reading/tango.dat.zip
app/src/main/assets/english_reading/token.dat.zip
```

Release ZIP はコンパイル済み辞書データだけを含む。`licenses/`、
`THIRD-PARTY-NOTICES`、`NOTICE`、CMUdict、JMdict 原本、allowlist、監査レポートは
含めない。

## 出典

- 読み・候補の生成: JapaneseCorpus の direct-loanword ビルダー
- 発音判定: ワークフローで commit と SHA-256 を固定した CMUdict
- 元の語彙データ: JMdict_e（JapaneseCorpus 側のライセンス表示に従う）
- 実行時の辞書名: `english_reading`
