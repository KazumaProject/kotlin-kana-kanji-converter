# 助数詞辞書の詳細テスト結果

実施日：2026-10-09。Apple M2、macOS、OpenJDK 17.0.12で実行しました。
テスト対象は生成したJKCR v1辞書とKotlinの読み込み・変換処理、CLIです。
Android・Pixel 4での実行は未検証です。

## 実行結果

| 検証 | 結果 |
| --- | --- |
| 既存テストを含む通常JUnit | 115件、失敗0、エラー0、スキップ1 |
| うち助数詞関連JUnit | 23件、すべて成功 |
| 通常辞書全体の生成を含む追加JUnit | 2件、失敗0、エラー0、スキップ0 |
| 独立したTSV正解・不正解例 | 106件、すべて成功 |
| CLIを別Javaプロセスで実行 | 20通り、すべて成功 |
| 配布ZIP | 構成検証成功、格納した辞書が生成元とバイト単位で一致 |
| 辞書サイズ | 41,327 bytes、64 KiB目標以内 |

通常JUnitのスキップは`DictionaryBuildIntegrationTest.buildFullDictionaryArtifactsFromRealSources`です。
通常実行では`dictionaryBuild.full`が無効のため、既存テストの条件によってスキップします。
このテストを`dictionaryBuildTest`で別途有効にし、実データからの通常辞書・英語辞書・
接続行列の生成と既存の性能回帰制限も確認しました。通常辞書生成の基準値は変更していません。

## 助数詞の網羅テスト

追加した`CounterDetailedTest`は、生成された辞書を読み込んで検証します。
網羅用の読み生成には、実装の数パーサー・TSV音変化規則・数字表記生成関数を使いません。
期待値用の独立した読みの部品と明示した音変化を使用しています。
全件例外の往復テストは、編集用TSVの入力・数値・出力表記を契約として照合します。

| 項目 | 内容 |
| --- | --- |
| 小さい数量 | 0〜9,999のかな読み＋枚、10,000入力。数値・表記順・全角出力 |
| 大きい数量 | 万・億・兆・京の境界前後、促音形、Long.MAX_VALUE、固定シードの乱数を含む2,099入力 |
| 本・匹・杯 | 各0〜9,999、計30,000入力。促音・濁音・半濁音に加え、末尾8の別読み3,000入力 |
| 時刻 | かな読みの時0〜23×分0〜59×秒0〜59、86,400入力。時刻解析とHH:mm:ss |
| 午前・午後・半 | 午前／午後×0〜12時×0〜59秒、1,560入力。12時の換算・半・秒 |
| 数量の範囲 | 140の通常接続IDで1,680の境界例。さらに上限+1とLong.MAX_VALUE+1を拒否 |
| 個別例外 | 全75レコードがバイナリ往復後も正しい数値・ID・表記を出す |
| 表記揺れ | 全34レコードの半角候補の存在、標準表記、別表記無効化 |
| 完全一致 | 空入力、空白、余分な接尾辞、負数、小数、区切り付き数、桁順違反を拒否 |
| 正規化・候補数 | 全角数字・カタカナ、重複除去、候補上限0から候補数+1までの整合性 |
| 決定性 | TSV行をランダムに並べ替えても生成バイト列が同一 |
| 破損辞書 | CRCを再計算した22種類の不正な構造も拒否。UTF-8、参照、範囲、3索引の循環・オフセット等 |

既存の助数詞テストでは、入力ByteArrayを書き換えても読み込み後の辞書が影響を受けないこと、
4スレッドでの200回の変換、切り詰め・CRC不一致・巨大件数・不正なTSV参照も確認しています。
音の同じ語の区別にも注意し、25時を時刻として拒否しつつ「25字」の候補は許可しています。

## CLIの別プロセス検証

Gradleのタスク終了コードをCLIの終了コードと混同しないように、
コンパイル済みの`CounterCli`を`java -cp ...`から別プロセスで呼び出しました。

- `inspect`の件数・サイズ、`inspect --list`の全141ID。
- `check`の106件全成功。
- 123本、午後3時半、Long.MAX_VALUEの変換。大きな数のJSON値が文字列で精度を保つ。
- 標準入力5行とJSONL、未一致入力、全角数字・カタカナ、引用符・バックスラッシュ・タブのJSONエスケープ。
- 別表記の無効化、候補上限2・0。
- 入力不足・値不足・未知の引数・負の上限・重複フラグ・不適切なオプション・未知のコマンド・反復回数0で終了コード2。
- 不一致の正解例で終了コード1、生成失敗で終了コード2。失敗時に既存ファイルを保持。
- 正常生成で終了コード0、通常生成した辞書と同一のバイト列。CRC不一致の辞書で終了コード2。

実行記録は`build/reports/counter/cli-verification.json`に保存しています。

## 実行コマンドと条件

```sh
./gradlew counterTest --rerun-tasks
./gradlew buildCounterDictionary test --rerun-tasks
./gradlew test
./gradlew -q counterCli --args='check'
./gradlew -q counterCli --args='benchmark --warmup 10000 --iterations 100000 --report build/reports/counter/benchmark.json'
./gradlew packageJapaneseKeyboardDictionaryAssets verifyJapaneseKeyboardDictionaryAssets -x generateJapaneseKeyboardDictionaries
```

配布ZIP検証は既存の通常辞書資源を再利用し、新しい助数詞辞書を生成して実施しました。
それとは別に、通常辞書全体の生成を一時ディレクトリで検証しています。
追加の全辞書生成テストでは既存タスクにクラスパスとテスト出力を指定する一時init scriptを使用しました。
元のGradleタスクや性能基準値は変更していません。

```groovy
// build/reports/counter/full-build-test.init.gradle
allprojects {
    afterEvaluate {
        tasks.named("dictionaryBuildTest", org.gradle.api.tasks.testing.Test) {
            dependsOn(tasks.named("testClasses"))
            testClassesDirs = sourceSets.test.output.classesDirs
            classpath = sourceSets.test.runtimeClasspath
        }
    }
}
```

```sh
./gradlew -I build/reports/counter/full-build-test.init.gradle dictionaryBuildTest
```

JUnitの結果は`build/test-results/test`と`build/test-results/dictionaryBuildTest`に保存されています。
容量・速度・保持量の測定値と限界は[性能測定記録](counter-performance.md)を参照してください。
今回の確認範囲では不具合を検出していませんが、全ての助数詞の読み・方言・古い読みを網羅するものではありません。
