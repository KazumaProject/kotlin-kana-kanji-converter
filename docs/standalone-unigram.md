# 単体入力用 unigram 辞書

`src/main/ngram-standalone-unigram/preferences.ngram` に「しろ」「ごと」「したい」「はいる」「みた」「なにか」「なら」「なのか」の8語を登録します。既存の各ノード用 unigram（v4）とは別の、入力全体用の辞書です。通常辞書の語・品詞・コストは変更しません。

## 生成・配布

Mozc の資源を通常の手順で準備してから実行します。

```sh
./gradlew buildStandaloneUnigramDictionary
./gradlew --quiet convertCandidates --args='--count 5 しろ ごと したい はいる みた なにか なら なのか ばかなのかな しろい しろくろ しろあり こと しごと'
```

生成先は `src/main/resources/ngram/system_ngram_standalone_unigram.dat`、レポートは `build/reports/ngram/standalone-unigram-build.txt` です。配布タスクにも生成を接続し、ZIP 内の `app/src/main/assets/ngram/system_ngram_standalone_unigram.dat` に追加します。既存の `system_ngram_unigram.dat` は置き換えません。生成済みバイナリは既存辞書と同様に Git 管理外です。

## 照合の契約

`PackedStandaloneUnigramDictionary.matches(input, path)` に、元の入力文字列と BOS/EOS を除いた**候補全体の経路**を渡します。次のすべてを満たす場合に優先対象です。

- 入力が空でなく、辞書に含まれる。
- 経路がちょうど1ノードである。
- ノードの開始位置が0で、長さが入力全体の長さと等しい。
- ノードの読み（`key`）と表記（`tango`）が両方とも元の入力に等しい。

これにより「しろ」単体は対象ですが、「しろ＋医」「しろ＋黒」「しろ＋蟻」「し＋ごと」は対象になりません。「こと」入力から生成される「ごと」も対象になりません。「なのか」単体は対象ですが、「ばかなのかな」の経路内にある「なのか」は対象になりません。現仕様は読みと表記が同じひらがな候補用です。異なる読みから漢字表記を優先する辞書としては使用しません。

同じ候補表記について、安い複数ノード経路が先に見つかり、後から条件を満たす1ノード経路が見つかる場合があります（手元の生成辞書の「はいる」「みた」で確認）。v5 では後者の経路を見つけた時点で既存候補に優先フラグを付け、先に保持したコストを維持します。表記は重複させません。v3/v4 の一致判定は引き続き最初に保持した経路だけで行います。

探索候補数は既存の上限を利用します。登録のない入力は単体用辞書による探索拡張を行いません。辞書は候補を新規作成しないため、条件を満たす1ノード経路が通常辞書に存在し、探索で列挙される必要があります。`nBestPath` と CLI の再順位付けに適用し、`convert` / `viterbiAlgorithm` の最小コスト経路選択には適用しません。

## バイナリと JapaneseKeyboard 側の対応

ヘッダーのバージョンを **5** にします。レコードと圧縮形式は v4 と共通で、1語のリテラルルールのみ許可します。違いは上記の照合契約です。このリポジトリの v3/v4 用リーダーは v5 を拒否し、単体用リーダーも v3/v4 を拒否します。

辞書バイナリ自体は利用側の照合範囲を強制できません。JapaneseKeyboard でこの仕様を使うには、別アセットのロード、元の入力と候補全体を渡す照合、v5 の重複候補処理を利用側にも実装する必要があります。v4 としてロードしたり、既存の各ノード用照合へ渡したりしないでください。

今回の変更対象はこのリポジトリだけです。JapaneseKeyboard の実際の checkout・リビジョン・実行経路・アセットハッシュとの照合、および実アプリでの動作は未確認です。配布 ZIP 全体の生成・検証も今回の単体辞書テストとは別です。

## 検証

```sh
./gradlew buildStandaloneUnigramDictionary test \
  --tests '*StandaloneUnigramTest' \
  --tests '*FindPathUnigramScopeTest' \
  --tests '*SystemNgramBinaryTest' \
  --tests '*SystemNgramRuntimeTest'
```

バイナリの再現性・8語の一致・バージョンの相互拒否、合成グラフでの「しろ＋医」等の除外と重複候補処理を検証します。ローカルの生成済み通常辞書を使ったエンジンテストでは8語の優先と、複合入力の候補順を単体用辞書なしの場合と比較します（候補数1・4・10）。この比較はここで実行した簡易エンジンの範囲の検証です。
