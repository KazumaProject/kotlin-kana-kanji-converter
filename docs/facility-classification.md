# 施設辞書の細分類

## 分類範囲と正本

施設分類の正本は `src/main/classification/facility-taxonomy.json` と `facility-classifications.tsv.gz` です。後者は採用済みの施設読み・表記ペアごとに、葉カテゴリ、分類方法、状態、規則ID、根拠、確認済みの場合のURLを保存します。`distribution-candidates.tsv.gz` の読み・表記・左右品詞ID・コストは分類処理で書き換えません。同じ読み・表記に複数の元レコードがある場合も、その各レコードを配布データに維持します。

16の大分類と全葉カテゴリの日本語名・定義はtaxonomyに記録しています。大分類は表示用の親で、配布対象は定義された葉カテゴリのみです。親カテゴリを葉として重複配布しません。`other`、`unknown`、`unclassified`、`review` は施設の配布カテゴリとして定義せず、すべての採用ペアに用途に最も近い葉を一つ割り当てます。

## 分類基準と境界

まず複数用途にまたがる名前語を優先順の固定規則で処理します。例として、大学病院・がんセンターは医療、小学校・高等学院は教育、美術館は文化、護国神社は宗教、ショッピングモール・珈琲店は商業、スキー場はスポーツ、発電所は産業、港・道路出入口・車両基地は交通、橋は土木、城・砦・古墳・歴史的住宅は遺産に分類します。「病院」を「寺院」、「車両基地」を軍事基地と誤認しないよう優先順位を固定しています。規則は `scripts/facility_classification.py` にID・根拠とともに記録し、施設語の末尾だけでは判定しません。

規則で一意に決められない既存採用ペアは、読みと表記をまとめてGemini 3.5 Flash-Liteの無料枠でbest-fit分類します。Geminiの個別ラベルは資料照合済みとはみなさず、固定TSVに `best_fit_not_independently_verified` と明記します。旅客駅・停留所、交通路線、組織、地名・自然地形、一般用語との境界候補には確認推奨状態と根拠を残します。元の採用・除外判断を分類だけを理由に変更しません。

複数の用途がある建物は名称で確認できる主用途を選びます。大学病院は大学名ではなく病院機能、店舗は運営企業ではなく個別の実店舗を優先します。チェーン企業・ブランドは `organization` または `product` に残し、実在する個別店舗は `facility/commercial/restaurant` にします。駅と鉄道設備を区別し、旅客駅・停留所は `station`、信号場・車両基地は施設内の鉄道設備に分類します。橋梁・ダムなどの構造物は `infrastructure`、道路・鉄道路線は `transport_route`、地名・自然地形は `place` を優先します。個別レビューでは、蕨市公式資料で寺院と確認した「三学院」、堺市公式資料で歴史的寺院と現在の町家歴史館公開を確認した「清学院」を用途別に分類しました。「教学院」は公式サイトが仏教学研究機関として説明していますが、組織と物理施設の境界を確認できないため研究施設への暫定best-fitとし、`organization` への移動候補として明示しています。

配布先の再確認を推奨するbest-fit境界ヒントは1,588組で、提案先は `term` 1,216組、`place` 280組、`station` 80組、`organization` 12組です。組織境界の12組は「大本本部」「旧参謀本部」「国際連合本部」「スミソニアン協会本部」「天神峰現地闘争本部」「登米市消防本部」「那比本社」「日向市消防本部」「香港天文台本部」「安来市消防本部」「養老町消防本部」「横浜銀行協会」です。これらはモデルの確認候補で、移動を確定したものではありません。個別レビュー済みの「教学院」も別に組織境界の要確認状態です。確認候補を含め、現状の施設採用語はすべて一つの葉カテゴリへ収録しています。

## 再生成と検証

分類再実行の作業領域と無料枠証明はリポジトリ外に置きます。作業用APIキーはローカルのKeychainから読み、ファイルやログには出しません。分類は同じ入力スナップショットと固定順で再開し、処理済みペアを再送しません。APIレート制限や形式不正時は処理を止め、未完了分を再開します。現在のdefault batch sizeは50です。

```sh
python3 scripts/run_facility_classification.py \
  --workspace "$HOME/.cache/kotlin-kana-kanji-converter/facility-gemini-classification-3-5-flash-lite" \
  --free-proof "$HOME/.cache/kotlin-kana-kanji-converter/facility-gemini-classification-3-5-flash-lite/free-tier-proof.json" \
  prepare
python3 scripts/run_facility_classification.py \
  --workspace "$HOME/.cache/kotlin-kana-kanji-converter/facility-gemini-classification-3-5-flash-lite" \
  --free-proof "$HOME/.cache/kotlin-kana-kanji-converter/facility-gemini-classification-3-5-flash-lite/free-tier-proof.json" \
  run --workers 1 --interval 4.2
python3 scripts/run_facility_classification.py \
  --workspace "$HOME/.cache/kotlin-kana-kanji-converter/facility-gemini-classification-3-5-flash-lite" \
  --free-proof "$HOME/.cache/kotlin-kana-kanji-converter/facility-gemini-classification-3-5-flash-lite/free-tier-proof.json" \
  finalize
python3 scripts/classified_distribution.py verify
python3 scripts/write_classified_dictionary_catalog.py --preserve-excluded-pages
python3 scripts/write_classified_dictionary_catalog.py --check
```

`facility-classifications-manifest.json` は入力ペアと元レコードのハッシュ、モデル・無料枠の実行情報、分類方法別・葉別件数を記録します。全件の一葉分類、重複ペア、元レコード保持、カテゴリ定義と配布スナップショットの一致を `verify` が検査します。Geminiによるbest-fitは無料枠を利用した分類であり、35,000件超すべての施設機能を個別の公的資料で再確認したことを意味しません。

カタログはMarkdownを編集せず、固定分類データから `scripts/write_classified_dictionary_catalog.py` で再生成します。生成物には葉カテゴリ別の読み・表記組数、レコード数、ページリンクを含めます。施設の親ページ `docs/classified-dictionary-catalog/facility/index.md` は新しい階層への案内です。この作業環境にはローカルのLuna監査台帳がないため、上記コマンドは既存の不採用理由ページを保持してカテゴリ一覧を再生成します。理由ページそのものの再生成・照合には台帳が必要です。

## ラーメン店の追加

新規の実店舗名は公式店舗案内を根拠とするレビュー行で追加し、`facility/commercial/restaurant` に収録します。チェーン名だけの語を店舗として複製しません。登録した表記と読み、店舗ページURL、確認内容は `src/main/classification/reviews/` に記録します。
