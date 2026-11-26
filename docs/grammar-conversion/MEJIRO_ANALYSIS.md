# メジロ式のソース調査

調査対象は [Plover_Mejiro 0c999c67cbeeec8f5763f8b10337683bd5be864e](https://github.com/JEEBIS27/Plover_Mejiro/tree/0c999c67cbeeec8f5763f8b10337683bd5be864e) と [Mejiro_Engine 7bcb453e11a02d2858615a53b37f9dc1ebbc8d0c](https://github.com/JEEBIS27/Mejiro_Engine/tree/7bcb453e11a02d2858615a53b37f9dc1ebbc8d0c)。両方の `src/ime.rs` は照合時点で同じ内容だった。

| 位置 | ソースで確認した機能 |
| --- | --- |
| 共通エンジン `src/ime.rs` の `analyze`、`Analysis`、`Segment`、`VerbInfo` | ストロークと事前状態から描画前の文字列と UTF-8 バイト範囲を返す。入力区分、文脈、動詞の活用種別・語幹境界・内部活用番号を取得できる。解析はセッションを変更しない。 |
| 共通エンジン `src/rules.rs` の `particle`、`translate_observed` | 先行文脈と入力に応じて助詞出力を変更する。助詞や動詞を出力した入力分岐を観測して文法情報を付与する。文字列末尾から一律に品詞を推論する仕組みは確認できなかった。 |
| 共通エンジン `src/session.rs`、`src/lib.rs` の `Context` | 直前の出力に対応する文脈を管理し、ホスト辞書によるリテラル上書きは文法不明として扱う。 |
| Plover `Mejiro/ime.py`、`docs/rust-engine.md`、README のタイピングモード | Plover の履歴、辞書、出力、IME切替をアダプターで扱う経路を確認。ホスト IME に未確定かなを入力する機能と、Rust の構造化解析 API は別々に確認した。 |

確認したソースには、日本語 IME の N-best に対して POS 絞り込みを実行する接続、または「以外な」の全経路を除外するテストや実装は見つからなかった。構造情報を IME が受け取り制約をかけられることは設計上の可能性であり、実装の確認とは区別する。

Plover の `LICENSE` は GPL v3 本文、`setup.cfg` と Rust の `Cargo.toml` は GPL-3.0-or-later を表記する。引用したのはソース位置と確認した機能の要約。実装の由来は [由来記録](IMPLEMENTATION_PROVENANCE.md) を参照。
