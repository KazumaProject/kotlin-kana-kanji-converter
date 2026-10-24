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

施設辞書には個別に特定できる実店舗・建物を収録します。地域の店舗を調べた今回の補足では、全国チェーンの支店名ではなく、北海道・東北・関東・中部・近畿・中国・四国・九州・沖縄の観光協会・自治体等の店舗案内で実在と所在地を確認できた25店を選びました。これは地域別の追加例で、全ラーメン店を網羅する名鑑ではありません。店名から「本店」など支店固有の接尾辞を落とし、個別店舗名を `facility/commercial/restaurant` に収録します。各読み・表記、確認状態、根拠URLは `src/main/classification/reviews/2026-10-24-regional-ramen-shop-additions.jsonl` に固定します。読みを資料で確認できなかった場合は推定読みとして記録します。

| 地域 | 個別店舗名 | 店数 |
|---|---|---:|
| 北海道 | 生姜ラーメンみづの、ラーメンすがわら | 2 |
| 東北 | 味の札幌大西、出し屋五丈軒、くどうラーメン、まるかいラーメン | 4 |
| 関東 | 飯田商店、麺らいけん、ラーメン太七 | 3 |
| 中部 | 中華そばなかつぼ、まさごそば、つづみそば、宮川中華そば | 4 |
| 近畿 | 井出商店、本家アロチ丸髙中華そば、丸木中華そば | 3 |
| 中国 | 笠北、おっつぁん、麺屋晴レ | 3 |
| 四国 | 讃岐ラーメンはまんど、橋本食堂 | 2 |
| 九州 | 沖食堂、来福軒 | 2 |
| 沖縄 | ゆいまーる人、中華そば 月の灯り | 2 |
| **合計** |  | **25** |

新規ペアは24組で、既に `organization` に追加していた「飯田商店」は個別店舗として施設分類へ変更しました。「旭川三平本店」は観光協会の掲載で休業中と確認できたため追加していません。既に施設辞書にある「旭川ラーメン蜂屋」「坂内食堂」「とら食堂」などは重複追加していません。`元祖長浜屋` は元データで寺院に誤分類されていたため、福岡県公式観光情報を根拠に飲食施設へ訂正しました。施設以外のブランドは `organization` / `product` に残し、支店表記は追加しません。

既存の「博多一風堂」は施設ではなくブランド名であり、固定分類では神社へ誤分類されていたため、レビューで `organization` のみに修正します。「らあめん花月嵐」もチェーンブランドとして `organization` に移し、「新福菜館」はラーメン店の施設として `facility/commercial/restaurant` に修正します。検証処理は、施設として採用済みだったペアの明示的な移動を記録から認識し、施設の原本スナップショットと各辞書の配布先を別々に照合します。
