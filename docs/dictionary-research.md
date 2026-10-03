# 全入力の再審査とローカルAIワーカー

## 現在の到達点

**全件再審査は進行中であり、完了した新辞書はまだ公開していません。**
2026-10-03に5入力の1,103,684行をSQLite台帳へ取り込みました。旧正規化済み
1,064,924エントリだけでなく、分離前の元表記、旧保留・除外行、原入力に含まれる
根拠付き分離候補も追跡し、現在の審査対象は1,074,028候補です。
旧採用372,438件も再審査します。参照辞書の見出しを追加する処理はありません。

旧版の収録数、600語・200文の結果、Linuxバイナリ一致は
[旧版の配布資料](dictionary-distribution.md)に残しています。
これらを新しいschema 4の品質検証結果として流用しません。
旧版の実測評価を `research/evaluation-baseline-v2.json` とハッシュ付きの
`research/evaluation-core.lock.json` に固定し、旧成功語も後退検査の対象にしました。

一括照合ではJMdictの元XML制約23,987語義を再検査し、JMnedictの104,340組を
照合しました。後者には、原入力に含まれる分離先の照合も含みます。
**これらは一致・検査数であり、新規採用数ではありません。**
公開データの型タグ、同名項目の存在、モデル間の一致だけで読みを承認しません。

独立した正解データ、2,000件の試験結果、全件審査、各カテゴリの標本点検、
追加の自然な200文、schema 4のLinuxバイナリ一致が揃うまで、完成とはしません。
現在のコミット済みメタデータlockは旧schema 3です。
`v*`タグの通常Releaseは、承認済みschema 4が用意できるまで失敗して停止します。

2,000件の試験を2026-10-03に開始しました。旧採否・カテゴリ・正規化・元出典の
289層から選び、時間やバッチ数による打切りを設定せず実行しています。
独立した正解による精度はまだ測定していません。開始時点の入力ハッシュ・追跡件数・
モデル／プロンプト設定は [準備記録](dictionary-research-preparation.json) に保存しました。
元入力の追跡漏れと、出典を持たない候補はいずれも0です。
Python 33テスト・Kotlin 140テスト（失敗0、スキップ1）を実行しました。
[今回のLinux PRテスト](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/runs/37161862279)も成功しました。これは実装の検証であり、
実際の全辞書の精度や、新版バイナリのLinux一致を確認した結果ではありません。

最初の試験で、記事内の別対象から公式リンクを拾う問題と、gzip HTML・日本語の
Web文字コードの解析問題を検出して修正しました。名称の直接対応を優先し、
公式リンクは対象の明示された名称と結び付くものに限定しました。
旧パーサーの調査根拠は履歴へ移し、新しい版で2,000件の試験を再開しました。
取得・解析に失敗した候補を非配布へ確定したことはありません。

## 判定と作業状態

| 最終判定 | 台帳の値 | 意味 |
|---|---|---|
| 採用 | `adopted` | 独立した読み・意味・品質を確認し、公開判定も通過 |
| 根拠付き除外 | `excluded_confirmed` | 元資料・構造の根拠で不適切さを確認 |
| 非配布 | `not_distributed` | 必要な調査が終了しても不足・不一致が残る、または配布条件未達 |

`queued`（未処理）、`ready_review`（別モデルの審査待ち）、`error`（再試行待ち）、
`reviewed`（読み・意味を確認したが独立検証・配布承認前）は作業状態です。
`reviewed`を採用済み件数として報告しません。
通信障害、モデル停止、JSON不正、未対応の資料形式、容量不足を非配布へ変換しません。
容量不足はワーカーを停止し、取得の429/503はRetry-Afterと候補別の再試行間隔を保持します。

非配布は誤語という意味ではありません。読み不足、対象・語義不足、独立審査の不一致、
修正根拠不足、カテゴリ公開条件不足などを別々に残します。
全候補の最終判定が揃っても、全語を個別に人が確認したとは報告しません。

## 読みと分類を分ける仕組み

読み根拠は正規化した**読み・表記の組**へ結び付けます。
意味根拠は対象ID・語義に結び付け、読みとは別に保存します。
分類includeから読み確認を迂回する旧経路、元5入力の読みを括弧分離の根拠にする経路を
廃止しました。個別の表記・読み変更にも独立した境界根拠が必要です。

| 参照 | 再照合する内容 |
|---|---|
| Mozc | 固定commitの辞書行と同一読み・表記 |
| JMdict | `re_restr`・`re_nokanji`・`stagk`・`stagr`、継承POS/misc、分野と語義 |
| JMnedict | 実際のDTD、`re_restr`、翻訳単位の名前種別 |
| 日本郵便 | 都道府県・市区町村・町域を区別した対応、正式住所の構造 |
| Wikipedia | 固定revisionの記事名、冒頭の明示された読み、明示された別名対応 |
| Wikidata | 直接名と別名の違い、P1814/P5168の名称別対応、対象別の型 |
| 公式資料 | 実際に取得した名称・読みの併記。名称掲載だけでは読みを承認しない |

全かな表記は、公表された独立名称であることと読みの一致が必要です。
本名の読みを別名へ流用しません。同名別項目の不一致はその対象だけに作用させ、
別の制約付き語義や確かな読み根拠を破棄しません。

JMnedictの姓・名の明示や、構造確認した郵便住所を、モデルの不確かな意見だけで
拒みません。一方、広いplace-nameタグだけでは城・建物まで地名へ自動分類しません。
JMdictの名詞POSや広い分野タグだけによる一般語・専門語への分類も、直接の分類事実と
扱わず審査の対象にします。保留語の受け皿として一般語を使いません。

括弧を機械的に削除せず、必要な地名を独立した読みと境界から分離します。
第十・一円・作品の括弧・市原市原田を反復削除の対象にしません。
正式な施設名、削る地名、読み境界を照合して重複施設名を修正します。
分離後の語だけでなく、分離前の入力も台帳へ残します。

## モデルと追加調査

`src/main/dictionary-quality/research/models.lock.json` がモデルと設定の正本です。
ローカルOllamaの `qwen3.5:9b` が提案し、`qwen3:8b` が旧分類・提案結果を見ずに審査します。
digest不一致はエラーです。接続先はloopbackのHTTPのみで、クラウド推論へ切り替えません。
1ワーカー、温度0、seed 17、コンテキスト8,192、既定16件です。
大きすぎるバッチは分割し、資料を黙って切り捨てません。
単独候補に多数の語義・対象がある場合も、出典の意味単位ごとに審査します。
個々の要求・応答を保存し、ホストによる統合結果をモデルの生の応答と区別します。
モデルを同時に読み込まないよう、提案と審査を128件の窓で順次処理します。

JSON Schemaで出力を制約し、ホスト側でも候補ID・カテゴリ・対象・取得済み根拠IDを
検証します。短い一時IDを使用しますが、対応表とリクエスト・レスポンス全文を保存します。
資料内の命令は実行せず、判定対象のデータとして扱います。
モデルによる読みの予測や、架空のURL・根拠・対象は採用根拠になりません。

不足語には最大2巡の追加調査を行います。各巡でWikipediaを最大3記事、
記事・Wikidataから実際に得た公式リンクを最大3ページ調べます。
検索結果なしと取得失敗を区別し、URL・revision・本文SHA-256・調査回数を残します。
後から読みが見つかった修正候補にも同じ読み境界検査を適用します。

資料キャッシュの上限は64GiBです。巨大な旧ローカル参照DBに依存せず、
コミット済みlockの旧固定DBと公開JMdict・JMnedict・日本郵便を入力に使用します。
Pythonワーカーには標準ライブラリ以外の依存はありません。

## カテゴリ

既存12カテゴリを維持し、次の5カテゴリを定義へ追加しました。
**定義への追加と、配布への追加は別です。現在、新カテゴリの配布件数は未確定です。**
境界・最低目安は版管理した `research/categories.json` が正本です。

| ID | 対象・境界 | 配布最低目安 |
|---|---|---:|
| organism | 生物の分類群・種・品種・化石・実在動物の個体。解剖用語はtechnical | 500 |
| sports | 競技・技・地位・ルール。大会はevent、チームはorganization | 100 |
| religion | 教義・儀礼・用具・制度。人物はperson、神はcharacter、経典はwork | 100 |
| astronomy | 天体・宇宙構造・天文現象。一般的科学理論はtechnical | 100 |
| transport | 乗り物の種類・船・車両・航空機。商品モデルはproduct、駅はstation | 100 |

一般語10,000、専門語1,500、食品250、商品200の最低目安も維持します。
少数カテゴリは分類を台帳へ残したうえで非配布にし、一般語へ移しません。
独立した語義・役割がある場合だけ複数カテゴリを保持し、候補は実行時に重複させません。

## CLIと再開

```sh
./gradlew installDist
CLI=./build/install/kana-kanji-converter/bin/dictionary-cli
$CLI research prepare --audit build/research/baseline-v2/audit.tsv.gz
$CLI research bulk --base-dir src/main/resources \
  --jmdict build/planning-jmdict/JMdict_e.gz \
  --jmnedict build/research/JMnedict.xml.gz \
  --postal-zip build/dictionary-metadata/postal.zip
$CLI research pilot
$CLI research status
$CLI research explain --surface 高畑
```

既定台帳は `build/research/ledger.sqlite`、資料は `build/research/documents/` です。
同じ入力ならprepareを繰り返しても台帳を初期化しません。変更された根拠に関係する候補を
再審査へ戻し、古い資料・旧パーサーの根拠は履歴として残して新しい採用に使いません。
候補ごとにチェックポイントを保存し、同じコマンドで再開できます。
同じ台帳を2ワーカーで操作することはロックで拒否します。
`--max-batches`は診断用であり、通常のpilot/runには時間・バッチ数の打切りを付けません。

試験の進捗と追加調査による読み発見は、読みの一括照合時点の基準と比較できます。
今回の2,000件では一括照合で831件の読みを確認しています。これは分類・採用の確定数ではありません。

```sh
# pilotが対象を固定した後、一括照合の基準を一度保存する
python3 scripts/report-local-dictionary-pilot.py --capture-bulk-baseline
# 以後は保存済みの同じ基準と比較する
python3 scripts/report-local-dictionary-pilot.py \
  --baseline build/research/pilot-bulk-baseline.json.gz \
  --output build/research/pilot-progress.json
```

この集計は台帳を変更せず、対象集合のハッシュを検査します。独立正解が未確認なら精度は
未測定として出力し、未完了の試験から全件の所要時間を計算しません。

```sh
$CLI research freeze-gold --gold build/research/independent-gold.json
$CLI research run
$CLI research export --candidate --output build/research/candidate/snapshot.sqlite
$CLI build --candidate --snapshot build/research/candidate/snapshot.sqlite \
  --lock build/research/candidate/snapshot.lock.json
# 辞書引き・400文評価・標本レビュー・Linux一致・ZIP検証を実施
$CLI research accept --acceptance build/research/acceptance.json
$CLI research finalize
$CLI research export --output build/research/release/snapshot.sqlite
```

本番用exportはfinalize前に拒否します。`--candidate`でも未処理・失敗や独立検証の不足を
迂回しません。候補版は通常のmetadata fetchや標準buildから使えません。
候補buildのlock指定には、候補出力の `snapshot.lock.json` を使用してください。
調査用取得は通常buildと分離し、通常buildがネットワークやOllamaを呼ぶ経路はありません。

## 独立検証と完了条件

全件処理前に、既存カテゴリは校正100件・独立検証100件、新カテゴリは50件ずつを
固定します。同じ表記や同じ対象を両方に入れません。正解には資料の引用・ハッシュと
読み・意味の対応が必要で、対象AIの出力を正解として登録しません。
AI採用経路は精度99.5%以上、正確な二項分布による片側95%信頼下限99%以上、
確認済み評価語の採用率95%以上が必要です。100件全正解だけでは信頼下限を満たせません。
2,000件の試験は旧採否・旧カテゴリ・正規化・元出典で層化し、速度・読み発見率・
精度を測ります。2件の診断結果から百万件の所要時間を推定しません。

各カテゴリの新規・旧採用を100件ずつ、少数群は全件確認します。
非配布は理由・出典別に500件を確認します。
現行600語・200文と、追加カテゴリ50語ずつ・自然な200文を評価し、旧成功ケースの
後退、最良候補と上位10候補を記録します。誤った正解を訂正する場合は根拠と変更を保存し、
両版を同じ正解で比較します。

全元入力の対応漏れ、未処理、処理失敗がゼロで、独立検証・標本確認・実用性・
Linuxバイナリ一致・ZIP検証が通ったときだけ完了です。
AIで確認した意味単位、規則で照合した数、個別資料を確認した数を分けて報告します。

## 固定データとActions

schema 4は `resolutions`（最終判定）、`source_map`（元入力行の追跡）、
`reading_facts`（読み根拠）、`semantic_facts`（対象・語義の根拠）、
`quality_facts`（修正・除外根拠）を分離します。
モデル入出力・取得本文・非配布の詳細は台帳と圧縮レビュー出力へ残します。
通常ビルド用DBは512MiB以内に絞り、展開・圧縮SHA-256をlockへ記録します。
通常ビルドはDB内の最終判定・読みペア・対象・修正根拠・原入力対応と全判定のハッシュを
検証し、分類の代替推測を行いません。

ActionsはAIを実行しません。固定データから辞書を作り、原入力全件比較、評価、
承認されたバイナリとの一致、ZIP検証を行います。
PRでは小規模のPython/Kotlin fixtureを実行します。
独立検証用の追加データが存在しないschema 4も公開できません。

辞書ZIPは `build/category-release/categorized-dictionaries.zip` です。
`manifest.json`・`NOTICES.md`・2ライセンス・共有 `pos_table.dat` と、
公開条件を満たしたカテゴリごとの `yomi.dat`・`tango.dat`・`token.dat` を同梱します。
カテゴリ数をCとすると合計 `5 + 3C` ファイルです。12カテゴリなら41、17なら56です。
少数新カテゴリの空ディレクトリ、非配布・保留・未分類用の辞書は含めません。
従来の `japanese_keyboard_dictionary_assets.zip` と出力先を分けて維持します。
固定メタデータは通常版と別のReleaseへ公開し、検証済みlockを明示的に更新します。

出典と利用条件は [NOTICES.md](../src/main/dictionary-quality/NOTICES.md)、
[JMnedict公式仕様](https://www.edrdg.org/enamdict/enamdict_doc.html)、
[EDRDG利用条件](https://www.edrdg.org/edrdg/licence.html)に記載しています。
