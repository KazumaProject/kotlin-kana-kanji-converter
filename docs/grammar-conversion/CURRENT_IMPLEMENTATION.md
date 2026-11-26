# 変更前の実装と辞書

ローカルの `dev` (`c25337a3`) から専用 worktree を切り、最新の `origin/main` (`2d33bf0ff8e13095c53cb3347c9cc2585c7786d4`) に fast-forward した。取得時点の origin に `dev` のブランチはなかった。

- `KanaKanjiEngine.kt` の公開 API は `nBestPath(String, Int): List<String>`、`convert(String): ConversionResult`、`viterbiAlgorithm(String): String`。追加辞書を同じラティスに合流する。`ConversionResult.kt` は最小コスト経路の既存ノード情報を公開する。
- `GraphBuilder.kt` は LOUDS の読み前方一致、`TokenArray.kt` の postings と左右 ID ペア、表記 trie を参照する。`Node.kt` はキー・表記・開始位置・読みの長さ・単語コスト・左右 ID を持つ。`Dictionary.kt` の原始レコードにも左右 ID と語コストがある。
- `FindPath.kt` の `buildViterbi` は終端位置順の DP。`backwardAStar` は BOS→EOS、`remainingCosts` は逆向きの最小残余コスト。連接は前ノードの rid と次ノードの lid。`convert` は文脈規則の優先順位付けを適用せず、N-best は完了経路の表記を重複排除し、規則照合済み表記を優先する。
- `SystemNgramBinary.kt` と `SystemNgramDictionary.kt` では v3 複数ノード、v4 経路内単一ノード、v5 入力全体と一致する単一ノードを区別する。v3/v4 は同表記の初回経路で評価、v5 は探索済みの後続経路から同表記を優先できる。`ConvertCandidates.kt` はローカル資産または指定された配布 ZIP の JVM 検証用。
- `MozcIdDef.kt` は定義の連番・重複・BOS/EOS を検証する。`generateIdDefConstants` は定数生成、`validateMozcIdDef`・`validateDictionaryIds`・`validateConnectionMatrix` は入力検証、`run` は辞書生成、`dictionaryBuildTest` は全体生成の統合検証。`docs/classified-dictionary-catalog/pos.md` は分類辞書で共用する ID の運用を記録する。
- `FindPathCostDirectionTest`、`FindPathBranchingTest`、`FindPathUnigramScopeTest`、`StandaloneUnigramTest`、`KanaKanjiEngineBasicConversionTest`、`AllCategoryConversionTest`、`DictionaryBuildIntegrationTest` が既存の関係するテスト。

## バイナリで確認した事実

`dictionary04.txt` の「意外」「以外」と `dictionary08.txt` の別の「以外」を実際の LOUDS/TokenArray からも確認した。下表のコストは該当する「な」の助動詞トークン（lid=rid=163、単語コスト0）への連接。163 は特殊・ダ、体言接続。

| 読み | 表記 | lid/rid | 単語コスト | id.def 分類 | →163 |
| --- | --- | --- | ---: | --- | ---: |
| いがい | 意外 | 1931/1931 | 3174 | 名詞・形容動詞語幹 | 647 |
| いがい | 以外 | 2163/2163 | 0 | 名詞・非自立・副詞可能 | 3498 |
| いがい | 以外 | 1851/1851 | 3340 | 名詞・一般 | 2666 |

「な」には助動詞 163（コスト0、1580）、終助詞421（97、2324）、特殊・ナイ197（0）、動詞757/1549（各5000）、形容詞2394（0）、感動詞2591（3482）の候補もある。「なら」の特殊・ダ仮定形は162で、各行からの連接は1931→162が3264、2163→162が2603。

`convertCandidates --args='--count 100 いがい いがいな いがいなら いがいの'` の上位を確認した。

| 読み | 1位 | 2位 | 3位 |
| --- | --- | --- | --- |
| いがい | 以外 | 意外 | 遺骸 |
| いがいな | 意外な | 以外な | 以外名 |
| いがいなら | 以外なら | 意外なら | 以外奈良 |
| いがいの | 以外の | 意外の | 遺骸の |

テストは手元にあった生成済み JVM 用資産を全方式で共用した。使用したファイルの SHA-256 は [テスト結果](TEST_RESULTS.md) に記録した。
