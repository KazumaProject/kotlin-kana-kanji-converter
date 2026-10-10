# 助数詞辞書の測定記録

以下は初期版（索引なし）の記録です。末尾文字索引の変更前後の比較は後半に記載します。
測定日：2026-10-09。対象はJKCR v1の初期収録データです。
測定環境はApple M2、macOS、aarch64、OpenJDK 17.0.12です。
Pixel 4・Android上での実行時間と保持メモリは未測定です。

## 容量と収録内容

| 項目 | 値 |
| --- | ---: |
| 辞書本体 | 41,327 bytes（40.36 KiB） |
| 辞書の容量目標 | 65,536 bytes（64 KiB） |
| 助数詞・単位ID | 141 |
| 数の部品 | 75 |
| 接続レコード | 667 |
| 個別例外 | 75 |
| 別表記 | 34 |
| 3索引の状態数合計 | 1,100 |
| 索引の配列要素 | 18,674 bytes |
| 辞書＋変換器の保持量概算 | 86,240 bytes（84.22 KiB） |

辞書のSHA-256：
`7decaa2574df37bd341898f08a655afed0a7987f956ce7fef3bfa5a42f732e08`

141は意味を分けたID数です。同じ表記の「日」でも暦日・期間を別のIDにしています。
数字と助数詞の全件登録は行っていません。101、123、Long.MAX_VALUEまでの数量は、
同じ有限の部品・規則から組み立てます。数字3表記も保存せず、候補生成時に作ります。

保持量はテスト専用JOLによるデスクトップJVMのオブジェクトグラフ概算です。
クラスメタデータ・静的フィールド・読み込み中の一時バッファ・候補結果を含みません。
圧縮参照等のVM条件は推定を含むため、Androidの保持量として使用しないでください。

## 候補取得

正解・不正解、数量・時刻、長い数量を含む106入力を順番に巡回しました。
ウォームアップ10,000回後に100,000回を測定し、別表記あり・候補数制限なしで実行しています。
同一入力の結果キャッシュは使っていません。

| 項目 | 値 |
| --- | ---: |
| p50 | 1,083 ns（0.001083 ms） |
| p95 | 2,917 ns（0.002917 ms） |
| p99 | 4,625 ns（0.004625 ms） |
| 平均 | 1,635 ns（約0.001635 ms） |
| 最大 | 18,001,166 ns（18.001166 ms） |
| 初回の辞書読み込み＋変換器作成 | 12.221959 ms |
| 1変換あたりの割当量概算 | 1,740.048 bytes |

数・助数詞・時刻の解析、候補文字列の生成、結果のチェックサム計算を含みます。
JSON出力・Gradle/JVM起動は含まず、各呼び出しのタイマーのオーバーヘッドは含みます。
割当量はThreadMXBeanによる概算で、測定配列の要素分を差し引いています。
初回読み込みは1回の観測で、コールド起動の分位点や最悪値ではありません。

最大値はp99から大きく離れています。この測定では外れ値の原因を特定していません。
p95/p99から最悪時間を保証できず、Pixel 4の目標（p95 1 ms、p99 3 ms、
ロード20 ms、保持量512 KiB）の達成は実機で確認する必要があります。

## 既存LOUDSとの索引比較

同じ541の逆向き接続キー、791検索入力、各30,000回の完全一致検索で比較しました。
逆順の入力は事前生成し、数の復元・数量解析・助数詞ごとの接続レコードは含めていません。
両方とも全検索の一致・不一致が同じで、チェックサムは20,558でした。

| 索引 | 保存量 | 保持量概算 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: |
| CSR配列トライ | 13,750 bytes | 13,864 bytes | 167 ns | 208 ns |
| 既存LOUDS | 4,370 bytes | 21,512 bytes | 333 ns | 375 ns |

既存LOUDSはこのキー集合では保存量が小さい一方、現行APIの保持量と検索時間はCSRが小さい
結果でした。辞書全体が64 KiB以内に収まることも踏まえ、初期実装はCSRを採用しています。
比較対象のLOUDS保存量には既存APIのJava外部化形式を使用しています。
これは索引単独の比較で、変換全体やAndroid上の優劣を示す測定ではありません。

## 検証結果

網羅テストとCLIの詳細は[詳細テスト結果](counter-test-results.md)に記録しています。

- TSVの独立した正解・不正解例106件：全件合格。
- 既存テストを含むJUnit 115件：失敗0、エラー0、スキップ1。
- 通常実行でスキップした全辞書生成を別途有効にして2件実行：失敗0、エラー0、スキップ0。
- かな読みの時・分・秒全86,400通り、数量0〜9,999、Long.MAX_VALUE・オーバーフロー、同時実行、破損データを検証。
- 配布ZIPの構成検証に成功し、格納した辞書と生成元のバイト列が一致。

配布ZIP検証では既存の通常辞書資源を再利用し、新しい助数詞辞書を生成して組み込みました。
ZIP検証とは別に、通常辞書全体の再生成を一時ディレクトリでテストしました。

## 再現

この変更のworktreeで実行します。

```sh
./gradlew buildCounterDictionary counterTest
./gradlew -q counterCli --args='check'
./gradlew -q counterCli --args='benchmark --warmup 10000 --iterations 100000 --report build/reports/counter/benchmark.json'
```

生成レポートは`build/reports/counter/build.json`、`benchmark.json`、`memory.json`、
`index-comparison.json`に出力します。測定値はマシン・JIT・負荷の影響で変わります。
未測定のAndroid項目と利用方法は[規則辞書の説明](counter-dictionary.md)を参照してください。

## 末尾文字索引の事前生成比較 / Precomputed ending-index comparison

測定日：2026-10-09（Toronto）。Apple M2 / macOS 26.6.2 (25G83) / aarch64 /
JBR OpenJDK 17.0.12+1-b1207.37、`-Xms256m -Xmx256m`。
変更前はコミット`333c338bbbcf9feada95796cf1e88e3aa6473bc4`のクラスと41,327バイトの辞書で先に測定し、
変更後は同じ元データから生成した49,523バイトの索引付き辞書で測定しました。
旧変換器そのものは索引を持ちません。「実行時索引」は提示された生成仕様を加えた計測専用対照で、
JapaneseKeyboardアプリ全体ではありません。索引の再生成はテスト専用ベンチマークにだけ存在します。

| 条件 | ファイルbytes | 辞書＋変換器の保持bytes（JOL） |
| --- | ---: | ---: |
| 旧変換器のみ / Original | 41,327 | 86,240 |
| 旧＋実行時索引 / Runtime control | 41,327 | 94,448 |
| 格納済み索引 / Stored | 49,523 | 94,456 |

保持量は辞書・変換器・対照用索引の到達可能オブジェクトグラフです。
クラスメタデータ、静的フィールド、入力バッファ、一時オブジェクト、変換結果を含みません。
JOLの圧縮参照・アラインメント推定を含むPCの概算です。格納済み索引は1配列で8,208 bytes
（要素8,192＋JVM配列ヘッダー等）、旧辞書との差8,216 bytesには辞書の参照・アラインメントも含みます。
対照と変更後の保持量差は8 bytesで、変換器を増やしても索引配列は増えません。

### 初回の読み込み＋変換器作成

各条件・各経路につき新規JVM30回（合計180 JVM）。JVM起動、ByteArrayの事前読み込み、
計測基盤の準備は除外し、初回の辞書クラス初期化、検証・デコード、変換器作成、
対照では索引生成も含めます。Stream経路はファイルopen/read/closeを含みます。
OSのファイルキャッシュは消していません。p95/p99はnearest-rankで、30回のp99は最大値です。
割当量はThreadMXBeanで計測範囲を挟んだ値の中央値です。

| 条件・入力 | 中央値ms | p95 ms | p99 ms | 割当bytes（中央値） |
| --- | ---: | ---: | ---: | ---: |
| 旧変換器のみ / Original / bytes | 20.566792 | 21.430875 | 21.472709 | 2,102,744 |
| 旧変換器のみ / Original / stream | 20.767958 | 22.411958 | 22.498125 | 2,276,008 |
| 旧＋実行時索引 / Runtime control / bytes | 25.203209 | 26.414458 | 27.603708 | 2,948,072 |
| 旧＋実行時索引 / Runtime control / stream | 25.443084 | 27.079292 | 27.186792 | 3,121,336 |
| 格納済み索引 / Stored / bytes | 34.886750 | 120.529416 | 129.820416 | 2,113,624 |
| 格納済み索引 / Stored / stream | 34.188083 | 72.561916 | 80.827792 | 2,295,088 |

### ウォームアップ後

各条件は1 JVMで5回測定。read＋createとconverter-onlyは毎回2,000回ウォームアップ・5,000回計測。
ByteArray/Streamの実行順は交互です。converter-onlyは読み込み済みの同じ辞書から作成し、
対照では毎回索引生成、格納済みでは配列の再生成・コピーを含みません。
既存の別表記・例外などの変換器補助メタデータの作成は全条件で含みます。
変換は同じ106入力を巡回し、毎回10,000回ウォームアップ・100,000回計測、別表記あり・無制限です。
結果をvolatile参照へ保存して消去を防ぎ、解析・候補文字列を含めます。JSON/JVM起動は除外。
時間配列の確保は計測前、計時と結果保存のオーバーヘッドは含みます。

末尾判定は同じ9入力（123本・二粒・午後3時半・12:30・買う・出会う・空文字・日本・１ヶ月）、
1,024判定のバッチを2,000回ウォームアップ・5,000回計測します。
下表のpredicate値はバッチ時間÷1,024で、個々の判定の分位点ではありません。
割当量は総割当÷操作数で、バッチ結果のボックス化等も含みます。

次の表は**5回の各分位点・割当平均の中央値**です。25,000/500,000サンプルの合算分位点ではありません。
全5回の分位点も後掲します。GC/JIT/OS負荷や条件の測定順の影響を排除できません。

| 条件・範囲 | 中央値ns | p95 ns | p99 ns | 平均割当bytes/op |
| --- | ---: | ---: | ---: | ---: |
| 旧変換器のみ / Original / load-bytes | 85,833.000 | 102,542.000 | 120,834.000 | 264,215.590 |
| 旧変換器のみ / Original / load-stream | 117,083.000 | 138,625.000 | 168,250.000 | 436,919.590 |
| 旧変換器のみ / Original / converter | 14,375.000 | 15,875.000 | 22,291.000 | 32,903.590 |
| 旧変換器のみ / Original / convert | 458.000 | 1,167.000 | 1,667.000 | 1,594.615 |
| 旧＋実行時索引 / Runtime control / load-bytes | 94,750.000 | 109,209.000 | 123,458.000 | 276,039.590 |
| 旧＋実行時索引 / Runtime control / load-stream | 125,625.000 | 142,584.000 | 160,417.000 | 448,743.590 |
| 旧＋実行時索引 / Runtime control / converter | 25,375.000 | 26,833.000 | 32,833.000 | 44,727.590 |
| 旧＋実行時索引 / Runtime control / predicate | 5.127 | 5.290 | 11.067 | 12.475 |
| 旧＋実行時索引 / Runtime control / convert | 458.000 | 1,167.000 | 1,625.000 | 1,594.615 |
| 格納済み索引 / Stored / load-bytes | 211,333.000 | 577,959.000 | 2,493,459.000 | 274,655.590 |
| 格納済み索引 / Stored / load-stream | 151,458.000 | 412,875.000 | 1,037,958.000 | 455,559.590 |
| 格納済み索引 / Stored / converter | 25,583.000 | 58,083.000 | 106,875.000 | 35,111.590 |
| 格納済み索引 / Stored / predicate | 2.400 | 6.999 | 10.824 | 0.031 |
| 格納済み索引 / Stored / convert | 625.000 | 2,250.000 | 3,458.000 | 1,594.615 |

この測定で、初回・ウォームアップ後の読み込みや変換器作成の時間短縮は確認できませんでした。
変更後には大きな外れ値もあり、速度改善を主張しません。今回の保証は同じ索引のビルド時生成、
配列共有、変換器作成時の索引走査・再生成の排除です。対照に比べconverter-onlyの割当量は減少し、
末尾判定の実装はCharのボックス化を避けますが、計測ハーネスの微小な割当は残ります。
変換本体は変更していません。分位点の変動から最悪時間やAndroidの改善量を判断できません。

### 各回の分位点

各セルは中央値 / p95 / p99（ns）。predicateはバッチ平均の1判定あたりです。

| 条件・範囲 | run 1 | run 2 | run 3 | run 4 | run 5 |
| --- | --- | --- | --- | --- | --- |
| 旧変換器のみ / Original / load-bytes | 85,833.000 / 114,500.000 / 202,709.000 | 85,916.000 / 100,875.000 / 114,042.000 | 85,542.000 / 102,542.000 / 120,834.000 | 85,792.000 / 101,125.000 / 115,458.000 | 91,125.000 / 229,542.000 / 304,250.000 |
| 旧変換器のみ / Original / load-stream | 117,250.000 / 144,875.000 / 174,917.000 | 116,583.000 / 136,500.000 / 158,375.000 | 116,625.000 / 137,042.000 / 165,417.000 | 117,083.000 / 138,625.000 / 168,250.000 | 118,667.000 / 272,000.000 / 365,750.000 |
| 旧変換器のみ / Original / converter | 14,458.000 / 16,417.000 / 24,291.000 | 14,292.000 / 15,584.000 / 18,917.000 | 14,334.000 / 15,917.000 / 22,291.000 | 14,375.000 / 15,875.000 / 22,625.000 | 14,416.000 / 15,708.000 / 16,917.000 |
| 旧変換器のみ / Original / convert | 1,125.000 / 2,917.000 / 6,958.000 | 667.000 / 1,542.000 / 2,166.000 | 458.000 / 1,166.000 / 1,625.000 | 458.000 / 1,125.000 / 1,583.000 | 458.000 / 1,167.000 / 1,667.000 |
| 旧＋実行時索引 / Runtime control / load-bytes | 95,083.000 / 110,417.000 / 123,458.000 | 95,417.000 / 109,209.000 / 119,833.000 | 94,750.000 / 107,958.000 / 124,125.000 | 94,459.000 / 106,792.000 / 119,708.000 | 94,750.000 / 110,250.000 / 132,958.000 |
| 旧＋実行時索引 / Runtime control / load-stream | 124,667.000 / 141,334.000 / 160,417.000 | 125,625.000 / 142,584.000 / 157,333.000 | 125,917.000 / 144,458.000 / 165,125.000 | 125,042.000 / 141,917.000 / 158,666.000 | 128,458.000 / 164,625.000 / 197,458.000 |
| 旧＋実行時索引 / Runtime control / converter | 25,375.000 / 26,833.000 / 32,833.000 | 25,500.000 / 33,000.000 / 36,417.000 | 25,375.000 / 26,625.000 / 30,500.000 | 25,375.000 / 26,584.000 / 28,917.000 | 25,459.000 / 30,208.000 / 55,125.000 |
| 旧＋実行時索引 / Runtime control / predicate | 4.964 / 5.249 / 11.922 | 5.127 / 5.249 / 11.067 | 5.127 / 5.290 / 11.963 | 5.167 / 5.290 / 6.673 | 5.168 / 5.575 / 9.929 |
| 旧＋実行時索引 / Runtime control / convert | 1,125.000 / 2,750.000 / 6,500.000 | 667.000 / 1,542.000 / 2,167.000 | 458.000 / 1,167.000 / 1,625.000 | 458.000 / 1,125.000 / 1,584.000 | 458.000 / 1,125.000 / 1,584.000 |
| 格納済み索引 / Stored / load-bytes | 211,333.000 / 586,708.000 / 2,493,459.000 | 148,583.000 / 332,542.000 / 806,083.000 | 213,042.000 / 577,959.000 / 4,553,167.000 | 117,291.000 / 273,084.000 / 351,959.000 | 225,541.000 / 801,916.000 / 4,004,541.000 |
| 格納済み索引 / Stored / load-stream | 319,042.000 / 810,917.000 / 4,613,750.000 | 145,417.000 / 412,875.000 / 1,188,833.000 | 151,458.000 / 422,916.000 / 1,037,958.000 | 151,125.000 / 391,875.000 / 961,375.000 | 168,375.000 / 383,208.000 / 548,958.000 |
| 格納済み索引 / Stored / converter | 48,250.000 / 63,209.000 / 166,709.000 | 27,708.000 / 58,083.000 / 106,875.000 | 25,583.000 / 58,459.000 / 111,916.000 | 25,583.000 / 53,167.000 / 78,083.000 | 25,459.000 / 53,041.000 / 77,708.000 |
| 格納済み索引 / Stored / predicate | 2.401 / 7.080 / 14.689 | 2.360 / 6.998 / 8.504 | 2.400 / 6.999 / 10.824 | 2.359 / 6.958 / 12.939 | 2.400 / 6.999 / 7.528 |
| 格納済み索引 / Stored / convert | 1,750.000 / 6,125.000 / 15,334.000 | 875.000 / 4,541.000 / 8,042.000 | 625.000 / 2,250.000 / 3,458.000 | 584.000 / 2,042.000 / 3,292.000 | 542.000 / 1,833.000 / 3,125.000 |

### 測定の限界・再現

Android実機（Pixel 4・Pixel 6）の変更前後、実アプリの初期化経路、ARTの割当・保持メモリは未測定です。
ユーザー提供のPixel 6の0.441773 / 0.432455 / 0.476481 ms（中央値0.441773 ms）は、
旧アプリでの索引生成だけの3回測定であり、本表の読み込み＋作成とは比較しません。
事前生成してもI/O、CRC検査、配列確保・読み込みと既存の補助メタデータ作成は残り、初期化はゼロではありません。

テスト専用`CounterEndingBenchmark`をtest runtime classpathでJavaから起動します。
`baseline`/`control`は変更前クラス・旧辞書、`stored`は変更後クラス・索引付き辞書を使用します。
通常のJUnit・Android・配布ZIPにはこの測定ツールを組み込みません。

```sh
java -Xms256m -Xmx256m -cp "$TEST_RUNTIME_CLASSPATH" \
  com.kazumaproject.counter.CounterEndingBenchmark stored src/main/resources/counter/counter_rules.dat
# 新規JVMを各入力経路30回起動する（cold bytes または cold stream）
java -Xms256m -Xmx256m -cp "$TEST_RUNTIME_CLASSPATH" \
  com.kazumaproject.counter.CounterEndingBenchmark stored src/main/resources/counter/counter_rules.dat cold bytes
```

**English:** Measurements use Apple M2, macOS 26.6.2, aarch64, JBR OpenJDK 17.0.12,
256 MiB initial/max heap. The original classes were measured before edits. The runtime control adds
only the supplied ending-index construction, not the full JapaneseKeyboard application.
Cold rows use 30 fresh JVMs per condition/input path, excluding JVM startup; byte arrays are preloaded,
while stream timing includes file open/read/close. OS caches are not flushed. Warm rows use five runs,
each with 2,000 warmup/5,000 measured loads or creations; conversion uses the same 106 cases with
10,000 warmup/100,000 calls. Predicate timing divides 1,024-operation batches and does not describe
single-call tails. Percentiles use nearest rank. Summary rows are medians of five per-run estimates;
all per-run percentiles are shown above. Allocation uses ThreadMXBean; retained graphs use JOL and
exclude static/class/transient/result storage. Result sinks and timers are included, JSON is excluded.

No improvement in load/creation latency was demonstrated; post-change timing includes substantial
outliers. Converter-only allocation decreased against the runtime-construction control, and the
bitset is retained once without regeneration or copying. JVM/JIT/GC/order/OS effects remain.
None of these PC numbers establish Android gains or worst-case latency. The supplied Pixel 6 index-only
three-sample median is not a dictionary-load measurement. Android/ART and application-path results
remain unmeasured. Precomputation still incurs I/O, validation and array allocation/loading.
