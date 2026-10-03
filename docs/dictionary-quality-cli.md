# 品質確認済みのカテゴリ辞書とCLI

通常のMozc辞書を変換の土台にし、MozcUT人名・地名、Wiki、Neologd、共通入力から補助辞書を生成します。標準配布には、読み・表記の独立した根拠と意味カテゴリの両方を確認できた語を収録します。珍しい固有名詞や正しい連結住所も対象です。

収録内容、カテゴリ別・出典別の実測内訳、ReleaseとArtifactsの全ファイル構成、配布ZIPを使う手順は [配布辞書の詳細](dictionary-distribution.md) を参照してください。

## 固定メタデータを使った生成

既存ビルドと同じMozc入力資源を準備し、同一版のid.def・接続行列・辞書を使用します。

```sh
./gradlew installDist
CLI=./build/install/kana-kanji-converter/bin/dictionary-cli
$CLI metadata fetch
$CLI metadata verify --lock src/main/dictionary-quality/snapshot.lock.json
./gradlew run
$CLI build
$CLI package
$CLI verify-package
```

`metadata fetch` はコミット済みロックのRelease URL・圧縮ファイルSHA-256・展開後DB SHA-256を検証します。既存の正しいDBがあれば再利用します。欠落・破損はエラーとし、空データへの切替はありません。生成はオフラインで、外部情報の取得は `metadata refresh` へ分離しました。固定データが対応する入力5ファイルのハッシュも確認します。

初回公開前のローカル検証には、取得済みの圧縮ファイルを指定できます。

```sh
$CLI metadata fetch --archive build/dictionary-metadata/snapshot.sqlite.gz
```

## 品質判定と分類

品質状態は `accepted`（読み・表記の根拠あり）、`held`（根拠不足・不一致）、`excluded`（案内文・壊れた住所断片など）。カテゴリが不明という理由だけで語を不適切と判断しません。品質がacceptedでも意味分類が未確定なら標準辞書へ収録せず、確認用データに残します。利用頻度は採否の基準にしていません。

読みの根拠は、同一読み・表記の通常Mozc入力、日本郵便の正式町域・読み、外部エンティティの読み、根拠URL付き確認済み対応です。補助入力どうしの一致だけで独立した読みの証拠とはしません。Wikidataに読みがない場合、タイトルが一致するだけで品質をacceptedにはしません。

カテゴリは次の12個です。

| ID | 内容 |
|---|---|
| person | 実在人物、人名、姓、名 |
| place | 地名、行政地域、正式住所 |
| facility | 建物・施設 |
| station | 駅・停留所 |
| organization | 企業・学校・団体 |
| product | 商品・ブランド・具体的なソフトウェアやサービス |
| work | 書籍・漫画・アニメ・映画・ゲーム・楽曲などの作品 |
| character | 架空のキャラクター |
| event | イベント・祭り・大会 |
| food | 食品・料理・飲料 |
| technical | IT・科学・数学・医療・工学の専門概念 |
| general | 確認済みの一般語 |

Wikidataの直接タイトル対応と別名検索を区別し、直接対応を優先します。検索由来の同名項目は読み一致が必要です。型は具体性・包含関係を考慮し、言語型は一般的なソフトウェア型より優先します。サービス兼企業などの裏付けられた独立役割は複数カテゴリへ収録します。人名入力に含まれる団体を出典名だけで人名にしません。一般名詞IDや「概念」「用語」という広い型だけでは一般語へ分類せず、確認済み対応を必要とします。

出力は `person/yomi.dat`・`person/tango.dat`・`person/token.dat` の既存形式です。ルートの専用 `pos_table.dat` を共有します。エントリへカテゴリを追加せず、実行時に辞書名から判断します。複数カテゴリの同じ解析候補とN-best表記は重複させません。かな表記が読みと異なる場合も元の表記を保存します。

旧版のunclassified辞書は標準出力から廃止し、所有していた3ファイルだけを生成時に削除します。`--categories all` は12カテゴリを選択します。未分類の中には有用な語もあるため、後述のreviewデータを利用して根拠を追加します。

## 地名・建物の清掃

地名出典の括弧を解析し、読み境界を確認できる場合に `藍畑(高畑)` を `藍畑／あいはた` と `高畑／たかばたけ` に分離します。数字だけでは注記にせず、`藍畑(第十)` の `第十／だいじゅう` も残します。階数・丁目・番地などは明示単位と構造で判定します。

町域と施設の連結には、削る町域の読みと、修正先の正式施設名の根拠が必要です。`赤坂赤坂Bizタワー`・`渋谷渋谷スクランブルスクエア` の余分な町域を表記・読みの両方から除きます。途中に反復がある `大阪市北区中之島中之島ダイビル` のような構成も同じ規則で扱います。修正先が一意でなければ保留します。単純に反復文字を削る処理は行いません。

`市原市原田`、実在町域の `一円`・`明野ハイツ`、作品の意味のある括弧は保持します。`の次に番地がくる場合` などの郵便案内文や、壊れた括弧の住所断片は除外します。既存の出典別辞書生成にも同じ地名清掃を適用します。

## 辞書引き・変換・理由表示

```sh
$CLI lookup --reading あいはた --no-system
$CLI lookup --surface 赤坂Bizタワー --categories facility --no-system
$CLI lookup --reading やまだ --prefix --categories person --no-system
$CLI convert --input しぶやすくらんぶるすくえあ --categories facility --nbest 10
$CLI explain --surface 渋谷渋谷スクランブルスクエア --format json
$CLI explain --reading ぱいそん --surface Python
$CLI test --cases src/main/dictionary-quality/lookup-cases.tsv --no-system
$CLI test --cases src/main/dictionary-quality/conversion-cases.tsv
```

`explain` は生成時のauditから元候補・修正先・品質状態・読みの根拠・カテゴリ根拠を表示します。辞書に収録されなかった語も確認できます。

読みの検索は完全一致が既定です。前方一致・表記検索は読みを列挙するため時間がかかります。`--format json` に対応します。`--categories person,place`、`--exclude-categories product`、システムのみの `--categories none`、カテゴリのみの `--no-system` を指定できます。システムと各カテゴリのPOS表を正しく選び、カテゴリmanifestと成果物チェックサム、変換時のid.def互換性を検証します。

ケースTSVは `operation,input,assertion,expected,categories` の5列です。lookup/surfaceはcontains/excludes、convertはequals（最良結果）またはcontains/excludes（N-best）を使用します。終了コードは成功0、期待不一致・変換なし1、入力・設定エラー2です。

## 固定データの初期作成・更新・公開

```sh
$CLI metadata export \
  --metadata-db /path/to/read-only-original.sqlite \
  --postal-zip /path/to/utf_ken_all.zip \
  --output build/dictionary-metadata/snapshot.sqlite.gz \
  --lock src/main/dictionary-quality/snapshot.lock.json
$CLI metadata refresh \
  --snapshot build/dictionary-metadata/snapshot.sqlite \
  --output build/metadata-candidate/snapshot.sqlite.gz \
  --lock build/metadata-candidate/snapshot.lock.json \
  --api-budget 200 --minutes 30
scripts/publish-dictionary-metadata.sh
```

初期作成だけ元DBの `titles(title,entity_ids)`・`entity_searches(title,entity_ids)`・`entities(id,body)` を読み取り専用で参照します。元DBをコピーせず、旧分類結果も使用しません。必要な日本語・英語の名前、読み、型、3段までの型の祖先、直接対応の由来、revisionだけを新DBへ保存します。日本郵便は市区町村・町域・読みの各列を区別して取り込みます。

更新は上限200リクエスト・30分が既定です。途中終了では未処理キューを維持します。新しい郵便データは `--postal-zip` で追加できます。取得した確認済み事実だけを保存し、通常ビルドのロックを変更しません。`refresh` の既定出力は `build/metadata-candidate/snapshot.sqlite.gz` と、その隣の候補lockです。読み・型が不足する項目も更新キューへ入れ、取得失敗・予算終了による未処理項目を保持します。

スナップショットのタグは `dictionary-metadata-<SHA prefix>` とし、古い `v*` Releaseの削除対象から外します。公開済みスナップショットを上書きせず、通常の辞書Releaseに代わるlatestにも設定しません。新しい版の採用は候補lockをレビューしてコミットすることで行います。公開用スクリプトは認証済みGitHub CLIを必要とします。

## CI・報告・ストレージ

既存のタグ・手動ビルドはロック済みデータを取得し、オフラインで生成・CLI回帰テスト・ZIP検証を行います。タグReleaseには既存ZIPと別の `categorized-dictionaries.zip` を公開します。手動ビルドでも辞書・報告をArtifactsから取得できます。公開権限はpublish jobだけに付与します。

PR・mainへのpushは `dictionaryQualityTest` の独立したfixtureテストを実行します。全Mozc辞書やEnglish入力は不要です。メタデータ更新workflowは手動実行し、検証した候補スナップショットを別Releaseへ公開します。現在のlockを自動変更しません。

`build/reports/dictionary-quality` にmanifest、summary、`audit.tsv.gz`、未分類・保留・除外の `review.tsv.gz` を出力します。manifestには入力・固定データ・確認済み対応・実装・成果物のハッシュを記録します。CIは実際のMozc commit・English Release・ソースcommitも記録します。同一入力・ルール・固定データからバイナリを再現できます。Mozc masterとEnglish latestの既存取得方針は維持し、取得した実版を記録します。

展開後のスナップショットは512 MiB以内です。巨大なダンプ・元DBのコピー・生APIレスポンスは保存しません。作業用DB・展開・ビルド用POS表は成功・失敗時とも削除します。Actionsキャッシュは必須入力の原本にはしません。出典と利用条件はカテゴリZIP内のNOTICES.mdを参照してください。

分類改善の集計、500件の層化確認と修正結果、ローカルとLinux CIの検証結果は [検証記録](dictionary-quality-review.md) にまとめています。
