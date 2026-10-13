# 分類辞書の生成と配布

既存の Web・Person・Place・Neologd・wiki の5辞書は、28種類の意味カテゴリ辞書へ置き換えます。元の5辞書のテキストは、分類結果との照合と品詞・コストの復元に使用します。

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

## 配布物

`release_zips/japanese_keyboard_dictionary_assets.zip` の各カテゴリは `app/src/main/assets/categories/<カテゴリID>/` に配置し、`yomi.dat.zip`、`tango.dat.zip`、`token.dat.zip` を格納します。内側ZIPには対応する `.dat` が1ファイル入ります。旧5辞書の15ファイルは含みません。他の辞書と共通の `pos_table.dat`、`connectionId.dat.zip`、`id.def` は同じ配布ZIPに含まれます。

共通品詞表は基本辞書・英語辞書・分類辞書の品詞組を含めて一度生成します。その品詞表から全バイナリを生成し、配布ZIPを再読込して、各カテゴリの読み・表記・品詞・コストと余分・欠落のないレコード数を照合します。

既存Actionsを手動実行すると、ZIPと `dictionary-distribution-manifest.json`、`DICTIONARY-SHA256SUMS` を成果物として取得できます。`v*` タグでは3ファイルをGitHub Releaseへ添付します。タグ公開は従来の最新5リリース保持処理も実行します。

利用側IMEは旧5辞書の固定パスを28カテゴリの読み込みへ変更する必要があります。辞書バイナリの読み戻し検証と、実IMEの候補表示・順位の検証は別です。
