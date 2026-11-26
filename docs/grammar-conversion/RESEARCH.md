# 文法情報付きかな漢字変換の調査

通常の変換は既存の辞書・スコアと公開 API を使う。文法情報を扱う場合は、語や隣接語について利用者が知っている条件を明示する。例えば「いがいな」の「な」を形容動詞の連体形と指定した場合、終助詞などの同音トークンと名詞に接続する経路を除外できる。

| 調査範囲 | 主な確認事項 |
| --- | --- |
| [現行実装](CURRENT_IMPLEMENTATION.md) | 変更前の JVM、使用した辞書資産、確定した品詞とコスト |
| [メジロ式](MEJIRO_ANALYSIS.md) | 入力時に観測した文法情報の公開、変換候補の除外に関する実装確認範囲 |
| [Mozc](MOZC_ANALYSIS.md) | 文脈 ID の方向と連接データ、形態情報の粒度 |
| [日本語文法](JAPANESE_GRAMMAR.md) | 活用生成、助詞、辞書間で異なる分類 |
| [探索方式](ALGORITHM_COMPARISON.md) | 一経路の最小コスト、N-best、相関する制約の状態 |
| [設計](ARCHITECTURE.md)・[API](API_SPECIFICATION.md) | JVM 上の実装と再現コマンド |
| [テスト](TEST_RESULTS.md)・[性能](BENCHMARK_RESULTS.md) | 検証結果、実行環境、測定の読み方 |
| [ライセンス](LICENSE_AUDIT.md)・[由来](IMPLEMENTATION_PROVENANCE.md)・[特許](PATENT_RESEARCH.md) | 参照元と実装範囲 |
