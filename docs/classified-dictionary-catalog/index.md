# 分類辞書の収録一覧

30カテゴリ、全体で **836,923組**、カテゴリ別に **853,456レコード**を収録しています。

「組」は読み・表記の重複を除いた件数、「レコード」は品詞・コストの違いも保持したバイナリへの収録件数です。複数カテゴリへの所属があるため、カテゴリ別の組数の合計は全体の組数と一致しません。

一覧は配布対象の固定データから全件生成しています。Geminiとassistantの暫定分類・未確認の読みを含みます。既存28カテゴリのコストと品詞は元辞書の値です。漢方・医療は提供元の読みと空欄へのGemini推定読み（未確認）を採用し、個別の読み訂正には出典を記録します。品詞とコストは本プロジェクトで設定しています。分類取得失敗・未分類・除外候補はこの一覧には含めません。

[不採用語と判断理由](excluded/index.md) · [品詞IDと品詞名](pos.md) · [生成・配布手順](../classified-dictionary-distribution.md) · [漢方・医療の出典記録](../specialist-dictionaries.md)

[人物細分類の全収録語](person-taxonomy/index.md)（特別プレリリース向け）

| カテゴリ | 読み・表記の組 | 読み数 | レコード数 |
|---|---:|---:|---:|
| [人物・人名](person/index.md) | 266,950 | 237,899 | 268,898 |
| [架空キャラクター](character/index.md) | 6,799 | 6,728 | 6,871 |
| [神話・伝承の存在](mythological_figure/index.md) | 3,435 | 3,195 | 3,436 |
| [地名](place/index.md) | 43,377 | 41,365 | 45,089 |
| [住所](address/index.md) | 148,606 | 148,127 | 152,874 |
| [駅・停留所](station/index.md) | 12,756 | 12,396 | 12,758 |
| [施設](facility/index.md) | 35,062 | 33,472 | 35,069 |
| [交通路線](transport_route/index.md) | 4,230 | 4,195 | 4,231 |
| [組織](organization/index.md) | 47,408 | 46,636 | 47,487 |
| [家系・氏族](lineage/index.md) | 2,019 | 1,974 | 2,019 |
| [商品・サービス](product/index.md) | 9,881 | 9,662 | 9,883 |
| [車両・船舶](vehicle/index.md) | 2,579 | 2,546 | 2,579 |
| [イベント・事件](event/index.md) | 8,717 | 8,612 | 8,717 |
| [賞](award/index.md) | 1,167 | 1,150 | 1,167 |
| [条約・協定](agreement/index.md) | 425 | 421 | 425 |
| [事業・キャンペーン](initiative/index.md) | 1,072 | 1,065 | 1,072 |
| [一般語・専門用語](term/index.md) | 108,591 | 104,245 | 108,618 |
| [作品シリーズ](work_franchise/index.md) | 849 | 837 | 849 |
| [漫画作品](work_manga/index.md) | 5,143 | 5,103 | 5,144 |
| [アニメ作品](work_anime/index.md) | 1,104 | 1,088 | 1,104 |
| [映画作品](work_film/index.md) | 6,509 | 6,477 | 6,510 |
| [番組](work_program/index.md) | 9,312 | 9,238 | 9,313 |
| [書籍作品](work_book/index.md) | 7,666 | 7,612 | 7,667 |
| [ゲーム作品](work_game/index.md) | 3,151 | 3,061 | 3,151 |
| [音楽作品](work_music/index.md) | 10,335 | 10,202 | 10,338 |
| [舞台作品](work_stage/index.md) | 575 | 566 | 575 |
| [定期刊行物](work_periodical/index.md) | 1,811 | 1,768 | 1,812 |
| [媒体未特定の作品・美術作品](work_other/index.md) | 2,684 | 2,671 | 2,685 |
| [漢方・生薬](kampo/index.md) | 432 | 418 | 432 |
| [医療](medical/index.md) | 92,683 | 89,486 | 92,683 |

元データSHA-256: `6909ea156e6973e651a2fe1e4858810d4ded340bce8c082e286597fb4cfde8fc`

再生成: `python3 scripts/write_classified_dictionary_catalog.py`
整合確認: `python3 scripts/write_classified_dictionary_catalog.py --check`
