# 分類辞書の生成と配布

既存の Web・Person・Place・Neologd・wiki の5辞書は、28種類の意味カテゴリ辞書へ置き換えます。追加の漢方・医療2カテゴリを合わせ、計30カテゴリを配布します。[専門辞書の入力と条件](specialist-dictionaries.md) を参照してください。元の5辞書のテキストは、分類結果との照合と品詞・コストの復元に使用します。

## 固定入力

`src/main/classification/categories.json` が分類の定義です。`distribution-decisions.tsv.gz` は読み・表記ごとの最終分類、分類元、収録状態を保存します。分類取得失敗は `no_result` として未分類と区別し、バイナリには収録しません。`distribution-candidates.tsv.gz` はカテゴリ・読み・左品詞ID・右品詞ID・コスト・表記の6列で、元辞書のレコードを保持します。いずれもUTF-8、ヘッダーなしです。

分類の優先順位は、資料で確認した分類、assistantによる4,901件の再分類、保存済みのGemini成功結果の順です。確認済みの分類は、元の採用証明書に加えて、保存済みレビューでカテゴリと独立した読みの両方が確認された候補を含みます。Gemini履歴には最新の保存済み成功結果を使用し、Qwenの結果は使用しません。再分類結果の未分類指定は、その候補のGemini分類を取り消します。明示的な除外指定は分類元にかかわらず収録しません。

分類済みの暫定候補も収録しています。分類の確度や読みの確認状態を一律に保証するデータではありません。出典別件数とハッシュは `distribution-manifest.json` に保存しています。固定時点の収録件数はマニフェストに記録します。同じレコードはカテゴリ内で重複排除し、同じ読み・表記でも品詞やコストの異なる元レコードは保持します。

元辞書、分類ファイル、`id.def` の変更は検証エラーになります。更新時は保存済みの分類結果を再確認して固定入力を作り直します。ActionsがAIや外部の分類資料を取得し直すことはありません。

```sh
python3 scripts/classified_distribution.py freeze \
  --accepted /path/to/accepted-candidates.tsv.gz \
  --dispositions /path/to/candidate-dispositions.tsv.gz \
  --database /path/to/ai-run.sqlite3 \
  --manual /path/to/classifications.jsonl \
  --taxonomy /path/to/categories.json
python3 scripts/classified_distribution.py verify
python3 -m unittest discover -s scripts -p 'test_classified_distribution.py' -v
./gradlew buildDictionaryDistributionManifest test check
```

freezeはSQLiteを読み取り専用の一つのトランザクションで読み、進捗DBや元の分類結果を更新しません。Gitに保存するのは固定した圧縮データ、マニフェスト、必要なコードだけです。

## 一般語の追加

辞書原資料にない一般語は `src/main/classification/term-additions.tsv` に1行ずつ追加します。列は読み・左品詞ID・右品詞ID・コスト・表記・出典URL・確認日（YYYY-MM-DD）です。各行は独立した読みと表記が確認できる辞書・語彙資料を出典にし、配布時は一般語・専門用語の `term` カテゴリへ収録します。品詞とコストはMozc形式で指定します。

```text
どぱがき	1851	1851	8400	ドパガキ	https://example.org/dictionary-entry	2026-10-15
```

`freeze` はこの入力を出典確認済みの `term` 分類として取り込みます。重複行、無効な品詞ID・URL・日付、既存の別分類や除外判断との衝突は拒否します。出典URLと確認日は入力ファイルのハッシュとともに記録されます。

## 公式資料で確認した人名の追加

`src/main/classification/person-additions/` に、確認済みの名簿をUTF-8 JSONLで保存します。各行に `reading`、`surface`、`sport`（`mma`・`kickboxing`・`boxing`）、`left_id`、`right_id`、`cost`、`source_url`、`source_surface`、`source_reading`、`checked_on`（YYYY-MM-DD）を記録します。今回の名簿には、確認したページのSHA-256と確認箇所も保存しています。ページ本文はGitへ保存せず、出典は各行のURLで参照します。

読みは公式のカナ・ふりがなから、カタカナをひらがなへ変換して空白・中黒・引用符（“”「」）を除去します。長音は保持します。外国人名は公式日本語カタカナ表記を使い、英字名から読みを推定しません。表記は公式名・リングネームの姓名間の空白を除き、中黒などは保持します。競技の区分は名簿の整理用で、過去に別競技へ出場した選手も含みます。

```sh
python3 scripts/classified_distribution.py add-person-names \
  --entries src/main/classification/person-additions/fighters-2026-10-14.jsonl
python3 scripts/classified_distribution.py verify
python3 scripts/write_classified_dictionary_catalog.py
python3 scripts/write_classified_dictionary_catalog.py --check
./gradlew buildDictionaryDistributionManifest test check
```

取り込み前と、一時領域に作成した更新後の固定データを検証してから元人名辞書・固定データ・マニフェストを更新します。既存のperson収録は変更せず、既存の別分類・未分類・取得失敗・除外の判断と衝突する候補はエラーにします。分類判断自体がない既存の元辞書レコードは、公式資料で確認した場合に限り、元の品詞・コストを保持してpersonへ収録します。新しい元人名辞書レコードは左右品詞ID 1851（名詞,一般）・コスト8400です。同じ組に複数の元レコードがある場合、追加人数より配布レコードの増加数が多くなります。

新規判断の分類元は `verified` とし、元の分類履歴を保持したまま、名簿のハッシュ・新規の組・配布レコード数・元辞書への追加行数を `provenance.personAdditions` へ記録します。`verify` はその名簿と配布レコードの一致も確認し、外部サイトを取得しません。同じ名簿を再実行しても重複追加しません。後続の追加には別の名簿ファイルを使用します。`freeze` を改めて実行する場合は、その後に保存済みの追加名簿を取り込み直してください。

2026-10-14の名簿は490組（MMA 61組・キックボクシング91組・ボクシング338組）です。人数による上限を設けず、今回取得した[UFC](https://jp.ufc.com/athletes)、[K-1](https://www.k-1.co.jp/fighter)、[大橋ジム](https://www.ohashi-gym.com/boxers/)、[帝拳](https://www.teiken.com/profile/index.html)の公式資料で確認できた候補を収録しています。帝拳の戦績は「対戦相手」列のみを採用し、「試合会場」の地名を混入させません。姓だけ・愛称だけ・読み未確認の候補は追加していません。同じ選手の中黒位置違いである「シーサケット・ソールンビサイ」は重ねて収録せず、「シーサケット・ソー・ルンビサイ」の1表記を採用しました。「組」は読み・表記の件数であり、別表記を人数として数えるものではありません。

既存固定データとの差分は新規490組・492レコード、元人名辞書への追加は489行です。既存の収録レコードと分類判断の削除・変更はありません。品詞・コスト違いの2レコードを保持するため、配布レコードの増加数は組数より多くなります。全体は733,984組・767,766レコード、personは277,028レコードです。実IMEでの候補表示・順位は未確認です。

## 配布物

`release_zips/japanese_keyboard_dictionary_assets.zip` の各カテゴリは `app/src/main/assets/categories/<カテゴリID>/` に配置し、`yomi.dat.zip`、`tango.dat.zip`、`token.dat.zip` を格納します。内側ZIPには対応する `.dat` が1ファイル入ります。旧5辞書の15ファイルは含みません。他の辞書と共通の `pos_table.dat`、`connectionId.dat.zip`、`id.def` は同じ配布ZIPに含まれます。

共通品詞表は基本辞書・英語辞書・分類辞書の品詞組を含めて一度生成します。その品詞表から全バイナリを生成し、配布ZIPを再読込して、各カテゴリの読み・表記・品詞・コストと余分・欠落のないレコード数を照合します。

[収録一覧](classified-dictionary-catalog/index.md)では、全レコードの読み・表記・左右品詞ID・コスト・分類元をカテゴリ別に掲載します。品詞名は一覧内の対応表で確認できます。大きなカテゴリはGitHub上で閲覧できるサイズに分割します。一覧はリポジトリの文書として保存し、配布ZIPやRelease添付ファイルには含めません。`python3 scripts/write_classified_dictionary_catalog.py` で再生成し、`--check` で固定入力との一致を確認します。

既存Actionsを手動実行すると、ZIPと `dictionary-distribution-manifest.json`、`DICTIONARY-SHA256SUMS`、`DICTIONARY-LICENSES.txt` を成果物として取得できます。`v*` タグでは4ファイルをGitHubのプレリリースへ添付し、通常リリースのLatestには設定しません。最新5プレリリースを保持し、通常リリースとそのタグは削除対象に含めません。

利用側IMEは旧5辞書の固定パスを30カテゴリの読み込みへ変更する必要があります。辞書バイナリの読み戻し検証と、実IMEの候補表示・順位の検証は別です。

## 2026-10-14: うずまきボルトの修正

ユーザー確認に基づき、読み「うずまきぼると」、表記「うずまきボルト」を character に登録します（左右品詞1851、コスト8400）。先に報告された「うずまき → UZUMAKI／うず巻／淋蒔」は除外します。判断は `src/main/classification/reviews/` に保存し、`python3 scripts/classified_distribution.py apply-reviews --commit` で固定データへ反映します。`freeze` でも判断履歴を再適用します。

この変更の確認範囲は固定辞書データです。実アプリの候補表示・順位や配布ZIPの更新は含みません。
