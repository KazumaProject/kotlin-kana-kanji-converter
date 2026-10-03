# 配布辞書の内容・収録範囲・利用方法

## 今回の変更と利用対象

MozcUT人名・地名、Wiki、Neologd、共通の**既存5入力**から、読み・表記と意味分類を確認できた補助語彙を12カテゴリへ収録します。参照用Mozc・JMdict・日本郵便・公式資料から、新しい見出しを追加して語数を増やしてはいません。

今回、外部情報に読みがないだけで正しい語を保留する問題と、本名の読みを別名へ流用する問題を修正しました。JMdictの制約付きペア・語義・分野から一般語、専門語、食品などを分類する経路を追加しました。全かな表記も、独立した名称の存在と読みの完全一致が両方確認できる場合に限って採用します。WikidataのP1814/P5168を名称別に保存し、同名別対象の読みを混ぜません。

本リポジトリのLOUDS形式を読むエンジン向けの**補助辞書**です。通常の文章変換にはシステム辞書と接続行列を併用します。`person.dic`の単一ファイルではなく、`person/`の3バイナリが人名辞書です。カテゴリは辞書名から分かるため、各エントリにはカテゴリ文字列を追加しません。

元の左右文脈IDと単語コストを保持し、同一読み・表記・左右IDの重複は統合します。複数の意味が裏付けられた語は複数カテゴリへ収録します。実行時には同じ解析候補・変換表記を重複させません。コストの再学習は行っていません。

## 全件比較と採否

2026-10-03の固定入力での実測です。Mozcは `c7538e6f8ee56ff94789494106ad5d6d658cd4f6`。各版の入力・成果物ハッシュはZIPのmanifestが正本です。

| 指標 | 今回 |
|---|---:|
| 5入力の元行数 | 1,103,684 |
| 正規化・統合後 | 1,064,924 |
| 標準収録 | 372,438 |
| 独立した読みは確認済み・未分類 | 16,360 |
| 読み・名称対応が未解決、分類あり | 157,702 |
| 読み・名称対応が未解決、未分類 | 518,424 |
| 正規化段階の除外行 | 119 |
| 正規化段階の保留行 | 1,594 |

採否は読みと意味分類の別軸です。標準収録には両方が必要です。保留676,126件と未分類534,784件には重複があり、足してはいけません。現在の標準未収録は692,486エントリです。正規化段階の行数とも単位が違います。

旧版の未収録**719,520エントリ全て**の再評価結果を保存しました。

| 旧未収録の現在の扱い | 件数 |
|---|---:|
| 新たに標準収録へ救済 | 31,601 |
| 読み・対象対応が未解決 | 671,576 |
| 読み確認済み・分類未確定 | 16,340 |
| 根拠付きで誤ペアを除外 | 3 |
| 再評価記録の欠落 | 0 |

3組は `伊藤桃々／いとうもももも`、`来迎寺駅／らいごうじえき`、`鎌田安里紗／かまたありさ`です。公式資料の読みを確認して除外しました。同名項目の違う読みがあることだけでは除外しません。

旧収録345,407件のうち340,837件を保持し、4,570件を確認用へ戻しました。4,550件は名称と読みの対応不足、20件は意味分類不足です。これらを誤語と断定してはいません。新規救済31,601件と差し引いて**標準収録の純増は27,031件**です。全件の移動理由は `comparison/previously-published-losses.tsv.gz` に残します。

## 12カテゴリの実際の内訳

件数の単位は読み・表記・左右文脈IDの組です。表記数・読み数はカテゴリ内で重複を除き、バイナリbytesは3ファイルの展開後合計です。

| ID | 対象 | 旧版エントリ | 今回エントリ | 表記数 | 読み数 | バイナリbytes |
|---|---|---:|---:|---:|---:|---:|
| `person` | 人名・姓・名 | 165,597 | 165,089 | 164,736 | 153,237 | 3,884,150 |
| `place` | 地名・正式住所 | 166,526 | 168,832 | 166,743 | 167,248 | 4,796,102 |
| `facility` | 建物・施設・道路 | 4,468 | 4,633 | 4,612 | 4,268 | 162,006 |
| `station` | 駅・停留所 | 5,070 | 5,070 | 5,051 | 5,020 | 167,356 |
| `organization` | 企業・学校・団体 | 2,612 | 4,605 | 4,599 | 4,598 | 181,008 |
| `product` | 商品・ブランド・ソフトウェア・サービス | 106 | 346 | 345 | 344 | 13,860 |
| `work` | 作品 | 632 | 4,165 | 4,164 | 4,146 | 158,614 |
| `character` | 架空人物・神話の登場者 | 548 | 1,554 | 1,552 | 1,551 | 50,888 |
| `event` | 行事・祭り・大会・賞 | 82 | 321 | 321 | 321 | 15,406 |
| `food` | 食品・料理・飲料 | 42 | 648 | 647 | 613 | 20,876 |
| `technical` | 具体的分野の専門語 | 32 | 2,926 | 2,920 | 2,901 | 102,752 |
| `general` | 一般名詞等の確認済み語義 | 2 | 15,829 | 15,781 | 15,240 | 448,834 |

一般語10,000、専門語1,500、食品250、商品200の公開判定目安を全て満たしました。これは網羅性や全語の正しさを保証する数ではありません。一般語は一般名詞の語義を確認する経路で増え、未分類を流し込んではいません。食品はfood分野等、専門語はIT・科学・数学・医療・工学・法律等の具体的な分野から判定します。

facilityには道路・橋・市場も含み、温泉地はplace、駅はstationへ分類します。productはOS・具体的なソフトウェア等も含み、プログラミング言語はtechnicalを優先します。characterには神話の登場者も含みます。eventには巡礼・賞も含むため、単に現地で開催する催事だけの辞書ではありません。

複数カテゴリに属するのは1,512エントリ。`GitHub／ぎっとはぶ`はorganizationとproduct、`高畑／たかばたけ`はpersonとplaceです。人名入力に含まれる`DeepSeek`はorganizationで、personにはしません。

## 実際の収録例と確認待ち例

確認待ち例は500件の調査標本から選んだものです。一部は追加調査で救済済みであり、現在の採否は監査・explainを参照してください。確認できないことと語が不適切なことを区別します。

| カテゴリ | 今回収録した例 | 調査した保留例 |
|---|---|---|
| `person` | ぁぃぁぃ／ぁぃぁぃ、HIDEBOH／ひでぼー | 司馬攸／しばゆう |
| `place` | 高畑／たかばたけ、市原市原田／いちはらしはらだ | タシカン川／たしかんがわ |
| `facility` | 赤坂Bizタワー／あかさかびずたわー、渋谷スクランブルスクエア／しぶやすくらんぶるすくえあ | 館林城／たてばやしじょう |
| `station` | 来迎寺駅／らいこうじえき | 南幌駅／なんぽろえき |
| `organization` | DeepSeek／でぃーぷしーく、RIZE／らいず | RIZE／らいず |
| `product` | NetBeans／ねっとびーんず | Labelflash／れーべるふらっしゅ |
| `work` | 臨済録／りんざいろく、日本三代実録／にほんさんだいじつろく | 少女アリス／しょうじょありす |
| `character` | 神産巣日神／かみむすひのかみ、難陀／なんだ | 李珪／りけい |
| `event` | 銀熊賞／ぎんくましょう、知多四国霊場／ちたしこくれいじょう | 今回の保留標本に該当なし（未収録語がないという意味ではない） |
| `food` | かまたまうどん／かまたまうどん、カカオ豆／かかおまめ | 今回の保留標本に該当なし（未収録語がないという意味ではない） |
| `technical` | Java／じゃば、Java／じゃゔぁ、Python／ぱいそん、論理合成／ろんりごうせい | 三酸化キセノン／さんさんかきせのん |
| `general` | 過剰消費／かじょうしょうひ、通勤ラッシュ／つうきんらっしゅ | 今回の保留標本に該当なし（未収録語がないという意味ではない） |

`藍畑(高畑)`は読み境界を確認して藍畑・高畑へ分離し、第十など意味のある町域も残します。`赤坂赤坂Bizタワー`と`渋谷渋谷スクランブルスクエア`は、正式施設名と境界読みの根拠から余分な地名を表記・読みの両方で除きます。`市原市原田`、一円、作品の意味のある括弧は単純な反復削除や注記削除の対象にしません。

## 入力出典別の内訳

出典は見出しの元入力であり、読み・分類の確認元とは別です。複数出典・カテゴリが重なるため列の合計は全体件数と一致しません。

| 入力 | 正規化後 | 標準収録 | 確認用 |
|---|---:|---:|---:|
| MozcUT人名 | 70,403 | 16,109 | 54,294 |
| MozcUT地名 | 162,921 | 159,163 | 3,758 |
| Wikiのみ | 150,132 | 41,403 | 108,729 |
| Neologdのみ | 404,816 | 18,207 | 386,609 |
| Wiki・Neologd共通 | 308,185 | 159,248 | 148,937 |

| カテゴリ | MozcUT人名 | MozcUT地名 | Wikiのみ | Neologdのみ | 共通 |
|---|---:|---:|---:|---:|---:|
| `person` | 15,451 | 254 | 23,631 | 5,987 | 134,284 |
| `place` | 6 | 159,158 | 11,592 | 701 | 4,318 |
| `facility` | 2 | 24 | 2,050 | 594 | 1,972 |
| `station` | 0 | 1 | 152 | 40 | 4,877 |
| `organization` | 311 | 10 | 825 | 892 | 2,699 |
| `product` | 5 | 0 | 54 | 98 | 192 |
| `work` | 29 | 5 | 729 | 218 | 3,193 |
| `character` | 140 | 4 | 292 | 277 | 916 |
| `event` | 0 | 0 | 61 | 12 | 248 |
| `food` | 14 | 2 | 185 | 160 | 291 |
| `technical` | 7 | 3 | 486 | 789 | 1,642 |
| `general` | 221 | 152 | 1,495 | 8,683 | 5,302 |

## 読みの確認元と分類の根拠

JMdictの最終固定データは22,250の既存読み・表記ペア、23,987の一意な語義詳細です。取込み時の語義訪問数24,046には正規化等による重複があります。計画時の22,256組から最終データに変化したため、計画の一致数を採用数として報告しません。

`re_restr`・`re_nokanji`・`stagk`・`stagr`、継承POS、廃用表示を守り、無条件の表記×読みの総当たりを行いません。品詞が名詞であるだけで作品や人名を一般語にしません。日本三代実録・臨済録・うながっぱの語義など、標本で見つけた誤分類は根拠付きで補正しています。Wikidataの直接タイトル・別名検索・型の具体性を区別し、曖昧な検索結果はそのまま採用しません。

採用語で確認した読み根拠は次の通りです。複数根拠のある語は各行に数えます。

| 読み根拠 | エントリ |
|---|---:|
| 確認済み対応表 | 33 |
| かな表記と対象確認 | 13,630 |
| Wikidata読み | 174,384 |
| JMdict制約付きペア | 19,738 |
| Mozc同一読み・表記 | 5,657 |
| 日本郵便 | 159,151 |

元入力間の一致、機械生成した読み、Wikidataタイトル一致だけでは読み確認済みにしません。全かな表記は独立した名称確認と一致検証が必要です。本名・別名・同名異読は名称別に根拠を保持します。

## Actionsで公開するファイル

`v*`タグで成功すると、通常のGitHub Releaseに2つのZIPを公開します。

```text
Release v<version>
├── japanese_keyboard_dictionary_assets.zip  従来形式48ファイル
└── categorized-dictionaries.zip             新カテゴリ41ファイル
```

カテゴリZIPは既存パッケージ処理と別出力先で生成します。内部は次の構成です。12ディレクトリは全て同じ3ファイルを持ちます。

```text
categorized-dictionaries.zip
├── manifest.json
├── NOTICES.md
├── LICENSE-JMDICT.html
├── LICENSE-CC-BY-SA-4.0.txt
├── pos_table.dat
├── person/       ├── yomi.dat  ├── tango.dat  └── token.dat
├── place/        （同じ3ファイル）
├── facility/     （同じ3ファイル）
├── station/      （同じ3ファイル）
├── organization/ （同じ3ファイル）
├── product/      （同じ3ファイル）
├── work/         （同じ3ファイル）
├── character/    （同じ3ファイル）
├── event/        （同じ3ファイル）
├── food/         （同じ3ファイル）
├── technical/    （同じ3ファイル）
└── general/      （同じ3ファイル）
```

計37バイナリと4文書。カテゴリ文字列は個別エントリに入れず、ディレクトリ名から判断します。`unclassified/`は標準ZIPに含めません。CLI・監査TSV・参照DBも辞書ZIPには含めません。

従来ZIPのルートは `app/src/main/assets/` です。system、出典別補助辞書、接続行列、id.def、旧POS表、emoji等を維持します。**従来出典別辞書を全て品質確認済みへ置換した変更ではありません。** 品質判定済み補助候補を使うにはsystem＋必要なカテゴリを選びます。旧wiki/neologd/person_name/places/webも読むと、カテゴリ側で保留した語が旧辞書から出る場合があります。

2つのPOS表は同名でも交換できません。ZIPを平坦化して上書きしないでください。37・48ファイルの全パス・bytes・SHAは[実測JSON](dictionary-inventory.json)に記載しています。

手動workflow_dispatchでは通常Releaseを作らず、Artifactsへ保存します。

| Artifact | 内容 |
|---|---|
| `dictionary-release-packages` | `release_zips/japanese_keyboard_dictionary_assets.zip`、`build/category-release/categorized-dictionaries.zip` |
| `categorized-dictionary-reports` | manifest、summary、audit.tsv.gz、review.tsv.gz、全719,520件のcomparison/reassessment、旧収録からの移動記録、600語・200文の最良/上位10候補、未処理research/pending.tsv.gz |
| `english-dictionary-report` | 既存English分析報告 |
| `ngram-build-report` | 既存n-gram生成報告 |

PRは全量生成せず小規模fixtureを実行します。公開権限はタグのpublish jobだけです。固定データ欠落・チェックサム不一致、カテゴリ目安未達、600語95%未達、文章の最良/上位10候補の後退、未レビューの監査版はビルド失敗となり公開しません。監査ハッシュが変わる版は再レビューと記録更新が必要です。Mozc masterの更新で該当した場合も、黙って旧記録で公開しません。

### 固定メタデータは別Release

[固定データRelease](https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/tag/dictionary-metadata-841246a60a852ed8)には次の6資産を保存しました。

```text
dictionary-metadata-841246a60a852ed8
├── snapshot.sqlite.gz
├── snapshot.lock.json
├── NOTICES.md
├── LICENSE-JMDICT.html
├── LICENSE-CC-BY-SA-4.0.txt
└── baseline-audit.tsv.gz
```

圧縮96,727,451 bytes、展開404,365,312 bytes（512MiB以内）。圧縮SHAは `841246a60a852ed86e8d2d864d97c13a43f9adc1ce27fdfa8ba48be39c26c358`、DB SHAは `464cefa914990d434dbd25f5811bb48dacbebf876bec53f995893f646dd5a0ce`。コミット済みlockで指定し、空の保存先から公開URLで取得・両SHAを検証しました。通常ビルドに巨大なローカルDBや有料APIは不要です。

手動更新workflowは既定200リクエスト・30分で候補版と未処理キューを保存し、JMdict更新も選択できます。初期照合の全件数を200件へ制限していません。通常入力lockは自動変更しません。Actionsキャッシュは高速化用で、データ原本はこのReleaseです。

JMdict参照・派生情報に必要な出典とCC BY-SA 4.0を表示し、EDRDG公式利用条件とライセンス本文をZIPへ同梱します。Wikipedia個別調査のURL・日付・確認事項はreading-research.json、他出典の条件はNOTICES.mdへ記載しました。

## 配布物を使って確認する手順

### カテゴリだけの辞書引き

リポジトリでCLIをインストールし、カテゴリZIPを専用ディレクトリへ展開します。

```sh
./gradlew installDist
CLI=./build/install/kana-kanji-converter/bin/dictionary-cli
unzip categorized-dictionaries.zip -d build/downloaded-categories
$CLI verify-package --output categorized-dictionaries.zip
$CLI lookup --dict-dir build/downloaded-categories --no-system   --categories facility --reading あかさかびずたわー --format json
$CLI lookup --dict-dir build/downloaded-categories --no-system   --categories person,place --reading たかばたけ --format json
```

施設辞書引きの結果例です。

```json
[{"dictionary":"facility","reading":"あかさかびずたわー","surface":"赤坂Bizタワー","leftId":1851,"rightId":1851,"cost":8406}]
```

`--no-system` を付けたlookupにはsystemや接続行列は不要です。JSONの `dictionary` が所属カテゴリ、`reading/surface/leftId/rightId/cost` が実際に読み込んだ語の情報です。カテゴリを省略すると全12カテゴリを選択します。

### システム辞書と組み合わせた変換

同じReleaseの既存ZIPも展開し、必要な資源だけを別ディレクトリに用意します。単語バイナリの内側のZIPと、接続行列ZIPをそれぞれ展開します。

```sh
unzip japanese_keyboard_dictionary_assets.zip -d build/downloaded-legacy
mkdir -p build/downloaded-system
unzip build/downloaded-legacy/app/src/main/assets/system/yomi.dat.zip -d build/downloaded-system
unzip build/downloaded-legacy/app/src/main/assets/system/tango.dat.zip -d build/downloaded-system
unzip build/downloaded-legacy/app/src/main/assets/system/token.dat.zip -d build/downloaded-system
unzip build/downloaded-legacy/app/src/main/assets/connectionId.dat.zip -d build/downloaded-system
cp build/downloaded-legacy/app/src/main/assets/pos_table.dat build/downloaded-system/
cp build/downloaded-legacy/app/src/main/assets/id.def build/downloaded-system/
$CLI convert --dict-dir build/downloaded-categories --base-dir build/downloaded-system   --categories facility --input しぶやすくらんぶるすくえあ --nbest 10 --format json
$CLI test --dict-dir build/downloaded-categories --base-dir build/downloaded-system   --cases src/main/dictionary-quality/conversion-cases.tsv
```

接続行列とid.defはカテゴリと同じMozc版を使います。CLIはカテゴリmanifestのid.defハッシュと、選んだカテゴリバイナリのハッシュを照合します。異なるReleaseから混在させず、対応する2ZIPを一緒に取得してください。

品質判定済み語だけを補助候補にしたい場合は、system＋必要なカテゴリを読み込みます。さらに従来のwiki/neologd/person_name/places/webを同時に読み込むと、カテゴリ側で保留・除外した語が従来辞書から出る可能性があります。

アプリへの実装では `LoadedDictionary.load(categoryId, categoryDir, categoryPosTable)` でカテゴリを読み、systemはsystem用POS表で読み込み、`KanaKanjiEngine.loadDictionaries` に辞書一覧と接続行列を渡します。ファイルを追加するだけでは有効化されません。[ローダー](../src/main/kotlin/dictionary/LoadedDictionary.kt)と[CLIの実装例](../src/main/kotlin/cli/DictionaryCli.kt)を参照してください。

### 収録されなかった理由を調べる

`explain` はバイナリでなく監査ファイルを参照します。Actionsの `categorized-dictionary-reports` も取得・展開してください。

```sh
$CLI explain --reports build/downloaded-reports   --surface 渋谷渋谷スクランブルスクエア --format json
$CLI explain --reports build/downloaded-reports   --reading ぎふはぶ --surface GitHub --format json
```

固定データを `metadata fetch` で準備すると、`explain --snapshot build/dictionary-metadata/snapshot.sqlite` は対象ID・名称別の読み・JMdict語義も表示します。DBがない場合は事実の詳細が利用できないことを明示します。

`audit.tsv.gz` は正規化と分類の両段階を含みます。`phase`、入力出典、元の読み・表記、修正後の読み・表記、categories、reason、左右ID・コスト、quality_status、reading_evidenceを保存します。`review.tsv.gz` は標準辞書から外した未分類・保留・除外の確認用データです。単にlookupで見つからないことから「語が不適切」と判断せず、これらの理由を確認します。


## 実用評価と残る課題

| 評価 | 旧版 | 今回 |
|---|---:|---:|
| 固定600語の指定カテゴリに出現 | 464/600（77.33%） | 580/600（96.67%） |
| 固定200文の期待変換が最良 | 145/200 | 164/200 |
| 固定200文の期待変換が上位10 | 180/200 | 199/200 |
| 旧版成功例からの最良・上位10の後退 | — | どちらも0 |

600語は元入力から50件/カテゴリを選び、最初の新版辞書生成前に固定しました。ただし実装着手前に固定する計画条件は満たせず、実装開始後の固定です。初回の誤った温泉分類1件は根拠とともに補正し、旧版・新版の両方を同じ評価セットで再実行しました。変更前後のハッシュはevaluation-corrections.jsonへ残します。

200文は4種の短い文脈を組み合わせた固定試験で、自然な文章コーパスや実端末の利用評価ではありません。負のコストと同一候補の組合せで旧経路探索がメモリを使い切ったため探索を修正し、**辞書比較の旧版・新版には同じ修正済みエンジンを使用**しました。元の旧エンジンの200文結果が改善したという比較ではありません。

未出現20語の全理由と、上位10に出ない1文は[検証記録](dictionary-quality-review.md)に記載しています。語数目安を満たしても、頻度に合う候補順位、網羅性、モバイルでの速度・メモリ、自然文の精度を保証しません。

新規採用1,110件（各カテゴリ100件、駅は新規10件全て）と保留500件の読み・型・語義の保存済み根拠を確認しました。問題のある例は公式資料やWikipediaで追加調査し、規則・対応表を修正しました。これは全語の人手確認でも、全1,610件について公式サイトを開いたという意味でもありません。[確認方法と行別記録](dictionary-quality-review.md)を保存しています。

## 内訳の再集計

[実測JSON](dictionary-inventory.json)に全カテゴリ・出典・採否・ZIPパス・ハッシュを保存します。版が変わる場合はその版のArtifactsから再集計してください。

```sh
python3 scripts/report-category-inventory.py   --reports build/reports/dictionary-quality   --category-zip build/category-release/categorized-dictionaries.zip   --legacy-zip release_zips/japanese_keyboard_dictionary_assets.zip   --output docs/dictionary-inventory.json
```
