# スマホからの辞書改善

スマホのブラウザでGitHubにログインし、Issueフォームから送信します。

- [単語を追加する](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/new?template=dictionary-add.yml)
- [変換候補の問題を報告する](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/new?template=dictionary-report.yml)

フォームとワークフローをデフォルトブランチへマージすると利用できます。投稿内容は公開されます。自動処理するのは `KazumaProject` 本人が投稿し、本人が実行した申請だけです。

## スマホでの操作

1. 追加の場合は、基本形の読み・表記、追加先、品詞・活用種類を選択します。追加先はシステム辞書と全30カテゴリです。1件のIssueにつき1語を登録します。
2. 問題報告の場合は、実際に入力した読み全体と候補をそのまま記入します。辞書の版が分かればReleaseタグも記入してください。「除外する」は自動変更の申請、「調査・修正を依頼する」は調査待ちの報告になります。
3. Issueの自動コメントからPRを開き、変更する語・活用形・品詞・コストと検証結果を確認します。検証成功後にDraftが解除されます。
4. PRをマージすると修正履歴が保存され、次回の通常リリースで配布されます。アプリへの辞書インストール・更新は既存の手順を使います。

除外は **対象辞書・読み・表記の完全一致** です。読みの末尾を削ったり、英字の大小を同一視したりしません。例えば `りばーと → RIVERと` と `りばーと → Riverと` は別の申請です。この申請から `りばー → RIVER` や `りばー → River` は除外しません。指定した辞書に同じ読み・表記で品詞・コストの異なるレコードが複数ある場合は、その一致するレコードをすべて除外します。

収録先が分からない場合は「収録先を検索（完全一致）」を選択できます。システム辞書と30カテゴリの実際の生成入力から一致する収録先を列挙します。現在の入力に見つからない場合は調査待ちとし、別の読みを除外しません。読みから復元される表記と元の表記が異なる既存レコードも、自動除外の対象にしません。

## 動詞・形容詞

基本形と活用の種類を指定します。例えば `ぐぐる／ググる／動詞ラ行五段` を登録すると、固定したMozc規則から連用形などを展開します。ひとつの読み・表記に複数の品詞IDが必要な場合も保持し、PRに全レコードを表示します。

品詞・活用種類の選択肢は、固定した `user_pos.def` と `cforms.def`、実際の `id.def` から生成します。基本形の語尾が合わない申請、対応する品詞IDがない種類、現在のバイナリのかな表記復元と合わない語は自動登録しません。品詞の選択自体や語の意味・正しい読みを自動判定するものではありません。例外的な活用を含む場合は生成結果を確認し、対応しないものは調査・修正として報告してください。

新規レコードの標準コストは9000です。同じ追加先に既にある読み・表記は既存の品詞・コストを保持します。漢方・医療は既存辞書・他の専門カテゴリとの重複を許可しないため、重複する追加申請は調査待ちになります。ユーザーの申請は `user_confirmation` と記録し、独立資料で確認済みの語とは区別します。

## 履歴と再生成

`src/main/dictionary-feedback/requests/` に、Issue URL・本文ハッシュ・入力内容・元レコード・操作・生成レコードを追記保存します。28カテゴリへの変更は既存の `src/main/classification/reviews/` にもレビューを生成します。システム辞書は `system.json`、漢方・医療は保存済み原本に対する履歴の適用結果を使用します。元の上流辞書・専門辞書スナップショットは変更しません。

過去の履歴を編集・削除して変更を取り消さないでください。後続の申請で操作を記録します。同じIssue本文の再処理は追加を重複させません。未マージのIssueを編集した場合は、最新mainを基準に同じPRを再生成します。マージ済みの申請を編集して別の語を追加した場合、以前の登録は取り消されず、新しい履歴が追加されます。

複数のPRが同じ固定データを変更して競合した場合は、一方のマージ後、残りのIssueを更新するか、[Dictionary Issue feedback](https://github.com/KazumaProject/kotlin-kana-kanji-converter/actions/workflows/dictionary-feedback.yml) をIssue番号付きで再実行してください。手動コミットが加わったPRは自動で上書きしません。

ローカルから同じ処理を確認できます。

```sh
./gradlew exportFeedbackDictionaryInventory
python3 scripts/dictionary_feedback.py prepare \
  --issue /path/to/github-issue.json \
  --inventory build/dictionary-feedback/inventory.jsonl.gz
# build/dictionary-feedback/result.json の status が ready の場合:
python3 scripts/classified_distribution.py apply-reviews --commit
./gradlew exportExistingDictionaryInventory
python3 scripts/specialist_distribution.py freeze
python3 scripts/write_classified_dictionary_catalog.py
python3 scripts/dictionary_feedback.py verify
./gradlew buildDictionaryDistributionManifest test check
```

`--issue` はGitHub REST APIのIssueオブジェクトです。`number`・`html_url`・`user.login`・`state`・フォームのMarkdown `body` を検証します。Issue本文をシェルやコードとして実行する処理はありません。AI APIは使用しません。

## GitHub Actionsの設定

リポジトリの **Settings → Actions → General → Workflow permissions** で、GitHub ActionsによるPR作成が許可されている必要があります。管理ポリシーで禁止されている場合、ワークフローはAPIの失敗として停止します。個人アクセストークンの登録は不要で、ワークフローの `GITHUB_TOKEN` に `contents`・`issues`・`pull-requests`・`statuses` の書き込み権限を宣言しています。

PRを作成するワークフロー自身が生成コミットの検証を実行し、`dictionary-feedback/verification` の状態を記録します。自動作成PRに対する別ワークフローの起動には依存しません。Issueが処理中に編集された場合は成功扱いにせず、古い変更案をDraftのまま残します。

通常リリースとIssue処理は、共通の `dictionary-inputs` Actionから同じ固定Mozcリビジョンを取得します。活用規則・`id.def` のSHA-256は `src/main/dictionary-feedback/mozc/source.json` に保存しています。Mozcの更新時はこの固定情報と規則を合わせて再確認し、`python3 scripts/dictionary_feedback.py forms` でフォームを再生成してください。日本語コーパスの英語辞書は従来どおり、同一の最新公開Releaseから取得・ハッシュ検証します。

検証するのは辞書入力、固定データ、配布ZIPの読み・復元表記・品詞・コスト・件数、重複とハッシュです。スマホで利用中の配布版や実アプリの候補順位は、この検証だけでは確認できません。
