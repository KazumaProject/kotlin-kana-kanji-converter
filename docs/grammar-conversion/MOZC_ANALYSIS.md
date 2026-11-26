# Mozc の文脈 ID と探索

[google/mozc 04d909a1a4a3fc59769a53697ceac67e68606681](https://github.com/google/mozc/tree/04d909a1a4a3fc59769a53697ceac67e68606681) を参照した。この版の `src/data/dictionary_oss/id.def` は試験に使ったローカルファイルと SHA-256 が一致した。

- `src/data/dictionary_oss/id.def` は連続する文脈 ID と 7 項目ラベル。先頭4項目が品詞・細分類、次の2項目が活用型・活用形。末尾は文脈をさらに分けるラベルであり、汎用 ID では `*`。辞書レコードの基本形を求める用途に使えない。
- `dictionary00.txt` から `dictionary09.txt` は読み・lid・rid・単語コスト・表記を持つ。例えば同じ動詞でも `書く`、`書い`、`書け` などは異なる読み・表記と活用形の投稿として格納される。`README.md` は参照レコードの ID を継承する辞書追加方式も説明する。
- `src/data_manager/gen_connection_data.py` の `ParseConnectionFile` は単列費用を rid 行・lid 列に復元し、特殊な POS 領域に無効値を設定する。`BuildBinaryData` が圧縮と量子化を行う。公開ジェネレーターから学習元の全手順は確定できない。
- `src/converter/connector.cc` の `GetTransitionCost` はコストを得る。`kInvalidCost` を量子化した有限費用と区別する。一方、この Kotlin リポジトリの `ConnectionMatrix` は raw の Short 費用を返す。有限の費用を閾値で一律に禁止せず、明示規則で接続を拒否する。
- `src/converter/segmenter.cc` の `IsBoundary` は文節境界を扱う。`immutable_converter.cc` の Viterbi は `GetTransitionCost(lnode.rid, rnode.lid)` を使用し、`nbest_generator.cc` の `GetTransitionCost` も同じ方向で候補を探索する。本リポジトリの単語境界制約は文節セグメンテーションと独立。
- 左右 ID の異なるエントリーを単一の品詞に潰さない。本実装の自己トークン制約はラベルが両側で満たされることを要する。左隣はその rid、右隣はその lid を使う。接続が可能と推定できても、格関係や文の意図まで決まらない。

コードと辞書のライセンスは [LICENSE_AUDIT.md](LICENSE_AUDIT.md) を参照。
