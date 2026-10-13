# ひらがな読み→英語辞書

`english_reading` は発音・外来語の読みから英語を候補にする専用辞書です。
JapaneseCorpus の direct-loanword 配布と、このリポジトリの確認済み補完辞書を
合流させ、通常のかな漢字辞書とは別の LOUDS / TokenArray 3点を生成します。
`りんご → apple` のような意味による英訳は対象にしません。

## 補完辞書の作成・追加

編集する入力は `src/main/english/reading-supplement.tsv` です。UTF-8 / LF、
ヘッダー付きの5列TSVを使います。

```text
reading<TAB>surface<TAB>cost<TAB>source<TAB>note
```

1. 日常語・IT用語の必要な英語表記を選び、JMdict のカタカナ読み、英語 gloss、
   借用元を確認します。略語は公式の仕様・資料でも表記を確認します。
2. **読み全体と表記全体**が対応する組だけを採用します。JMdict の gloss は訳語であり、
   借用元にも部分形・和製語があるため、その存在だけで自動採用しません。
   CMUdict の発音は確認材料ですが、日本語で定着した読みを棄却する絶対条件にはしません。
3. 読みはひらがなと `ー`、表記は注釈を含まない英語単語・略語・複合語で登録します。
   説明付き gloss から単語を採る場合は個別に対応を確認し、その判断を note に残します。
   括弧を機械的に除くルールはありません。
4. source に `jmdict:<ent_seq>` または確認した資料の HTTPS URL を記録します。
   標準読みの cost は12500、出典で確認できた追加の読み揺れは12800です。
   これは頻度の実測値ではなく初期設定です。長音の一括削除などで読みを増やしません。
5. 数詞・機能語・一文字候補・説明文などの既存除外規則を通過したことを確認します。
   複合語の許可は読みと表記の完全一致ペアに限定されます。

```text
ぎゃらりー                → gallery
ぎゃらりー                ↛ art gallery
あーとぎゃらりー          → art gallery
さーばー / さーば         → server（それぞれ出典の読みを確認）
```

統合は読みと大小文字を区別しない表記で重複排除し、最小 cost を選びます。
同額なら上流の表記を優先します。異なる同音語は残し、読みごとの token 順は
cost・表記順で固定します。TSV の列数、かな、表記、cost、出典、重複の誤りは
ファイル名・行番号付きで失敗します。出典欄は形式検査であり、意味・発音の妥当性を
自動証明するものではありません。

## 上流の取得と生成

Actions は JapaneseCorpus の最新公開リリースを**一度だけ解決**し、同じタグから
辞書、manifest、SHA256SUMS を取得します。辞書の SHA-256、manifest の checksum、
`dictionary_kind == direct-loanword` を検証して `src/main/resources/english-dictionary.txt`
へ展開します。補完TSVは自動的に全生成・検証・監査に合流します。

ローカルでも同じリリースの3ファイルを取得し、checksum と manifest を照合してから
辞書を展開してください。ダウンロード、原本、抽出候補は `build/` に保存し、追跡しません。
その後、必要な Mozc 入力を準備して実行します。

```bash
./gradlew validateEnglishDictionary analyzeEnglishDictionary
./gradlew test check
./gradlew run
./gradlew verifyJapaneseKeyboardDictionaryAssets
```

最後のタスクは既存の全辞書生成・パッケージ検証に加え、配布ZIP内の英語辞書を
再読込します。`verifyEnglishDictionaryBinary` だけでも同じバイナリ照合を実行できます。

## 監査・バイナリ検証

`build/reports/english-dictionary/` に次を生成します。

- `english-dictionary-candidates.tsv`: 全入力の候補と品質判定
- `english-dictionary-quality.tsv`: 全入力行の個別判定
- `merged-runtime.tsv`: 統合・重複排除後の全採用行
- `supplement-sources.tsv`: 補完行の出典と採用理由
- `summary.md`: 基準辞書との差分、追加ペア、既存ペアの変更、新しい英語表記、既存表記への読み追加、読み揺れの件数

ZIPの再読込では、全登録読み、表記、cost、token 順、共有 `pos_table.dat` のPOS ID、
余分・欠落した読みや token を照合します。利用側の追加候補が読みIDを符号付き Short に
変換するため、最大 term ID が32767以下であることも検査します。未登録の途中読みが
完全一致候補にならないことを確認します。

調査した利用側は JapaneseKeyboard の
`ab3342ae8c7512f571996a13f9409843de8e81f2` です。入力全体の完全一致で追加候補を作り、
分節探索では登録語の common-prefix を使います。入力より長い語の予測補完ではありません。
このリポジトリでの辞書照合・CLIの成功は、実端末の候補表示・最終順位の成功を意味しません。

## 配布・出典

既存の配布パスを維持します。

```text
app/src/main/assets/english_reading/yomi.dat.zip
app/src/main/assets/english_reading/tango.dat.zip
app/src/main/assets/english_reading/token.dat.zip
```

共有POS表とセットで使用してください。Release ZIPは従来どおりコンパイル済み辞書データのみです。
原本、補完TSV、監査レポートは含めません。監査は Actions artifact に保存します。

初期補完の参照資料は JapaneseCorpus `v2026.1012.19` にある `JMdict_e-20261012.xml.gz`
（SHA-256 `5004ad9c777db2188baaa51554d4bb3e1ef3781725c4b38467723886b5d47d9e`）です。
初期版では867組を追加し、さらに日常・開発・仕事・会議用の実用語と複合語を352組
追加しました。用途別の選定例71例（70固有ペア）では19組の欠落が見つかったため、出典を確認して
別読み2組も補完しました。さらにレビューで標準読み1組の欠落を補い、
補完は合計1,241組です。全行の出典・採用理由は補完TSVに記録しています。

この71例は頻度に基づく網羅率評価ではありません。収録件数や用例テストの成功だけで、
広い語彙の網羅性や実IMEでの選びやすさを保証するものではありません。

検証基準の上流辞書は829組、圧縮ファイルのSHA-256は
`b34b9c630ecf4d3f404049ef6580d8f4d5d5b13e1197e083d51b8ea3f064cd6e`です。
通常のCIではタグを固定せず、実際に解決したリリースとchecksumをログで確認します。

JMdict由来の補完辞書と生成データは CC BY-SA 4.0 です。出典・ライセンス表示は
`src/main/resources/THIRD-PARTY-NOTICES.md` と `third-party/JMDICT-LICENSE.html` を参照してください。
利用側のアプリでも必要な表示を維持してください。

- [JapaneseCorpus 基準配布](https://github.com/KazumaProject/JapaneseCorpus/releases/tag/v2026.1012.19)
- [JMdict 利用条件](https://www.edrdg.org/edrdg/licence.html)
- [JMdict DTD / 語義・読み制限の定義](https://www.edrdg.org/jmdict/jmdict_dtd_h.html)
