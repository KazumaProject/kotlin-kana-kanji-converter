# 新語候補 Issue のレビュー（2026-11-01）

対象：[#231](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/231)、[#240](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/240)、[#251](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/251)、[#256](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/256)、[#261](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/261)、[#268](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/268)、[#273](https://github.com/KazumaProject/kotlin-kana-kanji-converter/issues/273)。読みと標準表記を確認し、既存の配布候補との重複、用語の継続使用、かな入力から得られる表記上の利点を基準に採否を決めた。

## 採用

18組を出典付きで用語辞書へ追加する。個別の確認先と分類は [レビュー記録](../src/main/classification/reviews/2026-11-01-neologism-issues.jsonl) に記録した。

| Issue | 追加語 |
| --- | --- |
| #273 | ワークスロップ、GEO、能動的サイバー防御、オンチェーン金融 |
| #268 | SaMD、DTx |
| #261 | eKYC、JPKI、SLM |
| #256 | VLM、DeFi |
| #251 | AIスロップ、PQC、レアアース泥 |
| #240 | GX-ETS、ctDNA、MRD |
| #231 | POCUS |

## 重複・保留

- `ADC`（#273）、`DEX`（#256）、`AX`（#240）、`MASH`（#231）は、同じ読み・表記が配布候補にすでに存在するため追加しない。`MASH` は組織・人名カテゴリに収録済みで、出力表記もすでに変換できる。
- `AI TRiSM`（#251）は日本語での継続使用と用語の一般性がまだ狭い。`RWA`（#256）は金融・トークン化資産以外の意味と競合しやすく、日本語入力の需要を今回の根拠だけでは十分確認できない。どちらも保留。
- `JESTA`（#231）は制度化済みだが運用開始前の将来用語、`DePIN`（#231）は利用がWeb3・分散インフラ分野に偏るため今回は保留。

## 検証範囲

公開中の配布候補で読み・表記の完全一致と、4つの重複語の配布カテゴリを確認した。実際のJapaneseKeyboardチェックアウトでの文節探索、候補順位、学習・予測を含むアプリ全体の挙動はこのリポジトリの辞書データだけでは確認していない。
