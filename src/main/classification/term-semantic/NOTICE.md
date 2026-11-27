# Taxonomy provenance / 分類定義の来歴

The 26 domain IDs/definitions and five tag IDs/definitions are adapted from
[PR #149 taxonomy.json at e0b4d030](https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/e0b4d0307be3d6a9e97bc2c82c5918f6c968f463/src/main/classification/term-domain-proposal/taxonomy.json).
The [upstream manifest](https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/e0b4d0307be3d6a9e97bc2c82c5918f6c968f463/src/main/classification/term-domain-proposal/manifest.json)
declares its classification annotations **CC BY-SA 4.0**, and credits
James William BREEN / Electronic Dictionary Research and Development Group.
That inherited notice is retained here:
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
[upstream reference notice](https://www.edrdg.org/edrdg/licence.html).

Changes to the inherited taxonomy: separate usage class from semantic domain,
clarify the general-domain boundary, add three explicit outcome categories, and
remove reference-derived confidence/method metadata. Existing assignment rows,
reference IDs, dictionary field/gloss evidence and trained classifiers are not
carried into the new classifier inputs.

New judgments have their own LLM execution provenance. This inherited taxonomy
notice does **not** mean JMdict was supplied to those models or used to derive
the new judgments. The runtime does not assign a new blanket license to source
dictionary records or claim that all source material has one license.

26分野・5タグの定義を継承した来歴と、今回の独立AI判定の来歴は区別する。
元の語・読み・品詞・コストには、リポジトリの `LICENSE-DATA.md` と
`src/main/resources/third-party/` に記録された各出典の条件・表示を維持する。
コードのMIT表示を辞書レコード全体へ適用しない。
