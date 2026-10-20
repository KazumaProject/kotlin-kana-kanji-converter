# 意味理解に基づく分類案 / Semantic classification proposal

この仕組みは辞書レコードを変更せず、読み・表記組にAI分類を付加する。本番辞書・JapaneseKeyboardの設定は変更しない。実行結果、使用量、監査結果は実行ディレクトリのレポートを参照する。この文書自体は実行成功や精度を証明しない。

This pipeline attaches semantic labels to reading/surface pairs without modifying dictionary records or production IME assets. Consult the run's reports for measured results; this document does not certify execution or accuracy.

## 分類 / Classification

`usage_class`はgeneral / technical / mixed / uncertain。意味分野は既存26カテゴリを継承し、5タグは独立判定する。分野が分かることと専門語であることは異なる。`primary_domain`は互換用の分野であり、使用領域を表さない。

`final_category`は26分野に加え、理解可能だが主分野を選べない`term_multidomain`、意味未特定の`term_unknown`、略語展開不明の`term_unresolved_abbreviation`を許す。後二者はLuna A/B、Reviewer、Sol裁定が必須。未特定語も最終カテゴリを持つが、意味を特定できたと報告しない。理解できる意味に既存分類が不足する場合は、Coordinatorが定義・境界・代表例を確認してtaxonomyを版上げする。カテゴリを追加する場合、入力・プロンプトのハッシュを更新し、既存結果の互換性を検証する。

Usage and domain are independent. Additional categories distinguish understood multiple senses from genuinely unresolved meanings. Unknown outcomes require independent A/B classification, review and Sol adjudication. A new semantic domain requires a versioned definition and boundary review; an undeclared ID cannot pass validation.

## 入力・来歴 / Input and provenance

ワーカー入力はstable_id・読み・表記を基本とし、旧分類・確信度・辞書由来ヒントを含めない。JMdict、JMnedict、Wikipedia等を取得・投入・教師利用しない。LLMの事前学習資料の不使用を保証するものではない。元辞書の来歴とライセンスは維持し、新AI注釈と旧注釈を混同しない。旧結果は新結果固定後の比較だけに利用する。

Workers receive identifiers, readings and surfaces, without legacy labels or source hints. No external dictionary datasets are retrieved or supplied. This restriction concerns the workflow, not an unverifiable claim about model pretraining. Original source notices remain applicable; new model annotations have separate provenance.

継承した分類定義の表示は [taxonomy NOTICE](../src/main/classification/term-semantic/NOTICE.md) に残す。exportにはtaxonomy、入力ハッシュ・モデル・プロンプト版・ファイルハッシュを持つmanifest、既存の元辞書の出典表示を含める。これは新AI判定をJMdict由来と表示したり、元辞書全体を一律に再ライセンスしたりするものではない。

A/B use separate contexts and prompts. `common.md` is mandatory for all roles. Runner-recorded model, prompt version, pass, batch and call evidence are authoritative; model-written self-identification is not execution evidence. Save concise reasons, not chains of thought. Same-model agreement is not ground truth.

## 運用 / Operation

The ledger CLI exposes `prepare`, `next`, `ingest`, `status`, `verify`, `report`, `compare`, `audit`, `acknowledge-anomaly`, `promote`, and `export`. The runtime adapter starts the logged-in Codex CLI with a Sol coordinator that must invoke the formal subagent tool. Each worker's actual model and parent relationship are checked against local Codex host metadata by `runtime attest`; a model's self-identification is insufficient. Never substitute heuristics when model execution is unavailable.

```sh
# Run these commands from the dedicated worktree. RUN must be outside the repository.
RUN=/Users/kazuma/.codex/term-semantic-runs/run-v1
python3 -m scripts.term_semantic prepare --run "$RUN" \
  --source src/main/classification/distribution-candidates.tsv.gz \
  --taxonomy src/main/classification/term-semantic/taxonomy.json \
  --prompts src/main/classification/term-semantic/prompts
python3 -m scripts.term_semantic.runtime run --run "$RUN" --phase pilot
python3 -m scripts.term_semantic status --run "$RUN"
python3 -m scripts.term_semantic verify --run "$RUN" --complete
python3 -m scripts.term_semantic report --run "$RUN"
python3 -m scripts.term_semantic.runtime usage --run "$RUN"

# After the pilot quality checks in the approved plan pass:
python3 -m scripts.term_semantic promote --run "$RUN"
python3 -m scripts.term_semantic.runtime run --run "$RUN" --phase full
python3 -m scripts.term_semantic verify --run "$RUN" --complete
python3 -m scripts.term_semantic export --run "$RUN" --output "$RUN/final-export"
python3 -m unittest discover -s scripts -p test_term_semantic.py -v
```

中断後は`prepare`を繰り返さず、同じrunで`status`と`runtime run`を使う。リース期限切れのジョブだけ再予約され、検証済み結果は再利用する。実行中の別Coordinatorを重複起動しない。各試行は固有のディレクトリへ出力する。元ソースまたは分類契約を変える場合は新しいrunとし、古い結果を上書きしない。

Resume with `status` and `runtime run`, not another `prepare`. The current host adapter requires the Codex state database containing actual thread model/source metadata (`state_5.sqlite`); if that interface changes, attestation fails visibly rather than guessing provenance. It uses the existing ChatGPT login, not API-key billing. Output directories must be new and external; exports refuse to overwrite existing files.

実行ディレクトリはリポジトリ外に置く。ソースSHA-256、プロンプト版、taxonomy、モデル、対象集合を固定する。中断時は同じrunの状態と既存出力を照合し、検証済み結果を再利用する。ソースが変わった場合は新しいrunにする。応答喪失後の厳密な一度だけの推論は保証せず、重複呼び出しを記録する。

Begin with 100 rows, then a 1,200-pair pilot (900 deterministic random pairs and 300 input-ambiguity pairs). Use 100-row batches, reducing only for output truncation or format failure. Do not select samples using old labels or frequency inferred from dictionary costs. After pilot checks, continue to the full input under the approved plan. Report random and ambiguity-enriched samples separately.

Luna A/B classify every pair independently. Reviewer examines disagreements, high-risk entries and a deterministic 10% agreement sample. Sol adjudicates unresolved cases and independently audits about 1% of the full input. The pilot additionally schedules 240 Sol audit entries (120 random, 120 stratified by new category/usage/agreement). Prior Sol judgments are reused. Failures found in a group require expanded review in a new version if an immutable accepted judgment must change. Unknown outcomes never become general merely to reduce an unknown rate. Above 20% unknown in a batch triggers a recorded Sol input/prompt/abandonment check, not a quota; `acknowledge-anomaly` requires evidence and a concrete note.

## 検証・費用 / Verification and usage

Validate IDs, complete coverage, unchanged reading/surface, schema, category/tag consistency, mandatory adjudication, resumability and deterministic merge. Export must preserve the full multiset of original records, including duplicate counts, POS IDs and costs. Tag views overlap and are not counted as the primary export multiset. Terminal unknown records remain in the primary export.

Report A/B agreement by axis, disagreements by domain, usage distribution, review counts, JSON errors, unresolved meanings and legacy changes. Without independently verified reference labels, do not call agreement or AI audit success an accuracy measurement. Human review is optional and does not block other work.

`report` writes `human-review.jsonl` for terminal unidentified meanings, `disagreements.jsonl` for paired A/B disagreements, and `audit-sample.jsonl` for the independent audit selection. These stay outside the repository. Known meanings with multiple domains are classified outcomes and are not automatically put in the human-review list.

取得できたトークン・料金だけを実測と呼ぶ。取得不可は取得不可とし、予測・残枠を分離する。API単価をCodexログインの実請求額とみなさない。初期の呼び出し・トークン目安は実測と照合し、キャッシュ入力を含む総量と未キャッシュ入力・出力を区別する。`runtime usage`は同じスレッドの累積値を重複加算せず保存する。全件予測はパイロット実測から別途算出する。認証・モデル利用不可・解消しない品質問題ではチェックポイントと具体的障害を残す。

Only measured usage is reported as measured. API list prices are not a Codex subscription bill. Authentication/model failures and unresolved quality blockers must remain visible. Completion requires a final category for every pair, all mandatory audits and full record-preservation verification; it does not mean every meaning is resolved.

## PR

Include only implementation, configuration, directly relevant tests and this usage guide. Keep classification runs, logs, reports, temporary scripts and screenshots outside the repository. Draft PR title/body must contain Japanese and English, identify the relationship to PR #149, and clearly separate completed work, unresolved outcomes and unverified claims. Do not merge or change production dictionaries.
