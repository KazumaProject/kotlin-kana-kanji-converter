# JVM API と研究 CLI

通常変換の `nBestPath`、`convert`、`viterbiAlgorithm` は従来の API を使う。詳細情報や文法を利用する場合は、辞書をロードしたエンジンで文法セッションを開く。

```kotlin
val grammar = engine.grammar(File("build/grammar/metadata.dat"))
val options = GrammarSearchOptions(
    constraints = listOf(GrammarConstraint.Span(3, 4, GrammarRole.ADJECTIVAL_ATTRIBUTIVE))
)
val result = grammar.convert("いがいな", 100, options)
check(result.candidates.any { it.value == "意外な" })
check(!grammar.containsCandidate("いがいな", "以外な", options))
```

- `Span(start, end, alternatives)` は UTF-16 の半開区間。ちょうど1トークンを要求する。条件の各フィールドは AND、スパンの解釈リストは OR。異なるスパンは AND で、範囲の重複は不正。隣接条件は前ノードの出口と次ノードの入口を指定する。
- `GrammarSelector` は POS 大分類、細分類、活用型、活用形、役割を任意に組み合わせられる。対象トークンの左右両方の文脈で満たす。形容動詞連体形は前ノードの出口に語幹役割が必要。
- `Boundary(position)` は指定位置を語境界にする。サロゲートペアの内側はエラー。
- `includeLattice` は生の辞書ノードと到達可能な状態から評価した接続を記録する。エッジの `fromState` と `toState` で同じ生ノードの解釈状態を区別できる。除外ノードと拒否辺は理由と制約番号を持つ。`NO_PATH_WITH_CONSTRAINTS` は指定条件下で EOS に達しなかったことを表す。
- `minimumCostPath` は規則優先前のコスト最小経路。`candidates` は規則優先後の順位。単語ごとの累積コストは Long の注釈で参照する。既存 `ConversionPathNode.cost` は Int に収め、EOS 費用は候補の別項目に格納する。
- `inflect(reading, form, surface)` は辞書から全範囲の基本形を取り、語彙と型の可能性を返す。`JapaneseInflection.generate` は明示した読み・表記・活用型に直接規則を適用する。
- `particleConnections(readings, previousRightId, followingLeftId?)` は指定読みの助詞・助動詞を照合する。`SUPPORTED`、`INCOMPATIBLE`、`UNCLASSIFIED`、根拠、期待する活用形と左右の連接コストを返す。

## コマンド例

既存の辞書資産と `id.def` を用意する。別ディレクトリを使う場合は、生成側に `-PgrammarResourceDirectory=...` / `-PmozcIdDefFile=...`、CLIに `--resources` / `--metadata` を渡す。

```sh
./gradlew --offline generateGrammarMetadata
./gradlew --offline -q grammarCandidates --args='legacy いがいな --count 100'
./gradlew --offline -q grammarCandidates --args='convert いがいな --penalty 1500 --compare'
./gradlew --offline -q grammarCandidates --args='convert いがいな --span 3:4:ADJECTIVAL_ATTRIBUTIVE --trace --compare --expect 意外な --exclude 以外な'
./gradlew --offline -q grammarCandidates --args='convert かかない --pos 0:2:動詞:五段・カ行イ音便:未然形 --expect 書かない'
./gradlew --offline -q grammarCandidates --args='context 1931'
./gradlew --offline -q grammarCandidates --args='inflect TE きる'
./gradlew --offline -q grammarCandidates --args='inflect NEGATIVE かえる --surface 帰る --class GODAN'
./gradlew --offline -q grammarCandidates --args='particles 1931 な に の --following 1851'
./gradlew --offline -q grammarCandidates --args='benchmark いがいな --iterations 300 --warmup 175 --span 3:4:ADJECTIVAL_ATTRIBUTIVE'
```

`--expect` は上位 N 件、`--exclude` は到達可能な全経路を検査する。`--trace` は可視化用ノードと枝、除外理由を JSON に含める。`--compare` は同じ N で従来の候補と比較する。CLI で表現できる条件は `--help`、相関する複数解釈は JVM API を参照。
