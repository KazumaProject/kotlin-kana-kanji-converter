# ライセンス監査

新規 Kotlin 実装と自作テストはリポジトリの [MIT](../../LICENSE)。既存の [LICENSE-DATA.md](../../LICENSE-DATA.md)、[THIRD-PARTY-NOTICES.md](../../src/main/resources/THIRD-PARTY-NOTICES.md) と [辞書の第三者表記](../../src/main/resources/third-party/LICENSE-DATA.md) が既存資産に適用される。CC BY-SA 等の条件は維持される。新しい KKG1 は既存 `id.def` のラベルを含む生成物で、配布する場合は使用した `id.def` の由来と辞書条件を添える。

| 参照元・版 | コードとデータの条件 | 成果物への取り込み |
| --- | --- | --- |
| [Plover_Mejiro 0c999c6](https://github.com/JEEBIS27/Plover_Mejiro/tree/0c999c67cbeeec8f5763f8b10337683bd5be864e)・[Mejiro_Engine 7bcb453](https://github.com/JEEBIS27/Mejiro_Engine/tree/7bcb453e11a02d2858615a53b37f9dc1ebbc8d0c) | GPL v3 本文、パッケージの宣言は GPL-3.0-or-later | ソース参照位置と機能の要約。コード、データ、規則表、テスト、バイナリは収録していない。 |
| [Mozc 04d909a](https://github.com/google/mozc/tree/04d909a1a4a3fc59769a53697ceac67e68606681) | コードは BSD 3-Clause。辞書は Mozc、NAIST/IPADIC、ICOT 等の既存表記に従う。 | 既に入力資産として使われる `id.def` を別形式で生成し、既存の辞書を読む。新規の外部レコードやコードの取り込みはない。 |
| [MeCab/IPADIC 61b90ba](https://github.com/taku910/mecab/tree/61b90ba6e669dc2d7d533d4a80d206f3b31d52b1) | MeCab コードは GPL・LGPL・BSD の選択。IPADIC は辞書固有の `mecab-ipadic/COPYING` の条項を参照。 | 構造・分類の比較のみ。 |
| [UniDic 国語研](https://clrd.ninjal.ac.jp/unidic/) | 公式文書・辞書・配布形式ごとの条件を参照。現代書き言葉 UniDic の公開辞書は GPL/LGPL/BSD 選択の配布がある。 | 用語集・FAQ・規程から項目の意味を調査。辞書の実体を取り込んでいない。 |
| [Sudachi 434f31d](https://github.com/WorksApplications/Sudachi/tree/434f31d8af6ef99eee97c57317e5f097dfdfe561)・[SudachiDict 830bf9e](https://github.com/WorksApplications/SudachiDict/tree/830bf9e1313f6f75235ba87ee041e144dbcad8c1) | 本体は Apache-2.0。辞書も Apache-2.0 を掲示し、別途 UniDic・NEologd の由来を掲示。 | 分割粒度と辞書スキーマだけを比較した。 |
| [文法・論文資料](JAPANESE_GRAMMAR.md) | 発行者ごとの条件。転載や外部テストの再配布を前提にしていない。 | 一般的な文法と研究の要約・リンクのみ。 |

追加ライブラリはない。CLI は既存の Kotlin JSON ライブラリと JVM の管理 API を使用する。
