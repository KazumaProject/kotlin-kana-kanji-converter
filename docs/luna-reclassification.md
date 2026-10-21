# 未分類・保留・取得失敗の再分類

コミット済み main `0fe61a4d2f384834d25112ab24f152a787e1ad6e` を起点とします。既存の作業ディレクトリの未コミット分類変更は取り込みません。

対象は読み・表記で重複を除いた332,902組です。

| 対象 | 組数 |
| --- | ---: |
| 固定判断の `unclassified` | 10,730 |
| 固定判断の `no_result` | 52,467 |
| 元の `held` 一覧にあり、固定判断にない候補 | 269,705 |
| 合計 | 332,902 |

元の保留一覧は `distribution-manifest.json` の `provenance.dispositionsSha256` と一致する保存済みファイルを使用します。既に分類済みの候補や明示的な除外候補を再評価する処理ではありません。対象に対応する元辞書レコードは、品詞・コストの異なるものを含め347,421行あります。

## 判断基準とモデル

分類判断は `gpt-5.6-luna`、推論強度 `max` に限定します。成功した判断は「採用してカテゴリを付ける」か「不採用」の二択です。一般語・専門用語・固有名詞で、表記全体に対する読みが妥当なものを既存28カテゴリへ分類します。参考情報も用いて妥当な語や人名を積極的に分類し、短さや使用頻度だけで除外しません。読み違い、不自然な断片、注記の混入など、IME候補としてふさわしくないものは具体的な理由付きで不採用にします。`term` は未分類語の受け皿にしません。

結果はAI暫定判断です。資料による独立した読み・カテゴリ確認を意味せず、分類元は既存の `manual`（assistant再分類・暫定）として記録します。読みや表記を推定で置き換えません。現行のTokenArrayで原表記を保存できない採用回答は、原回答を台帳に残したまま実効不採用にします。詳細な結果台帳は `build/luna-classification/ledger/results.jsonl.gz` にローカル保存し、Gitへ追加しません。

試行200組をこの基準で再判定した結果は、採用110組・不採用90組です。旧方針で保留にしたもののうち50組を採用しました。全件処理の進捗は次のコマンドで確認します。この試行件数は全件完了の報告ではありません。

結果の `policy_version` は `ime-adopt-reject-v1` です。旧方針の回答をそのまま不採用へ変換せず、Luna Maxで再判定します。旧方針の回答は `build/luna-classification/previous-hold-policy/` に分離し、完了件数に含めません。入力の `held` や `unclassified` は元の判断状態を示す履歴であり、新しい判断結果ではありません。

## 実行・再開

最初の抽出は、元の保留一覧のハッシュが一致する場合だけ実行できます。既存の同一スナップショットは再利用します。抽出後は、保存された対象・元の固定判断・元の配布候補から作業を再開できます。

```sh
python3 scripts/luna_reclassification.py export \
  --revision 0fe61a4d2f384834d25112ab24f152a787e1ad6e \
  --dispositions /path/to/candidate-dispositions.tsv.gz
python3 scripts/luna_reclassification.py batches --batch-size 200
python3 scripts/run_luna_classification.py --workers 3 --batch-size 50 --finish
python3 scripts/run_luna_classification.py --status
```

モデル実行はCodex CLIのサブプロセスを最大3つ使用します。各要求は200組以内で、完了済みの候補IDを送信対象から除きます。要求、構造化回答のスキーマ、応答、CLI実行条件、ハッシュ、SQLite進捗は `build/luna-classification/` に保存します。モデルや推論強度を別の値へ自動変更しません。

IDの欠落・重複・未知ID・不正カテゴリを含む回答は、そのバッチ全体を取得失敗として記録します。取得失敗から語の不採用判断を生成しません。失敗したバッチは最大3回まで試行し、使用量上限・モデル利用不可などは全体を停止します。同じ実行コマンドで、保存済みの判定を残して未完了分を再開できます。

## 反映と検証

全対象の有効な回答が揃うまで、本番反映は拒否します。途中の検査は読み取り専用のdry-runで行います。

```sh
python3 scripts/luna_reclassification.py apply \
  --results build/luna-classification/results --dry-run --allow-partial
```

`--finish` は、分類処理が成功してから、全対象の回答が揃った場合だけ以下の反映・索引更新・専門辞書の重複再計算・一覧生成・ZIP検証・テストを実行します。分類と完了処理はこのコマンドで順番に実行してください。途中の取得失敗や未処理が残る場合は辞書を変更せず停止します。結果は `build/luna-classification/completion.json`、各段階のログは同じディレクトリに保存します。

各段階を個別に実行する場合:

```sh
python3 scripts/luna_reclassification.py apply \
  --results build/luna-classification/results
python3 scripts/classified_distribution.py verify
./gradlew exportExistingDictionaryInventory
python3 scripts/specialist_distribution.py freeze
python3 scripts/write_classified_dictionary_catalog.py
python3 scripts/write_classified_dictionary_catalog.py --check
./gradlew buildDictionaryDistributionManifest test check
```

採用したカテゴリへ元辞書のレコードを取り込み、左右品詞IDとコストの異なる元レコードも保持します。採用は固定判断の `classified`、不採用は `excluded` とし、理由と元の状態を台帳に保存します。全対象の判定が揃えば、対象に新しい保留・未分類は残しません。既存の分類済み判断は保持します。専門辞書は更新後の既存辞書索引に対して重複判定を再計算するため、その採用レコードに差分が生じる場合があります。新しい専門辞書の読み推定は行いません。

反映前に一時領域で検証し、更新時は復旧用バックアップを作成します。プロセスが強制終了してバックアップが残った場合は、他の反映処理が動いていないことを確認して復旧します。

```sh
python3 scripts/luna_reclassification.py recover
python3 scripts/classified_distribution.py verify
```

通常の検証とCIはAIを呼び出しません。ローカル台帳がある環境では、その件数・モデル条件・ハッシュ、元の判断との差分を検証します。台帳がない環境では、固定済み配布データとマニフェストを検証し、台帳監査をスキップしたことを表示します。カタログの `--check` もカテゴリ別一覧を照合し、不採用理由ページの照合をスキップします。不採用理由一覧の完全な再生成・照合と詳細な台帳監査にはローカル台帳が必要です。変換の確認は `しろ`・`しろい`・`しろくろ`・`しろあり` と、既存の「しろ＋医」回帰テストを含めます。簡易CLIやバイナリの読み戻し成功を、実アプリ全体の候補表示・順位の確認として扱いません。
