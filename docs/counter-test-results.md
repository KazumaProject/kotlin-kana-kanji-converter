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

## 末尾文字索引追加の検証 / Ending-index extension validation

JKCRのversionは1のままです。索引付き49,523 bytes、SHA-256：
`c1a470c655692ed3eb95ece7a16c6babf7916fef69192b2601498b931417a4c0`。
追加8,196 bytesを除いてヘッダーを旧長さ・CRCへ戻したバイト列は、旧41,327 bytesの
SHA-256 `7decaa2574df37bd341898f08a655afed0a7987f956ce7fef3bfa5a42f732e08`と一致します。
TSV、語彙・読み・例外・優先度、既存ペイロードは変更していません。

- 通常JUnit：121件、失敗0・エラー0・スキップ1。助数詞関連29件は全件成功。
- 通常実行でスキップする全辞書生成を別途有効化：2件、失敗0・エラー0・スキップ0。
- CLIの別Javaプロセス21通り、旧・新辞書の106正解例、JSONL、終了コード0/1/2、生成失敗時の既存出力保持を確認。
- UTF-16全65,536値を、元データから独立に作った文字集合と照合。旧データは全非空入力true、空文字false。
- 123本・二粒・午後3時半・12:30・日本・本はtrue、買う・出会う・空文字はfalse。
- ビット境界0/63/64/127/128/65535とサロゲートを確認。判定はコードポイントではなく最後のUTF-16 Char。
- 全例外、接尾辞なし例外、全別表記、数字3表記、Long.MAX_VALUE、時刻・半・時計表記を確認。
- 全接続読み、正解例、時間・分境界、時・分・秒86,400通りについて旧・新の解析結果と候補内容・順序が一致。
- 既存の独立した数量・音変化・大きな数・時刻の網羅テストでも、生成された各候補がフィルターを通ることを追加確認。
- 索引件数0/1023/1025/-1/Int.MAX_VALUE、正しいCRCを持つ不足・余剰、未知version 0/2/99、CRC破損・切り詰めを拒否。
- private配列が1本、変換器は同じ辞書を参照、索引を返す公開APIなし、入力ByteArrayを変更しても判定は不変。
- 同じ元データの複数回ビルドで完全一致。ビルドCLIも全65,536値の意味を確認してから書き込み。
- 配布ZIPの49ファイル構成とcounter辞書のバイト一致を確認。Gradle配布検証にもバイト一致チェックを追加。

```sh
./gradlew buildCounterDictionary counterTest test
./gradlew packageJapaneseKeyboardDictionaryAssets verifyJapaneseKeyboardDictionaryAssets -x generateJapaneseKeyboardDictionaries
# 実辞書の全生成はdictionaryBuildTestへテスト出力/classpathを補う既存の一時init scriptで実行
./gradlew -I build/reports/counter/full-build-test.init.gradle dictionaryBuildTest
```

ローカルZIP生成は既存の通常辞書資源を再利用し、counterを新規生成しました。
全辞書生成テストは別に実行しています。Actionsでは通常の配布フローで全辞書を生成・検証します。
公開ZIPの確認結果はPRに記載します。新しいコミットの検証用タグを使用し、既存タグ・成果物は上書きしません。

Android実機・実アプリの初期化、JapaneseKeyboardへの組み込み、文章解析・文法判定・設定画面は未検証・対象外です。
時間・割当・保持量の測定条件と限界は[性能記録](counter-performance.md)を参照してください。

**English:** Standard suite: 121 tests, zero failures/errors, one intentionally skipped full-build case;
29 counter tests passed. The separate full-dictionary build suite passed both tests with no skips.
Twenty-one separate-process CLI scenarios and all 106 golden cases passed, including legacy loading,
JSONL, exit codes and preservation of existing output on failed builds.

All 65,536 UTF-16 values match an independently derived character set. Representative positive/negative
cases, boundary bits, surrogates, all exceptions (including empty suffixes), alternate surfaces,
three numeric notations and time/half-hour/clock surfaces are covered. Legacy and indexed dictionaries
produce identical analyses and ordered candidates, including 86,400 hour/minute/second combinations.
Existing independent exhaustive conversion tests also assert that generated candidates pass the filter.

Correct-CRC malformed counts/lengths, truncation, surplus bytes, unknown versions and CRC corruption
are rejected. Tests establish private single-array ownership, shared dictionary references and independence
from caller buffers. Repeated builds are deterministic. Removing the extension and restoring the header
reproduces the original dictionary SHA-256 exactly. Build-time validation checks every UTF-16 value before
writing. The 49-asset ZIP is validated and its counter bytes match the generated asset; this byte check is
also part of Gradle distribution verification. Local ZIP checks reused legacy assets, with full legacy
regeneration tested separately. The normal Actions workflow generates and validates the complete bundle.
Published-download verification is reported in the PR. Android/application-path performance and
JapaneseKeyboard integration remain outside this validation.
