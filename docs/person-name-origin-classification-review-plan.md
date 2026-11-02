# 人名由来分類の段階レビュー / Person-name origin review

## 日本語

### 範囲と進捗

2026-11-02 の作業基準は `main` の `b9f3375a1cfb0ce5e56f4da622ecc4e983364581` です。添付 ZIP はリポジトリ外で検証しました。引き継ぎデータは267,652組・269,540元行で、既存データとの行フィンガープリントが一致しました。分類マッピングが扱う人名由来候補は225,704組です。行の照合完了は分類訂正の完了を意味しません。

今回の根拠付きレビューは26組です。うち24組は新しい由来カテゴリを採用し、2組（金勇帥、ヘームー）は保留しました。以前の6保留のうち5組は、追加資料と理由を記録して解除しました。分類マッピングと `person-dictionary-candidates.tsv.gz` では、対象24組のカテゴリ列を更新しました。読み、表記、品詞 ID、コスト、タグ、レコード数は変えていません。

残りの改善作業は次の個別キューに残します。

| キュー | 組数 | 引き継ぎ内の再解析 | 扱い |
| --- | ---: | ---: | --- |
| 日本由来 → 海外由来のAI候補 | 6,641 | 0 | AI候補。誤分類の確定数ではない |
| 未確認 → 海外由来のAI候補 | 8,908 | 0 | AI候補。誤分類の確定数ではない |
| 両用候補 | 227 | 227 | 項目ごとに両方の命名慣習と既存所属を確認 |
| 未解決候補 | 238 | 238 | 項目ごとに人名かどうか、型、由来根拠を調べる |
| 非人名候補 | 51 | 51 | 項目ごとに対象の実体と人名辞書からの除外根拠を調べる |

海外由来へ移す2つのAIキューには、この引き継ぎで再解析結果がありません。各JSONL.GZ行には読み・表記・候補キー・現在の固定分類・元行フィンガープリント・AI提案・再解析の有無・調査要件・採用条件があります。状態はすべて `pending_item_level_source_review` です。AI候補やキュー全体を誤分類数として数えず、各項目に独立した根拠が得られるまで分類を変更しません。

### 判定と変更のルール

- AIの推測や自信度だけでは分類を変更せず、保留も解除しません。新しい独立資料が対象の読み・表記と命名慣習を確認できた場合は、理由、URL、日付、変更前後の判定をレビュー台帳へ追記して解除できます。
- 読み、表記、品詞、コスト、タグは維持します。無関係なカテゴリ所属も維持し、誤分類と確認した由来カテゴリ所属だけを既存カテゴリへ変更します。
- 姓・名・姓名の型を訂正する根拠があれば、由来の採用可否と別々に記録し、既存のカテゴリで表現します。分類体系では表せない実例が確認された場合だけ、具体例と採用条件を付けてスキーマ変更を別案件にします。
- 両用・未解決・非人名キューの調査要件と採用条件は、各項目の行に記録します。曖昧という理由だけで一括して後回しにしません。
- 由来マッピングの `source_category_id` と候補キーは元の値を保ち、採用した行の `target_category_id` だけを更新します。レビュー台帳はマニフェストからSHA-256で検証されます。保留解除には新しい資料URLと解除理由が必要です。

### 再生成と検証

ワークキューのビルダーは、展開済みの引き継ぎ台帳を受け取ります。ZIP、全件のdry-run、展開JSONLはリポジトリに含めません。出力するのは項目単位で圧縮した作業一覧、少数の出典レビュー、マニフェストです。

根拠付きの分類訂正を辞書候補へ同期するには `python3 scripts/sync_person_name_origin_source_review.py` を実行します。この処理はレビュー済み行のカテゴリだけを変更し、無関係な同一表記のカテゴリ所属と他の全列を維持します。辞書アーティファクトのハッシュ、行数、変更組数、変更行数、保留数を分類マニフェストに記録します。

## English

### Scope and progress

The 2026-11-02 baseline is `main` at `b9f3375a1cfb0ce5e56f4da622ecc4e983364581`. The attached ZIPs were validated outside the repository. The handoff contains 267,652 pairs and 269,540 source rows, with source-row fingerprints matching the existing data. The fixed origin mapping covers 225,704 name-origin candidates. Matching source rows does not mean their classifications have been corrected.

This increment reviewed 26 cited pairs: 24 received a new origin category and two (金勇帥 and ヘームー) remain on hold. Five of the six earlier holds were released after recording new evidence and a reason. The mapping and `person-dictionary-candidates.tsv.gz` now change only the category column for those 24 pairs. Reading, surface, POS IDs, cost, tags, and record count are unchanged.

The remaining improvement work stays in these item-level queues:

| Queue | Pairs | Reanalysis in handoff | Treatment |
| --- | ---: | ---: | --- |
| AI candidates: Japanese origin → foreign origin | 6,641 | 0 | Proposals, not confirmed errors |
| AI candidates: unconfirmed → foreign origin | 8,908 | 0 | Proposals, not confirmed errors |
| Dual-use candidates | 227 | 227 | Review both naming conventions and each existing assignment per item |
| Unresolved candidates | 238 | 238 | Research personhood, name type, and origin evidence per item |
| Non-person candidates | 51 | 51 | Research the exact entity and evidence for removing its person-name assignment per item |

The handoff has no reanalysis results for either AI queue that proposes foreign origin. Each JSONL.GZ row records the reading, surface, candidate key, current fixed classification, source-row fingerprints, AI proposal, reanalysis presence, required investigation, and acceptance criteria. Every row remains `pending_item_level_source_review`. Do not count model proposals or a queue as confirmed errors, and do not change a classification without independent evidence for that exact form and naming convention.

### Decision and change rules

- Model guesses and confidence alone cannot change a classification or release a hold. A hold can be released when new independent sources resolve the issue; record the reason, URLs, date, and decision history in the review ledger.
- Preserve reading, surface, POS, cost, tags, and unrelated category assignments. Change only an origin assignment confirmed to be wrong, using an existing category.
- Record name-type corrections separately from the decision to accept an origin. Use the current taxonomy where it can express the correction. Open a separate schema change only when an evidenced case cannot be represented, with concrete examples and acceptance criteria.
- Store investigation requirements and acceptance criteria on every dual-use, unresolved, and non-person item. Ambiguity alone is not a reason to defer an entire group.
- Keep each mapping row's original `source_category_id` and candidate key. For accepted reviews, change only `target_category_id`. The manifest verifies the review ledger by SHA-256; releasing a hold requires a new source URL and an explanation.

### Regeneration and validation

The worklist builder reads the expanded handoff ledger. The ZIPs, full dry-run ledger, and expanded JSONL files stay outside Git. The repository contains compact item-level queues, the small source-review ledger, and their manifests.

Run `python3 scripts/sync_person_name_origin_source_review.py` to apply cited category corrections to the dictionary candidates. It changes only the category column for reviewed rows, preserving unrelated category assignments for the same form and every other field. The classification manifest records the dictionary artifact hash, row counts, changed pairs, changed rows, and held pairs.
