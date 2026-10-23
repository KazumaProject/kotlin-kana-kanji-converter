# 漢方・商品名を再利用可能な手順で収集する

`scripts/collect_dictionary_terms.py` は公開資料の明示された表記と読みを機械抽出し、実際の辞書入力から作った索引で未収録語を選びます。LLM・推定読み・全件再分類は使用しません。漢方は `kampo`、メーカー名付きの医薬品名と商品・ブランド名は `product` に追加します。

## 準備

辞書生成に必要なMozc等のリソースは通常のビルドと同じです。作業領域とPython環境はリポジトリ外に作ります。

```sh
collection_work_dir="$HOME/.cache/kotlin-kana-kanji-converter/term-collection"
python3 -m venv "$collection_work_dir/venv"
collection_python="$collection_work_dir/venv/bin/python"
"$collection_python" -m pip install -r scripts/requirements-term-collection.txt
./gradlew exportExistingDictionaryInventory
```

## 収集・確認・取り込み

```sh
"$collection_python" scripts/collect_dictionary_terms.py collect --resume
# 表示された batch.json のパスを使用する
"$collection_python" scripts/collect_dictionary_terms.py verify --batch /outside/repository/batch.json
"$collection_python" scripts/collect_dictionary_terms.py apply --batch /outside/repository/batch.json
```

`collect` は設定済みの有効な収集元を件数上限なしで処理します。最大4並列、同一ホストは1通信です。`--source tsumura_kampo kobayashi_brands` のように対象を限定できます。`--resume` は取得済みの成功応答を再利用し、失敗したページを再取得します。最新の公開情報へ更新する場合は `--resume` を外します。ETag・Last-Modifiedが提供される場合は条件付き取得を行います。

`batch.json` は採用候補、同じディレクトリの `report.json` は収集元別件数・重複・保留・取得失敗を記録します。`complete` は有効な収集元の処理完了を示し、無効化中の収集元は `disabledSources` に別記します。通信・抽出失敗は終了コード2となり、成功した収集元の結果とキャッシュを保持します。

`verify` は通信せず、保存した応答のSHA-256と、原文から再抽出した表記・読みの一致を検証します。`apply` も公開サイトへ通信せず、この検証と現在の辞書との再照合を行います。現在の分類・除外判断との衝突は拒否します。同じバッチの再適用は追加0件です。

取り込みは既存のレビュー機構を利用し、商品を一般名詞・コスト9400、漢方を既存ルールのコスト9000で追加します。品詞IDは現在の `id.def` から解決します。一時領域で分類辞書を検証し、実際のKotlin生成経路で更新後の既存辞書索引を作ってから漢方・医療の重複を再計算します。検証完了後に固定データと出典付き採用語を反映します。全件のAI分類履歴は開き直しません。

処理中の強制終了で `apply-journal.json` が残った場合は、次の操作で保存済みバックアップから更新前へ戻し、`apply` を再実行してください。

```sh
"$collection_python" scripts/collect_dictionary_terms.py recover
```

Gradle・JDK・Python依存パッケージの準備は事前に必要です。`apply` 内のGradleは通常のビルドと同じ依存解決を行います。

## 読みと収集元の設定

`src/main/collection/sources.json` に収集元ID、カテゴリ、URL、抽出方式を指定します。HTMLは商品名専用のCSSセレクタ、JSONは表記・読みのフィールドを使用します。HTMLの複数ページには `follow_selector` と同一ホスト内の `follow_url_pattern` を指定できます。同じ形式の収集元は設定追加で再利用でき、新しいデータ形式には抽出処理を追加します。

- カナの商品名は機械的にひらがな化します。表記の内部空白・英字大小・幅・異体字は保持します。
- 漢字・英字名はルビや明示された読みだけ使用します。型番、説明文、括弧内の機能名から読みを推定しません。パナソニックでは英字ブランドの明示読みと確認済みカナ名に限定します。
- ツムラ医療用JSONは `name` と `nameKana` の対応を利用します。一般用JSONの読み欄は処方名のみのため、設定したパターンで処方名を抽出し、製品名全体へ読みを転用しません。原フィールドも出典データへ保存します。
- 表記が原資料間で食い違う「竹如温胆湯」は `withhold_surfaces` で保留します。無断で別の漢字へ訂正しません。
- KNApSAcKの保存済み原本は既存収録との照合に利用し、提供元読みを新たな確認済み読みへ格上げしません。Wikidataは候補探索専用で、公式資料による裏付けなしには採用しません。
- サントリーは確認時にHTTP 403となり、実HTMLの抽出セレクタを未確認のため無効化しています。取得可能になった際は実際の製品名要素を確認し、セレクタを設定してから有効化してください。

`collect` は辞書を編集しません。HTML・HTTPキャッシュ・SQLite索引・ログ・一時ファイル・バックアップは `--work-dir`（既定は上記キャッシュディレクトリ）に保存します。リポジトリ内の作業ディレクトリは拒否します。Gitへ追加するのは必要な実装・設定・テスト・採用語と出典データ・生成済み辞書入力・収録一覧だけです。

## 検証と収録一覧

```sh
"$collection_python" -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/write_classified_dictionary_catalog.py
python3 scripts/write_classified_dictionary_catalog.py --check
./gradlew buildDictionaryDistributionManifest test check
```

既存の収録一覧の完全な再生成には、現在の分類マニフェストに記録されたSHA-256と一致するローカルLuna台帳が必要です。台帳なしでの `--check` は、既存仕様どおり不採用理由ページと `summary.json` の照合をスキップします。台帳をリポジトリへ追加しないでください。

配布ZIPの読み戻しは収録値の検証です。実IMEの登録、学習、候補表示・順位、互換性はこのCLIでは確認しません。

## English

The collector extracts explicitly published names and kana readings without model calls. Configure sources in `src/main/collection/sources.json`, then run `collect`, inspect `report.json`, run offline `verify`, and `apply` the printed batch path. `--resume` reuses successful cached responses; omit it for conditional refreshes. Disabled sources are reported separately. Failed active sources return exit code 2 without discarding successful work.

Application rechecks the current dictionary, validates source hashes and extracted evidence, stages both dictionary families, and exports the real Kotlin baseline inventory before updating frozen data. Reapplying a batch adds zero pairs. `recover` restores an interrupted application from its external journal and backups. Keep caches, logs, downloaded pages, and generated archives outside Git. Full catalog regeneration requires the existing private Luna ledger matching the manifest hash. IME runtime behavior and candidate ranking are not verified.
