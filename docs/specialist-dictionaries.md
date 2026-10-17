# 漢方・医療の追加辞書

PR #128 の head `8ec94757d48d58ac6a5ca2c3baccfcbb48d45003` の28カテゴリを維持し、`kampo`（漢方・生薬）と `medical`（医療）を追加します。[検証結果と無料APIの処理範囲](specialist-dictionaries-validation.md) を参照してください。採用・除外・保留の確定件数とハッシュは `src/main/specialist/distribution-manifest.json` を参照してください。

| 入力 | 版・内容 | 条件 |
|---|---|---|
| [KNApSAcK KAMPO](https://dbarchive.biosciencedbc.jp/jp/knapsack-kampo/desc.html) | core・syoyaku CSV、取得ZIPのSHA-256で固定 | [CC BY-SA 2.1 日本](https://dbarchive.biosciencedbc.jp/jp/knapsack-kampo/lic.html) |
| [万病辞書](https://sociocom.naist.jp/manbyou-dic/) | MANBYO_202106 / MANBYO_20210602.csv | CC BY 4.0 |
| [百薬辞書](https://sociocom.naist.jp/hyakuyaku-dic/) | HYAKUYAKU_202107 / HYAKUYAKU_20210706.csv | CC BY 4.0 |

`src/main/specialist/sources.json` に版、URL、ZIPハッシュ、列名、文字コード、出典を保存します。`sources/*.jsonl.gz` は原表記・原読み・CSV行番号だけのスナップショットです。引用符を含むCSVはCSVパーサーで読み、行番号はヘッダーを1とする論理レコード番号です。ICDコード、標準病名、一般名、頻度は抽出しません。

## 読みの扱い

提供元の読みには自動付与が含まれます。全件の読みの正確性は確認していません。万病辞書の空欄・プレースホルダーのうち、既存辞書や提供元に読み付き表記がないものには、明示的に実行したGeminiの推定読みを使用します。既存表記に読みがある空欄行は、この初版の補完対象にしません。

個別に根拠を確認した読み訂正は `reading-corrections.json` に記録します。訂正は出典・論理行番号・原読み・表記が原本とすべて一致した場合だけ適用し、出典URLと訂正前後の読みをprovenanceに保存します。現在の訂正対象は「巨舌」「疣痔」「胆砂」「錯乱」です。原本スナップショットは変更しません。

Geminiの結果は `gemini-readings.jsonl.gz` に別保存します。原本の空欄はそのまま保持し、原本行・表記・モデル・要求/応答SHA-256・推定未確認の状態・参考読みを保存します。入力IDとの対応、かなだけの読み、表記のカナ部分、同じCC BYの医療資料の部分語の読みとの整合性を検査します。この検査は独立資料による全件の正読確認ではありません。不一致・不明・取得失敗は保留し、候補には入りません。収録一覧では提供元読み、推定読み、出典確認済みの読み訂正を区別します。

取得処理は確認済みのFreeプロジェクトのキーのみ使用します。課金の有効化、Paidへの切替、Batch APIによる有料処理は行いません。HTTPエラー・不正応答で停止し、既に送信した行を自動再送しません。無料枠上限で止まった分は保留です。APIキー、SQLite進捗、要求・応答の原本はGitに保存しません。

## 選択と保存

読みは外側の空白除去・NFKC・カタカナからひらがなへの変換、表記は外側の空白除去・NFCのみです。表記の内部空白、英字の大小、幅、異体字は保持します。品詞・コストに関係なく正規化した読み＋復元表記で既存辞書と照合します。異なる読み・表記は別候補です。漢方を先に採用し、医療の重複を除外します。複数出典は `provenance.jsonl.gz` の全原本行で追跡できます。

索引は `BaselineDictionaryInputs` が生成処理と共有する実際の選択結果です。基本辞書・コード追加語・ATOK追加語・英語・単漢字・絵文字/顔文字/記号・読み補正・ことわざ・既存28カテゴリを含み、n-gram優先ルールは含みません。現在のバイナリでかな表記は読みから復元されるため、その復元と原表記が一致しない新規候補は保留します。既存表記のNFCとtrie挿入文字が不一致の場合の現行復元も索引で反映し、配布ZIPと照合します。既存レコードは変更しません。

採用TSVはカテゴリ・読み・左品詞ID・右品詞ID・コスト・表記の6列です。`id.def` の `名詞,一般,*,*,*,*,*` に対応するIDを使い、コストは9000です。頻度調整は行いません。

## 更新と検証

通常のビルドとCIは保存済みデータのみ使います。取得・推定・固定はそれぞれ明示的な更新操作です。

```sh
python3 scripts/specialist_distribution.py fetch
./gradlew exportExistingDictionaryInventory
# Freeのプロジェクトとモデル上限をAI Studioで確認したときのみ実行:
python3 scripts/supplement_gemini_readings.py --free-proof /path/to/verified-free-proof.json
python3 scripts/specialist_distribution.py freeze
python3 scripts/specialist_distribution.py verify
python3 scripts/write_classified_dictionary_catalog.py
python3 -m unittest discover -s scripts -p 'test_*.py'
./gradlew buildDictionaryDistributionManifest test check
```

マニフェストは入力・出典文書・補完・読み訂正・既存索引・id.def・採用出力のハッシュと採用規則を固定します。検証は保存済み原本から再計算し、古い索引・入力改変・出力や件数の改変を検出します。配布ZIPを読み戻し、全30カテゴリの読み・復元表記・品詞・コスト・件数と、新規対既存/新規間の共通集合が空であることを検査します。

配布先は `categories/<ID>/` 内の3つの辞書ZIPです。ライセンス全文・出典・加工表示は別添 `DICTIONARY-LICENSES.txt` にまとめ、Actions成果物・Release添付・SHA-256一覧へ追加します。漢方には継承条件が適用され、医療にはCC BY 4.0が適用されます。利用側IMEの登録、実アプリの候補表示・順位はこの検証の対象外です。
