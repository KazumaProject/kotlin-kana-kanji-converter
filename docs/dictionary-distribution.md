# 配布辞書の内容・収録範囲・利用方法

## このPRで何を変えたか

これまではMozcUT人名・地名、Wiki、Neologdの**出典別**に辞書を作成していました。このPRはそれを維持したうえで、同じ補助入力から**読みと分類の根拠を確認できたエントリだけを選ぶ、12カテゴリの追加配布物**を作成します。

1. 地名入力の括弧・郵便案内文・重複した地名と施設名を整理します。正式施設名と読みが一意に確認できる場合だけ、表記と読みを修正します。
2. 「変換候補として読み・表記を確認できるか」と「何の語か」を別々に判定します。分類できただけの語は採用しません。
3. 固定メタデータ、日本郵便、Mozcの同一読み・表記、根拠付き対応表を使い、確認済みの語を12カテゴリへ振り分けます。
4. カテゴリを選んで辞書引き・変換するCLI、採否の理由を確認する監査データ、固定データ更新処理を追加します。
5. Actionsで既存ZIPとカテゴリZIPを生成・検証します。PR用の小規模テストと、外部情報更新の手動workflowを追加します。

**既存出典別ZIPをすべて品質判定済みへ置き換えたPRではありません。** 地名の清掃は既存生成にも反映していますが、読みの根拠と意味分類による採否の絞り込みはカテゴリ辞書に適用します。分類や根拠不足でカテゴリ辞書から外した語が、既存出典別辞書には残る場合があります。

## 現時点でどの用途に使えるか

この配布物は、本リポジトリのLOUDS形式を読む変換エンジンの**補助辞書**です。人名・地名を中心に、読みの裏付けのある固有名詞をカテゴリ単位で追加する用途を想定しています。通常の文章変換はシステム辞書と接続行列を併用します。

今回の固定入力では、収録345,407エントリの大部分を人名と地名が占めます。商品106、食品42、専門語32、一般語2という規模なので、商品・食品・専門語・一般語を網羅する辞書としては使えません。12カテゴリが存在することは、12分野の網羅性を保証しません。収録頻度や候補順位の実用評価も、このPRでは完了していません。

カテゴリは語の役割であり、Mozcの品詞IDを置き換えるものではありません。固有名詞にも一般名詞にも元の左右文脈ID・単語コストを保持します。同一読み・表記・左右文脈IDの重複は統合し、出典間でコストが異なる場合は小さいコストを採用します。今回コストの再学習は行っていません。

`person.dic` のような単一ファイルではなく、`person/` の3バイナリが人名辞書です。Mozcのユーザー辞書TSV、標準Mozcの辞書バイナリ、他IMEのインポート形式ではありません。Androidアプリへファイルを置くだけで自動的に読み込まれる変更も含みません。アプリ側でカテゴリ辞書のローダーを使用する必要があります。

## 件数の数え方と全体の採否

以下は2026-10-03の固定入力で生成した実測値です。検証したLinuxビルドは[Actions run 37115162429](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/runs/37115162429)、生成コードは `2b858145441dee98f7540925964133a38f00fc0c`、Mozcは `c7538e6f8ee56ff94789494106ad5d6d658cd4f6` です。以後入力やルールが変われば件数は変わります。各Releaseの `manifest.json` がその版の値です。

- 入力行：1,103,684。括弧分離・除外・重複統合後：1,064,927エントリ。
- エントリの単位：読み・表記・左文脈ID・右文脈IDの組。
- 標準収録：345,407エントリ。今回のデータでは読み・表記の組も345,407、異なる表記は342,901、異なる読みは329,765。
- 1エントリが複数カテゴリや出典に属する場合があるため、表の列・行の合計は全体のエントリ数と一致しない場合があります。

| 読み・表記の品質状態 | 意味分類あり | 未分類 | 標準辞書へ収録 |
|---|---:|---:|---|
| accepted：独立した読みの根拠あり | 345,407 | 5,419 | 分類ありの345,407のみ |
| held：読みの根拠不足・不一致 | 169,678 | 544,423 | 収録しない |

標準辞書から外した正規化済みエントリは719,520です。読みが未確認の714,101と、読みを確認できたが未分類の5,419を含みます。「カテゴリ未確定」549,842は両行の未分類の合計で、品質heldと重なるため、714,101に足してはいけません。

heldの内訳は、独立した読みの根拠がない699,772と、読みが未確認または不一致の14,329です。後者をすべて「誤った読み」と確定したわけではありません。元入力に有用で正しい語が含まれていても、現在の固定データだけでは確認できず保留する場合があります。

正規化段階では別に116行を除外（郵便案内34、壊れた括弧82）、1,594行を保留（施設連結を一意に修正できない1,519、括弧の読み境界不明75）しています。この行数は上記の正規化済みエントリ数と単位が異なります。

## 12カテゴリの実際の内訳

表記数・読み数は各カテゴリ内の重複を除いた数です。バイナリbytesは3ファイルの展開後合計で、共有POS表とmanifestを含みません。

| ID | 収録対象 | エントリ | 異なる表記 | 異なる読み | バイナリbytes |
|---|---|---:|---:|---:|---:|
| `person` | 人名・姓・名 | 165,597 | 165,222 | 152,137 | 3,867,798 |
| `place` | 地名・正式住所 | 166,526 | 164,438 | 164,934 | 4,727,674 |
| `facility` | 建物・施設・道路等 | 4,468 | 4,444 | 4,053 | 153,002 |
| `station` | 駅・停留所 | 5,070 | 5,051 | 5,019 | 167,332 |
| `organization` | 企業・学校・団体 | 2,612 | 2,610 | 2,573 | 111,536 |
| `product` | 商品・サービス | 106 | 106 | 106 | 4,674 |
| `work` | 作品 | 632 | 632 | 627 | 26,788 |
| `character` | 架空キャラクター | 548 | 547 | 510 | 18,466 |
| `event` | イベント | 82 | 81 | 82 | 4,378 |
| `food` | 食品・料理・飲料 | 42 | 42 | 38 | 1,934 |
| `technical` | 専門語 | 32 | 31 | 31 | 1,738 |
| `general` | 一般語 | 2 | 2 | 2 | 502 |

facilityは建物だけでなく、型の根拠がある道路・橋なども対象です。stationは駅の表記を保持し、自動的に「駅」を外した略称を増やしません。personには姓・名・人物名を含みますが、出典の人名ファイルに入っていることだけではpersonと判定しません。

一般語は `過剰消費／かじょうしょうひ` と `通勤ラッシュ／つうきんらっしゅ` の2エントリです。一般名詞POSやWikidataの広い「概念」「用語」型だけで一般語に振り分けないため、ここは特に収録が少なくなっています。

複数カテゴリへ収録するエントリは294です。例えば `GitHub／ぎっとはぶ` はproductとorganization、`高畑／たかばたけ` はpersonとplaceに収録します。それぞれの役割の根拠を確認し、実行時に同じ解析候補・同じ変換表記を重複させない処理を追加しています。カテゴリ所属数の合計は345,407を超えます。

## 出典別の採用・確認待ち

ここでの出典は入力ファイルであり、分類の根拠や読みの検証元とは別です。例えばWiki入力の語を日本郵便で確認することもあります。入力内の重複統合・正規化後の語に出典を付与して集計しているため、元ファイルの物理行数ではありません。

| 入力出典 | 正規化後にこの出典を持つエントリ | 標準収録 | 確認用データ |
|---|---:|---:|---:|
| MozcUT 人名 (`person`) | 70,405 | 15,523 | 54,882 |
| MozcUT 地名 (`place`) | 162,921 | 159,163 | 3,758 |
| Wiki のみ (`wiki`) | 150,132 | 36,940 | 113,192 |
| Neologd のみ (`neologd`) | 404,817 | 9,968 | 394,849 |
| Wiki・Neologd 共通 (`common`) | 308,185 | 145,380 | 162,805 |

Neologdの約40万エントリを一括採用したわけではありません。読みや対象項目との対応が確認できないものが多く、今回の収録は9,968です。この制限を理解せず、旧Neologd辞書の完全な代替として扱うことはできません。

カテゴリごとの入力出典の内訳は以下です。同じ語の複数出典は各列に数えます。

| カテゴリ | MozcUT人名 | MozcUT地名 | Wikiのみ | Neologdのみ | 共通 |
|---|---:|---:|---:|---:|---:|
| `person` | 15,365 | 232 | 23,370 | 7,767 | 133,402 |
| `place` | 1 | 159,160 | 10,933 | 638 | 2,737 |
| `facility` | 0 | 12 | 1,881 | 718 | 1,858 |
| `station` | 0 | 0 | 151 | 44 | 4,875 |
| `organization` | 42 | 39 | 433 | 433 | 1,695 |
| `product` | 2 | 0 | 11 | 62 | 32 |
| `work` | 4 | 1 | 84 | 86 | 459 |
| `character` | 112 | 1 | 52 | 201 | 240 |
| `event` | 0 | 0 | 14 | 6 | 62 |
| `food` | 2 | 0 | 10 | 6 | 24 |
| `technical` | 0 | 0 | 5 | 13 | 14 |
| `general` | 0 | 0 | 1 | 1 | 0 |

読みの採用根拠は、日本郵便159,151、Wikidataの読みP1814が184,612、Mozcの同一読み・表記1,635、根拠付き確認済み対応表9です。複数の根拠を持つ場合は重複して数えます。分類はWikidataの型、確認済み地名・対応表、限定したMozc固有名詞POSの根拠で決定します。Wikidataの日本語タイトルや別名だけでは読みを確認した扱いにしません。

旧版の未分類または新しく正規化された候補から新たに採用した数は151,063、既存採用語へのカテゴリ追加は152です。全採用345,407をすべて今回新しく増えた語として説明してはいけません。

## 変更が利用者にどう見えるか

以下の収録・除外は生成済みカテゴリ辞書とCLI回帰テストで確認しています。

| 入力・読み | 今回の扱い | 理由 |
|---|---|---|
| `藍畑(高畑)` | `藍畑／あいはた`、`高畑／たかばたけ`へ分離 | 地名と読み境界を確認。元の括弧付き候補は除去 |
| `藍畑(第十)` | `第十／だいじゅう`も保持 | 数字を含むだけでは注記と判断しない |
| `赤坂赤坂トラストタワー(31階)` | `赤坂トラストタワー／あかさかとらすとたわー`をfacilityへ | 正式施設名と読みを確認。階数と余分な地名を除去 |
| `赤坂赤坂Bizタワー` | `赤坂Bizタワー／あかさかびずたわー`をfacilityへ | 確認した地名・施設名に基づき表記と読みを修正 |
| `渋谷渋谷スクランブルスクエア` | `渋谷スクランブルスクエア／しぶやすくらんぶるすくえあ`をfacilityへ | 同上 |
| `市原市原田／いちはらしはらだ` | placeで保持 | 正しい市名と町域の連結。単純な反復削除をしない |
| `犬上郡多賀町一円／いぬかみぐんたがちょういちえん` | placeで保持 | 一円は実在の町域。金額等の注記と決めつけない |
| `Python／ぱいそん`、`Java／じゃば` | technical | プログラミング言語の型を優先 |
| `GitHub／ぎっとはぶ` | product・organization | サービスと組織の役割を保持 |
| `GitHub／ぎふはぶ` | 標準辞書へ採用しない | 読みが確認できない。表記で分類できても採用しない |
| `AWS／あまぞんうぇぶさーびす` | product | この読み・表記の組を根拠付き対応表で確認。AWSの全読みを保証するものではない |
| `岡谷市岡谷市の次に番地がくる場合` | 除外 | 郵便検索の案内文 |

実在の反復表記、意味のある作品名の括弧は一律削除しません。施設名の修正先・読みが一意に確認できない場合は保留します。正規化auditには修正前と修正後を保存します。

## ReleaseとActions Artifactsのファイル構成

### vタグによる辞書Release

`v*` タグのビルド成功後、同じReleaseへ次の**2つのZIP**を公開します。

```text
GitHub Release v<version>
├── japanese_keyboard_dictionary_assets.zip  # 従来のシステム・出典別・周辺資源
└── categorized-dictionaries.zip             # 新しい品質判定済み12カテゴリ
```

監査TSV、巨大な元DB、固定メタデータ、CLI実行ファイルは、この2つの辞書ZIPへ含めません。CLIはソースから `./gradlew installDist` で用意します。

カテゴリZIPの今回のLinux実測は **4,488,151 bytes**、展開された37バイナリの合計は **9,085,863 bytes**、ZIP内は39ファイルです。以下はディレクトリエントリを省略した全ファイル一覧です。

```text
categorized-dictionaries.zip
  NOTICES.md
  character/tango.dat
  character/token.dat
  character/yomi.dat
  event/tango.dat
  event/token.dat
  event/yomi.dat
  facility/tango.dat
  facility/token.dat
  facility/yomi.dat
  food/tango.dat
  food/token.dat
  food/yomi.dat
  general/tango.dat
  general/token.dat
  general/yomi.dat
  manifest.json
  organization/tango.dat
  organization/token.dat
  organization/yomi.dat
  person/tango.dat
  person/token.dat
  person/yomi.dat
  place/tango.dat
  place/token.dat
  place/yomi.dat
  pos_table.dat
  product/tango.dat
  product/token.dat
  product/yomi.dat
  station/tango.dat
  station/token.dat
  station/yomi.dat
  technical/tango.dat
  technical/token.dat
  technical/yomi.dat
  work/tango.dat
  work/token.dat
  work/yomi.dat
```

- `yomi.dat`：読みのLOUDS trie・term ID。
- `tango.dat`：表記のLOUDS trie。
- `token.dat`：読みから表記へのトークン、POS表index、単語コスト。
- ルート `pos_table.dat`：全12カテゴリで共有する左右文脈ID表。カテゴリごとのtokenと必ず同じ版を使います。
- `manifest.json`：形式、ルール版、カテゴリ件数、入力辞書・id.def・固定DB・対応表・実装・37バイナリのSHA-256、CIのソースcommit・Mozc commit・English Release。
- `NOTICES.md`：出典・利用条件。元の補助入力にWikipediaのページ単位の由来がないなど、保持していない出典情報も明記しています。

カテゴリZIPにはsystem、接続行列、id.defがありません。`unclassified/` もありません。ZIP内のトークンにカテゴリ文字列は書き込まず、ローダーがディレクトリ名を辞書IDとして保持します。

既存ZIPは今回のLinux実測 **28,396,970 bytes**、内部48ファイルです。ルートは `app/src/main/assets/` であり、カテゴリZIPとは階層が異なります。以下はその配下の全ファイルです。

```text
japanese_keyboard_dictionary_assets.zip/app/src/main/assets/
  connectionId.dat.zip
  emoji/tango_emoji.dat
  emoji/token_emoji.dat
  emoji/yomi_emoji.dat
  emoticon/tango_emoticon.dat
  emoticon/token_emoticon.dat
  emoticon/yomi_emoticon.dat
  english_reading/tango.dat.zip
  english_reading/token.dat.zip
  english_reading/yomi.dat.zip
  id.def
  kotowaza/tango_kotowaza.dat
  kotowaza/token_kotowaza.dat
  kotowaza/yomi_kotowaza.dat
  mozc/zero_query/zero_query_number_string.data
  mozc/zero_query/zero_query_number_token.data
  mozc/zero_query/zero_query_string.data
  mozc/zero_query/zero_query_token.data
  neologd/tango_neologd.dat.zip
  neologd/token_neologd.dat.zip
  neologd/yomi_neologd.dat.zip
  ngram/system_ngram.dat
  ngram/system_ngram_unigram.dat
  person_name/tango_person_names.dat
  person_name/token_person_names.dat
  person_name/yomi_person_names.dat
  places/tango_places.dat.zip
  places/token_places.dat.zip
  places/yomi_places.dat.zip
  pos_table.dat
  reading_correction/tango_reading_correction.dat
  reading_correction/token_reading_correction.dat
  reading_correction/yomi_reading_correction.dat
  single_kanji/tango_singleKanji.dat
  single_kanji/token_singleKanji.dat
  single_kanji/yomi_singleKanji.dat
  symbol/tango_symbol.dat
  symbol/token_symbol.dat
  symbol/yomi_symbol.dat
  system/tango.dat.zip
  system/token.dat.zip
  system/yomi.dat.zip
  web/tango_web.dat.zip
  web/token_web.dat.zip
  web/yomi_web.dat.zip
  wiki/tango_wiki.dat.zip
  wiki/token_wiki.dat.zip
  wiki/yomi_wiki.dat.zip
```

旧POS表は既存ZIPの `app/src/main/assets/pos_table.dat`、カテゴリ用POS表は新ZIPのルートにあります。**同じファイル名でも交換できません。** 同じ名前の `yomi.dat` 等もsystemと各カテゴリで別の辞書です。ZIPを同じディレクトリへ平坦化して上書きしてはいけません。

### 手動ビルド

`Build and Release JapaneseKeyboard Dictionary Assets` をworkflow_dispatchすると、辞書を生成・検証してArtifactsへ保存します。**手動実行だけでは通常の辞書Releaseを作りません。** 成功した実行のArtifactsからダウンロードします。

| Artifact名 | 内容 |
|---|---|
| `dictionary-release-packages` | 上記2つのZIP。Artifact内部は `release_zips/japanese_keyboard_dictionary_assets.zip` と `build/category-release/categorized-dictionaries.zip` |
| `categorized-dictionary-reports` | manifest、summary、audit.tsv.gz、review.tsv.gz。GitHubのArtifactを展開すると報告ファイルが得られる |
| `english-dictionary-report` | English入力の既存分析報告 |
| `ngram-build-report` | 既存n-gram生成報告 |

PR・main pushの専用テストは `dictionary-quality-fixture-tests` にHTMLテスト報告を保存します。このworkflowは全量辞書ZIPを生成しません。

### 固定メタデータRelease

分類用の固定データは辞書Releaseとは別です。

```text
GitHub Release dictionary-metadata-<archive SHA-256 prefix>
├── snapshot.sqlite.gz
└── snapshot.lock.json
```

初期版は[このRelease](https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/tag/dictionary-metadata-024ae060e380b327)です。通常ビルドはコミット済みlockから取得し、圧縮・展開後のハッシュを検証します。通常辞書ZIPの利用者がDBを読み込む必要はありません。

`Update dictionary metadata candidate` は手動で既定200リクエスト・30分の範囲で外部情報を更新し、`dictionary-metadata-candidate` Artifactと別のメタデータReleaseを作成します。通常ビルドのlockは自動変更しません。候補lockを確認して採用する手順とCLIオプションは[CLI文書](dictionary-quality-cli.md)を参照してください。

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

上の施設辞書引きをLinux配布物で実行した実際の結果です。

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

`audit.tsv.gz` は正規化と分類の両段階を含みます。`phase`、入力出典、元の読み・表記、修正後の読み・表記、categories、reason、左右ID・コスト、quality_status、reading_evidenceを保存します。`review.tsv.gz` は標準辞書から外した未分類・保留・除外の確認用データです。単にlookupで見つからないことから「語が不適切」と判断せず、これらの理由を確認します。

## 検証済みの範囲と残っている課題

- ローカル全体122テスト（失敗0、スキップ1）、専用30テストが通過。
- Linuxの専用テストと全量配布ビルドが通過。辞書引き26ケース、変換9ケース、既存ZIP・カテゴリZIPの検証が成功。
- LinuxカテゴリZIPの37バイナリのSHA-256がローカル生成物と全一致。ZIP全体はCIのcommit等を含むmanifestが異なりうるため、バイナリの一致で評価。
- 今回新規採用・役割追加の151,215エントリからカテゴリ・出典別の36層で500件を選んで確認。初回500件の問題を修正し、追加188件を含めて最終500件の読み根拠を照合。記録は[確認済み標本](../src/main/dictionary-quality/reviewed-sample.tsv)と[検証文書](dictionary-quality-review.md)。

文書の手順に沿ってLinuxの配布ZIPを新しいディレクトリへ展開し、そこから辞書引き26ケース・変換9ケースを再実行して失敗0を確認しました。施設の辞書引き結果は上記のJSON、施設変換の最良結果は `渋谷スクランブルスクエア` でした。

この500件は全345,407エントリの全件確認でも、全カテゴリの誤分類率を推定する無作為調査でもありません。未知の誤分類・読み誤りが残る可能性があります。一般文章・入力履歴を使った候補順位、速度・メモリ使用量、モバイル端末での体感評価は未実施です。「完全に分類済み」「全語が正しい」「既存辞書より変換精度が高い」とは判断していません。

次の改善対象は、読み根拠のない語への根拠追加、同名の別項目の対応確認、専門語・一般語等の小さいカテゴリの収録拡充、実際のIMEへの組込みと文章変換評価です。保留語を機械的に一般語へ入れて件数を増やす処理は実装していません。

## 数値と一覧の再集計

この文書の内訳・全ZIPファイル一覧の元データは[機械可読の実測記録](dictionary-inventory.json)です。入力auditのSHA-256、カテゴリ別の件数・出典・サイズ、採否マトリクス、全ファイルのサイズ、Linux ZIPのmanifestを含みます。

```sh
python3 scripts/report-category-inventory.py   --reports build/reports/dictionary-quality   --category-zip build/linux-ci/packages/build/category-release/categorized-dictionaries.zip   --legacy-zip build/linux-ci/packages/release_zips/japanese_keyboard_dictionary_assets.zip   --output docs/dictionary-inventory.json
```

他版を集計する場合は、その版の監査ArtifactとZIPのパスを指定してください。今回の数値を次のReleaseへそのまま流用せず、再集計して文書も更新します。
