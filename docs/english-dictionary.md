# ひらがな読み→英語辞書

`english_reading` は英語の発音または外来語の読みから英単語を候補にする専用辞書です。
JapaneseCorpus の direct-loanword 配布と、このリポジトリの確認済み補完辞書を
合流させ、通常のかな漢字辞書とは別の LOUDS / TokenArray 3点を生成します。
`りんご → apple` のような意味による英訳は対象にしません。

実際に採用された全表記と読みは [収録一覧](english-dictionary-catalog.md) に掲載しています。
`./gradlew generateEnglishDictionaryCatalog` で同じ統合処理から再生成できます。
一覧は入力のSHA-256を記録したスナップショットで、通常ビルドや配布処理では書き換えません。

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

外来語として定着していない一般英単語も対象にできます。NGSLの頻度順で欠落を探し、
日本語の慣用読みがない場合はCMUdictの米語発音から自然なかな候補を作ります。
候補の全音節を一件ずつ確認し、別レビューで綴り・発音・かなを照合したものだけを採用します。
この読みは日本語資料で確認した読みとは区別します。自動生成候補の直接採用や、
綴りからの読み生成・活用形の一括展開はしません。新規追加は単独の英単語に限定します。

CMUdict由来の行では、sourceに40桁のcommitを含むGitHub permalinkと行番号を記録します。
noteは `英語発音から作成・確認した読み; ARPAbet=<元の発音>; <判断理由>` とします。
未固定のbranch URL、レビュー記録なし、未記録・不正な発音記号は読込時に失敗します。
形式検査は発音の正しさやレビューの実施を自動証明しません。日本語資料の行には
`日本語資料で確認した読み` と採用理由を残します。

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
原本、補完TSV、監査レポートは含めません。既存の候補・品質監査 `english-dictionary` は
Actions artifact に保存します。一般見出し語の `english-word-coverage` 監査は後述の
ローカル再実行で生成します。

初期補完の参照資料は JapaneseCorpus `v2026.1012.19` にある `JMdict_e-20261012.xml.gz`
（SHA-256 `5004ad9c777db2188baaa51554d4bb3e1ef3781725c4b38467723886b5d47d9e`）です。
初期版では867組を追加し、さらに日常・開発・仕事・会議用の実用語と複合語を352組
追加しました。用途別の選定例71例（70固有ペア）では19組の欠落が見つかったため、出典を確認して
別読み2組も補完しました。さらにレビューで標準読み1組の欠落を補い、
この段階の補完は合計1,241組です。一般英単語の追加結果は後述します。
全行の出典・採用理由は補完TSVに記録しています。

この71例は頻度に基づく網羅率評価ではありません。収録件数や用例テストの成功だけで、
広い語彙の網羅性や実IMEでの選びやすさを保証するものではありません。

検証基準の上流辞書は829組、圧縮ファイルのSHA-256は
`b34b9c630ecf4d3f404049ef6580d8f4d5d5b13e1197e083d51b8ea3f064cd6e`です。
通常のCIではタグを固定せず、実際に解決したリリースとchecksumをログで確認します。

補完辞書の編集・追加部分とJMdict由来データは CC BY-SA 4.0 です。
CMUdict由来部分の著作権表示・条件・免責も維持します。適用範囲と出典は
[LICENSE-DATA.md](../LICENSE-DATA.md)、
[第三者表記](../src/main/resources/THIRD-PARTY-NOTICES.md)、
[JMdictの公式表記](../src/main/resources/third-party/JMDICT-LICENSE.html)、
[CMUdictのLICENSE全文](../src/main/resources/third-party/CMUDICT-LICENSE) を参照してください。
利用側のアプリでも必要な表示を維持してください。

## 一般英単語の調査資料

一般語の選定はNGSL 1.2の頻度付き2,809見出し語と、開発・仕事の追加対象
`deploy / dependency / authentication / authorization / coroutine / vendor / stakeholder`
の計2,816語です。NGSLの補足52語はこの調査集合に追加しません。頻度は採用順に使い、
costやIMEの最終順位を推測する数値には使いません。

- NGSL: https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv
  （NGSL 1.2、SHA-256 `2098bab8955a120a9766c6282a51d7d578c6cb0a7d946600d2ffb73ba25a0b44`）。
- CMUdict: commit `74790861f652b15e4ac49015a90074ad62a27690`、
  https://raw.githubusercontent.com/cmusphinx/cmudict/74790861f652b15e4ac49015a90074ad62a27690/cmudict.dict
  （SHA-256 `81917843c7f44ce2b094ac63873c2c7a4cf802040792c455ba3ca406891c3d22`）。
  同commitの `LICENSE` は `src/main/resources/third-party/CMUDICT-LICENSE` に保存しています
  （SHA-256 `bd4ce8e44170a5f9f481310ca85c51de3c4f851a65e679b40e603b143bd3542a`）。
- 追加前の基準: このPRの `980eea5be020aa3c783f20cd593032e51bc697f6` と
  JapaneseCorpus `v2026.1012.19` で生成した2,070行の `merged-runtime.tsv`
  （SHA-256 `fde0a5da8ddb9a73d7455eb8dfed7fcd18457fe84a9e5fe800301e4e5ae547e8`）。

原本・抽出候補・選択記録・未採用理由・追加前の基準は `build/english-source/general-words/`
へ保存します。採用行だけを補完TSVへ反映し、原本や一時スクリプトはGitへ追加しません。
比較時は資料のchecksumと基準リビジョンを確認してください。NGSLの `TRUE / FALSE` は
一般語 `true / false` として扱い、元の表記も監査に残します。`I` は一文字除外です。
`IT / it` のような略語と一般語の一致は認めません。

単語数は表記の種類数や読みペア数とは異なります。NGSLに対する見出し語の収録数を集計し、
対象外の表記を未検証の語形・見出し語へ機械的にまとめません。複合語、活用形、別読みの追加を
基本語の追加として数えません。収録率はこの固定した調査集合に対する値であり、一般英文の
理解率や実IMEの表示成功率ではありません。

### 調査の再実行

上記SHA-256と一致するNGSL原本を `build/english-source/general-words/ngsl.csv` に用意します。
追加前の基準は、同じJapaneseCorpus `v2026.1012.19` の上流入力と同じ `id.def`
（今回の一般名詞POS IDは1851）で再生成できます。現在の上流取得が別のリリースなら、
先に基準配布のchecksumを照合して `english-dictionary.txt` を準備してください。
基準commitがローカルにない場合は、先に
`git fetch origin 980eea5be020aa3c783f20cd593032e51bc697f6` で取得します。

```bash
mkdir -p build/english-source/general-words
git show 980eea5be020aa3c783f20cd593032e51bc697f6:src/main/english/reading-supplement.tsv \
  > build/english-source/general-words/baseline-supplement.tsv
./gradlew installDist
java -cp 'build/install/kana-kanji-converter/lib/*' \
  com.kazumaproject.english.GenerateEnglishDictionaryReportKt \
  --input src/main/resources/english-dictionary.txt \
  --supplement build/english-source/general-words/baseline-supplement.tsv \
  --id-def src/main/resources/id.def \
  --output build/english-source/general-words/baseline-report/candidates.tsv \
  --summary build/english-source/general-words/baseline-report/summary.md
cp build/english-source/general-words/baseline-report/merged-runtime.tsv \
  build/english-source/general-words/baseline-runtime.tsv
shasum -a 256 build/english-source/general-words/baseline-runtime.tsv
./gradlew analyzeEnglishWordCoverage
```

基準のSHA-256は前記の値と照合します。NGSLはタスク自身が固定checksumと2,809件を検査します。
別の保存先を使う場合は `-PenglishWordListFile=...`、
`-PenglishWordCoverageBaselineFile=...`、`-PenglishWordReviewDecisionsFile=...` で指定できます。
レビューによる未採用理由は任意の3列TSV `word / status / reason`（statusは `deferred` または
`rejected`）で指定します。今回の `review-decisions.tsv` は次の内容です。区切りはタブです。

```text
word	status	reason
owe	deferred	CMU発音OW1に対応する標準読み「おー」は既存のvocalization-reading除外に該当
stem	deferred	既存すてむ→STEM(cost18501)と読み・大小文字をまとめた表記が衝突し、新規stem(cost12500)が正式略語を置き換えるため既存の統合方針では保留
```

このファイルを `build/english-source/general-words/review-decisions.tsv` に置くと自動で読み込みます。
省略した場合も全対象を監査しますが、保留の理由は未解決の読み確認という一般的な記述になります。
監査結果は `build/reports/english-word-coverage/` の `targets.tsv`、`added-pairs.tsv`、
`changed-existing-pairs.tsv`、`summary.md` です。監査は共有の統合結果を使い、読みの採用や
資料のダウンロードを自動では行いません。

### 一般英単語の追加結果

上記の固定入力で全2,816対象を調査した結果です。

| 状態 | 見出し語数 |
| --- | ---: |
| 追加前から収録 | 568 |
| 今回追加 | 2,197 |
| 既存の品質方針による除外 | 49 |
| 根拠・既存統合との衝突による保留 | 2 |

収録済み対象は2,765見出し語です。今回の採用データは2,323行で、JMdict由来1,276行、
CMUdict由来1,044行、公式の日本語資料由来3行です。別レビューで出典の読み制限・語義・発音全体を
照合し、不一致を修正した採用行を登録しています。補完TSVは既存分を含め3,564行となりました。

統合後は2,070組から4,391組へ純増2,321組、読みは4,256種類です。既存単語 `true` の
読み追加が1組、新しい単語に対する追加の別読みが125組あります。新規複合語・対象外単独表記の
追加は0組で、活用形の一括追加もありません。大小文字をまとめた全辞書の単独表記は3,959種類、
空白を含む複合表記は158種類ですが、単独表記数には既存略語・語形などを含むため、
3,959基本見出し語とは報告しません。

既存の読み・大小文字を区別しない表記のペアは0組削除、2組変更です。最小costを採る既存規則により
`さー→Sir / めい→May`（18500）は `さー→sir / めい→may`（12500）になります。POSは同じです。
`stem` は正式略語 `STEM` を置き換えるため保留し、`owe` は既存の発声読み除外に該当するため
保留しました。除外49語には数詞・機能語・一文字候補のほか、既存の説明文判定に該当する
`whether` も含みます。全件の状態・理由は監査に残します。

標準読みの確認に使った公式資料3点は次のとおりです（取得原本のSHA-256）。

- `おーせんてぃけーしょん→authentication`:
  [金融庁公開の本人確認に関する参考資料、PDF 16頁](https://www.fsa.go.jp/policy/bgin/ResearchPaper_Reference_NRI_ja.pdf#page=16)
  — `853a532d765f7f11c29d19cf5fc72f1117c3e7834003ae3861da06f9b092bf72`。
- `でぃぺんでんしー→dependency`:
  [SideFX公式ドキュメント](https://www.sidefx.com/ja/docs/houdini/network/dependencies.html)
  — `5f5065c5535075a80e6e7d60da2ea126b3e7431625d17f84dc765a941f240434`。
- `えすてぃめーと→estimate`:
  [弥生公式の英語見積書解説](https://www.yayoi-kk.co.jp/seikyusho/oyakudachi/quotation-english-translation/)
  — `d34bffd14ecafaaf03586ce27c89954faf041f474bf02cdb891be0acc9253dcf`。

通常テストは137件中136件成功・辞書ビルド専用1件スキップ、別実行の `dictionaryBuildTest` は
2件成功でした。`check` と配布ZIP再読込も成功し、全4,391採用行と共有POSを照合しました。
最大読みIDは4,256で、32767以下です。実端末の表示・最終順位は未確認です。

- [JapaneseCorpus 基準配布](https://github.com/KazumaProject/JapaneseCorpus/releases/tag/v2026.1012.19)
- [JMdict 利用条件](https://www.edrdg.org/edrdg/licence.html)
- [JMdict DTD / 語義・読み制限の定義](https://www.edrdg.org/jmdict/jmdict_dtd_h.html)
