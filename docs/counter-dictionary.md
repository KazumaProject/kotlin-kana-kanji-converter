# 助数詞・時刻の規則辞書

`counter/counter_rules.dat` は、読み全体を数量または時刻として解析する専用辞書です。
数×助数詞×数字表記の全件登録を行わず、有限の数の部品・接続規則・例外を保存します。
既存の `KanaKanjiEngine` のラティスやコストは変更していません。

## 対応範囲

- 数量：0以上の64ビット整数。101、123、任意の範囲内の整数を組み立てて解析。
- 出力：半角数字、漢数字、全角数字の順。0の漢数字は「零」。
- 本・匹などの音変化、`じっ／じゅっ`、人・日・つなどの明示した例外。
- 助数詞・単位の表記揺れ：標準表記を先に、同じ数字表記の別表記を後に。
- 時刻：時0〜23、分・秒0〜59。午前・午後・半を扱い、日本語と `HH:mm[:ss]` を出力。
- 午前12時は00:00、午後12時は12:00。午前・午後の入力は0〜12時。
- 入力：ひらがな、全角カタカナ、半角・全角数字＋助数詞のかな読み。
- 単語全体の完全一致。文中の数量の抽出、予測、文章への自動挿入は行いません。
- 小数・負数、任意の「本目・人分・枚ずつ」、24時以降は初期版の対象外。
  `番目` は明示的な独立項目で、汎用的な「目」の連結規則ではありません。

時間・暦・期間のIDは分けます。`month` は1〜12月、`day_calendar` は1〜31日、
`day_duration` は日数です。同音の「25字」は有効でも25時は無効です。
候補の文字列が同じ場合は重複を除き、解析結果には別々のIDを残します。
表記揺れの表は出力のためのもので、`m` を「えむ」と読む入力は自動生成しません。

## 元データ

`src/main/counter` のUTF-8 TSVを編集します。1行目は固定ヘッダーです。
空行と `#` で始まるコメント行を許可し、列数・余分な空白・重複・参照・範囲を検査します。
ID・元データの並び順を正規化し、同じ内容から同じバイナリを生成します。

| ファイル | ヘッダーと意味 |
| --- | --- |
| `numbers.tsv` | `reading value kind place`。`kind` はzero/part/scale/before_scale/before_k_scale。小さい部品は桁の降順、大きな単位は万・億・兆・京の降順に接続 |
| `counters.tsv` | `id surface plain voiced semi profile category min max priority`。`max=*`はLong.MAX_VALUE |
| `rules.tsv` | `profile terminal spoken_tail restored_tail suffix_form mode`。末尾の1〜9、10、100、1000、10000に適用。plain/voiced/semiを選択 |
| `exceptions.tsv` | `counter_id number reading mode output_unit`。数値全体に適用。`@inherit`は標準表記、`@empty`は接尾表記なし |
| `surfaces.tsv` | `counter_id surface priority`。標準表記は優先度0、別表記は正の優先度 |
| `cases.tsv` | `input counter_id ascii kanji fullwidth clock`。`@reject`は全候補なし。期待する解析IDと候補の存在・順序を照合 |

`replace` は、その数の末尾または特定の数値の通常読みを置き換えます。
`add` は通常読みも残します。例外は数量全体に適用するため、「ひとり」を21人には連結しません。
`とお` は「10・十・１０」を出し、「10つ」は出しません。

数の部品は1〜9、10刻み、100刻み、1000刻みと大きな単位です。300の「さんびゃく」などを
部品として登録するため、「さんひゃく」を一般則で受理しません。
「いっちょう」「いっけい」のような大きな単位の前の音変化には、有限の接続用部品を使います。
`before_scale`は兆・京の前、`before_k_scale`は京の前だけに使え、数の末尾として単独では受理しません。
数の組み合わせのための全件登録はせず、75の部品で処理します。
規則のない別読みや、全ての方言・古い和語読みを網羅した辞書ではありません。
外来単位は必要な促音形を`*_LOAN`の追加規則で受理し、基本読みも残します。
「平方メートル」のような複合単位に、先頭のハ行音だけから強制的な音変化は適用しません。
珍しい助数詞の別読みは、明示的な規則・例外と正解例を追加して拡張します。

読み・分類の確認材料：

- 既存のMozc資源にある助数詞の基本読み。数値ID・単語コストはこの形式に持ち込みません。
- [国立国語研究所：匹・本・杯などの音変化](https://kotoba.ninjal.ac.jp/qa/yokuaru/qa-225/)
- [東京書籍：「じっ」「じゅっ」の扱い](https://faq.tokyo-shoseki.co.jp/fa/customer/web/knowledge8248.html?suid=fb3b8321-0fc2-4614-8891-7ec18b58d00c)
- [国際交流基金：数・助数詞・時刻の教材](https://www.jpf.go.jp/j/urawa/j_rsorcs/textbook/dl/setsumei/setsumei_all.pdf)

## 構造とアルゴリズム

保存する索引は、CSR形式の配列トライです。状態ごとの遷移開始位置、文字、次状態、
終端の投稿開始位置とレコードIDを、IntArray/CharArrayとして保持します。
4本以下の分岐は短い走査、それ以外は二分探索します。検索中にノードのMapを構築しません。

数量は例外の完全一致と助数詞末尾の逆向き検索を行います。末尾の読みと復元する数の読みが
同じ候補は、数解析を共有します。数解析は部品の前向きトライ検索と桁の状態・整数演算を使い、
桁順序とオーバーフローを検査します。全助数詞を総当たりしません。
末尾を復元する際も、入力区間と復元文字列を参照し、数全体のsubstringを作りません。

時刻は `[午前/午後] 時 [分/半] [秒]` の固定文法で、同じ数量解析を再利用します。
時・分・秒の範囲を確認した後に時刻へ換算します。時計表記は常に24時間制です。
時計表記の入力や日付全体の変換は初期版に含めません。

文字列はUTF-8プールで重複を除きます。3つの数字表記は保存せず、解析結果から生成します。
ファイル全体の解凍やI/Oは候補検索に含めず、読み込みは1回だけです。
読み込み済みの辞書・変換器を共有できます。リクエストの状態を辞書内に保存しません。
公開結果の`number`はKotlinではLong、CLIのJSONでは精度を落とさない10進文字列です。

## バイナリ契約

JKCR v1、リトルエンディアン。JavaのObjectInputStream/ObjectOutputStreamを使用しません。

| 順序 | 内容 |
| --- | --- |
| ヘッダー16バイト | `JKCR`、version:u32、payloadLength:u32、payloadCRC32:u32 |
| 文字列プール | 件数:u32、各文字列のUTF-8長:u32とバイト列 |
| 数の部品 | 読みID:u32、値:i64、kind:u32、place:i64 |
| 助数詞 | ID/表記/分類の文字列ID、優先度:u32、min/max:i64、通常読みを禁止する末尾ビットマスク:u32 |
| 接続レコード | 助数詞ID:u32、復元読みID:u32、末尾コード:i32（-1は基本接続） |
| 例外 | 助数詞ID:u32、値:i64、読みID:u32、replace:u32、出力接尾辞ID:u32 |
| 表記揺れ | 助数詞ID:u32、表記ID:u32、優先度:u32 |
| 3つの索引 | 数部品、逆向きの接続、例外。それぞれedges:u32配列、labels:u16配列、targets:u32配列、postings:u32配列、outputs:u32配列 |

各テーブル・配列は要素数:u32を先頭に持ちます。文字列・レコード参照は0起点です。
数部品のkindはzero=0、part=1、scale=2、before_scale=3、before_k_scale=4です。
索引のedges/postingsは状態数+1件のオフセットです。構築時のBFS順の状態IDを使います。
末尾ビットは0〜9、十=10、百=11、千=12、万=13、それ以外の大きな単位=14です。
例外は助数詞ID・数値の順に並べます。文字列プールとデータの読み・IDはUTF-16辞書順で正規化します。
UTF-8、CRC、長さ、件数、参照、索引の範囲・到達性・桁の定義を読み込み時に検証します。
上限128 KiBのファイルを読み込み、64 KiB以内をテストの容量目標にします。
時刻文法・予約IDの変更はファイルversionと利用側の対応を同時に検討してください。

## 再現用CLI

既存の主ソースをコンパイルするため、Mozcの`id.def`は必要ですが、助数詞タスクは
通常辞書・Wikipedia・英語コーパスのダウンロードを必要としません。
必要なら`-PmozcIdDefFile=/path/to/id.def`を指定してください。

```sh
./gradlew buildCounterDictionary counterTest
./gradlew -q counterCli --args='inspect'
./gradlew -q counterCli --args='inspect --list'
./gradlew -q counterCli --args='convert --input ひゃくにじゅうさんぼん --input ごごさんじはん'
./gradlew -q counterCli --args='convert --input いっかげつ --no-aliases --limit 3'
./gradlew -q counterCli --args='check'
./gradlew -q counterCli --args='benchmark --report build/reports/counter/benchmark.json'
```

一括入力は、UTF-8で1行に1入力を渡します。stdoutは1入力1JSON行です。

```sh
printf '%s\n' いっぽん ごごさんじはん いちほん |
  ./gradlew -q counterCli --args='convert --stdin'
```

終了コードは正常終了0、正解照合の不一致1、引数・辞書・生成エラー2です。
未一致の変換は正常な空候補としてJSONを返します。
`build` は正解例を照合してから出力を書きます。Gradle生成タスクの出力は
`build/reports/counter/build.json`にも保存します。

## Androidで利用するコード

辞書本体は`counter/counter_rules.dat`です。Androidのassetsに配置し、
利用側のKotlinコードから読み込みます。公開読み込みAPIはInputStream/ByteArrayです。

```kotlin
val dictionary = assets.open("counter/counter_rules.dat").use { CounterDictionary.read(it) }
val converter = dictionary.converter() // 読み込み時に作り、再利用する
val result = converter.convert("ごごさんじはん", includeAliases = true, limit = 20)
// result.time: hour=15, minute=30
// result.candidates: 午後3時半、午後三時半、午後３時半、15:30
```

数量・時刻の結果をJapaneseKeyboardの候補へどう統合するかは利用側の実装で扱います。
生成した辞書は既存配布ZIPの`app/src/main/assets/counter/counter_rules.dat`に追加します。

## 性能の評価

初期実装の測定値と検証結果は[性能測定記録](counter-performance.md)に記載しています。

目標は辞書64 KiB以内、読み込み後の辞書・索引512 KiB以内、Pixel 4相当のAndroidで
候補生成込みのp95<=1 ms、p99<=3 ms、辞書読み込み20 ms以内です。実測前の目標です。

CLIのbenchmarkは、初回ロードを分離し、指定したウォームアップ後に異なる入力を巡回して
候補文字列生成まで測ります。JSON出力・Gradle/JVM起動は含まず、タイマーのオーバーヘッドと
結果のチェックサム計算は含みます。入力集合、表記揺れ、上限、環境と反復回数をJSONに保存します。
基本コーパスには正解・不正解・時刻・長い数量を含みます。同一入力の結果キャッシュは使いません。
割当量は対応するデスクトップJVMのThreadMXBeanで計測し、測定配列の要素分を差し引いた概算です。
`primitiveIndexBytes`は配列の要素分のみで、オブジェクトヘッダー・文字列・変換器の全保持メモリではありません。
`counterTest`はテスト専用の[OpenJDK JOL](https://github.com/openjdk/jol)で保持オブジェクトの概算を
`build/reports/counter/memory.json`に記録します。クラスメタデータ・静的フィールド・一時バッファは対象外です。
JOLはAndroidの配布ライブラリに含めません。VMの推定条件はレポートの`vmDetails`に残します。
同じ逆向きの接続キーで、既存LOUDSとCSRの完全一致検索・索引サイズ・保持量も比較し、
`build/reports/counter/index-comparison.json`に記録します。これは索引だけの比較で、変換全体の時間ではありません。

Pixel 4の実機は用意されていません。PCの速度はAndroid上の速度・保持メモリ目標の達成を
意味しません。Androidでの512 KiB保持メモリ目標も未検証です。
利用側では同じ辞書・入力集合を使い、通常の実行環境に加えて
[Jetpack Microbenchmark](https://developer.android.com/topic/performance/benchmarking/microbenchmark-overview)で
ウォームアップと割当量を測ります。[実機測定](https://developer.android.com/training/testing/instrumented-tests/performance)を最終判断に使用します。
