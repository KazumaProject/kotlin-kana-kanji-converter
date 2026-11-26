# 検証結果

Apple M2 / macOS arm64 / JBR OpenJDK 17.0.12。比較元のコードは `2d33bf0ff8e13095c53cb3347c9cc2585c7786d4`。同じキャッシュ済み資産と辞書読込設定を使った。

## 通常変換と文法条件

187入力の top-1、top-10、top-100 の JSONL が、それぞれ変更前後で完全に一致した。次の SHA-256 は候補表記と順序を含む出力全体の値。行順は [corpus.txt](corpus.txt)。

| N | SHA-256 |
| ---: | --- |
| 1 | `bd5c222d57d762d1449bf741d11f0412c3c0fa7f9a4d4170469f3391765fdc11` |
| 10 | `fda0707178e1b322d034a9149402604183413e1d87f4b93ef8264f277e5c8bb5` |
| 100 | `cbe8919e34ae5ad1bb21fde5876f63ede1106a6a7f9c204d65b96efdee4a0c4a` |

```sh
for n in 1 10 100; do
  ./gradlew --offline --quiet convertCandidates \
    --args="--count $n $(paste -sd ' ' docs/grammar-conversion/corpus.txt)" > "/tmp/grammar-n$n.jsonl"
  shasum -a 256 "/tmp/grammar-n$n.jsonl"
done
```

- 制約のある「いがいな」では「意外な」が1位。経路費用5942は BOS→意外2121、意外3174、意外→な647、な0、な→EOS0。「以外な」は top-N に依存しない全ラティス検索でも不在だった。
- 「意外な結果」「意外なもの」「綺麗な」「静かな」「危険な」は制約下で到達可能。「食べるな」「行くな」「するな」の終助詞指定、「以外なら」の仮定形指定も各々の条件を満たした。
- 700個の小規模ラティスで、A* の表記ごとの最小コスト、Viterbi の最小値、制約下の空集合が全列挙と一致した。通常変換のテストには「しろ + 医」を含む。
- 活用形の辞書フィルターは「書かない」の語幹と助動詞の区間を検査。生成では「切って／着て」「帰らない／変えない」を保持した。単体テストは22語彙例×5形式に加え、不正な活用型を確認した。
- Kotlin/JVM の研究 CLI を `--offline` で実行し、辞書と文法データをローカルからロードした。macOS のサンドボックスでネットワークを拒否した JVM でも、同じ明示制約と存在・不存在の検査を通過した。

## 使用したローカル資産

| ファイル | SHA-256 |
| --- | --- |
| id.def | `07a05a268c3783b7e02b36e4aa591555a2dd19a1f3c93891576740761c154f2d` |
| connectionId.dat | `58609d76f536c44eea61c24d24c4a522e65f8392ef43995390e177ac8ed9d875` |
| pos_table.dat | `2aa09e7f5318cb7be2f7d88c4a4473987a480bbecce3269685f7696797ed9f48` |
| yomi.dat | `41e3e1948e12912c03506d8bc85a081bd370ec8b075413191bea03b70fe52a20` |
| tango.dat | `4407cd27e150e092cdf62257eaea6d0144ca426bfb83dedbda7691604647db69` |
| token.dat | `95740850f808634d9f19bec3f6befb4f4a082d3436e68c8dd3909c9dec4b8137` |
| ngram/system_ngram.dat | `8d47adb7934ea687cae8254760623a40de1e009d5a028bf8d2f377fd39b71a0b` |
| ngram/system_ngram_unigram.dat | `3619430157ec6b58f0d0801a7e73e9a7567e3d6aa6bb34ac53ad4f52da9b7480` |
| ngram/system_ngram_standalone_unigram.dat | `b3ccd95031ad8e32181a6d1e068acea9774a12dfb4f3f99cf93f41bfec52ab61` |

## 実行したテスト

- `./gradlew --offline generateGrammarMetadata test`。ルート186件成功、フル辞書生成1件は専用タスクで実行。English IME 50件成功。
- `./gradlew --offline check dictionaryBuildTest`。Python の37件とフル辞書生成を含む2件が成功。辞書生成の本計測は9.381秒、既存の上限11.484秒。
- 通常変換の「しろ」「しろい」「しろくろ」「しろあり」の候補列は上記3つの N で変更前後が一致した。
