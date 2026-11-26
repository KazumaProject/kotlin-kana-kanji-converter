# 日本語の活用と接続

| 分類 | 設計への反映 |
| --- | --- |
| 五段 | 語尾の段を変える。否定の「う」は「わ」、て・たはイ音便、促音便、撥音便、サ行、ウ音便に分かれる。終止形が「る」でも一段とは限らない。 |
| 上一段・下一段 | 語幹が異なるが、対応範囲では「る」の置換が共通。Mozc の一般的な「一段」から上／下のどちらかは確定できない。 |
| カ変・サ変 | 「くる」は「こ／き／くれ」を使い、漢字の「来」は保持できる。「する／ずる」の活用ではサ変接尾部を扱う。 |
| イ形容詞・形容動詞 | イ形容詞の形態生成と、形容動詞語幹＋助動詞の連体接続は別問題。後者では語幹、助動詞自身の活用、語境界を検査する。 |
| 助動詞 | ダ・ナイ・マス・タ等は固有の型・形を持つ。用言側の活用と助動詞側の形は別々に指定できる。 |
| 格助詞・接続助詞 | 格助詞の候補は格支配や意味でも変わる。接続助詞「ば」などに形から説明できる条件がある。 |
| 終助詞・副助詞・係助詞 | 禁止の「な」は連体修飾の「な」と異なる。「は」「も」等には多様な対比・焦点の用法があり、品詞だけで自動的に一意には選べない。 |
| 不規則・複合・補助・口語 | 「行く」の促音便、「ある」の否定、敬語動詞の一部、「いい」の語幹交替を扱う。複合語・補助動詞は基本形と型が取れれば語尾の規則を適用できる。縮約、歴史的活用、複合語の内部構造や意味は個別データを要する。 |

## 資料と分類体系

- IPADIC の `mecab-ipadic` 辞書 CSV、`matrix.def`、`feature.def` と MeCab の `mecab/src/viterbi.cpp` を資料とした。左右 ID、接続コストと解析特徴をそれぞれ扱う構造が確認できる。[taku910/mecab 61b90ba6e669dc2d7d533d4a80d206f3b31d52b1](https://github.com/taku910/mecab/tree/61b90ba6e669dc2d7d533d4a80d206f3b31d52b1)
- UniDic は短単位の出現形、語彙素、書字形基本形を分ける。形容動詞の語幹を形状詞、活用語尾を助動詞とするため、学校文法の品詞と機械的に同一視できない。[国語研 UniDic 用語集](https://clrd.ninjal.ac.jp/unidic/glossary.html)
- Sudachi の分割モードは一つの文字列に複数の粒度があり得ることを示す。辞書の POS と語境界を他システムの分類へそのまま移せない。[Takaoka et al., Sudachi: a Japanese Tokenizer for Business (2018)](https://aclanthology.org/L18-1355/)
- 日本語では語境界と品詞を同時に扱う利点がある。CRF による学習の研究を参照し、既存のかな漢字ラティスへの明示条件の適用を選んだ。[Kudo, Yamamoto, Matsumoto, Applying Conditional Random Fields to Japanese Morphological Analysis (2004)](https://aclanthology.org/W04-3230/)
- 活用と接続の一般的な機能を確認した。[国際交流基金 文法の教え方 Unit I](https://www.jpf.go.jp/j/urawa/j_rsorcs/methods/dl/bunpo_U1P1_text.pdf)・[文法を楽しく「表現意図 − 指示・命令・禁止」](https://www.jpf.go.jp/j/project/japanese/teach/tsushin/grammar/201603.html)・[「こと」（1）](https://www.jpf.go.jp/j/project/japanese/teach/tsushin/grammar/201112.html)
